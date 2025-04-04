import re
from PIL import Image
from pyzbar.pyzbar import decode, ZBarSymbol
import fitz


class InvoiceParser:
    def __init__(self, pdf_path):
        self.file_path = pdf_path

    def parse(self):
        parses = []
        # 根据二维码提取数据
        info_str = self.get_qrcode(self.file_path)
        info_list = info_str.split(",")
        if len(info_list) > 6:
            # 一般电子普票，发票信息存在发票二维码内
            parses.append(
                {
                    "basic_info": {
                        "invoice_code": info_list[3],
                        "date": info_list[5],
                    },
                    "buyer": {},
                    "seller": {},
                    "items": [],
                    "tag": None,
                    "total_amount": info_list[4],
                }
            )
        else:
            # 深圳区块链电子发票，发票二维码是一个链接
            parses.append(
                self.fetch_invoice_info_from_bcfp_shenzhen_chinatax(info_list[0])
            )
        # 根据pdf文件的文本层提取数据
        # self.pdf_text = []
        # with pdfplumber.open(pdf_path) as pdf:
        #     for page in pdf.pages:
        #         self.pdf_text.append(page.extract_text().split("\n"))

        # for data in self.pdf_text:
        #     parse = self.extract_invoice_data_single_page(data)
        #     parses.append(parse)
        return parses[0]

    def fetch_invoice_info_from_bcfp_shenzhen_chinatax(self, url):
        invoice_code = re.findall(r"bill_num=(\w+)", url)[0]
        total_amount = str(float(re.findall(r"total_amount=(\w+)", url)[0]) / 100)
        result = {
            "basic_info": {
                "invoice_code": invoice_code,
                "date": None,
            },
            "buyer": {},
            "seller": {},
            "items": [],
            "tag": None,
            "total_amount": total_amount,
        }
        return result

    def get_qrcode(self, file_path):
        """提取pdf文件中左上角的二维码并识别"""
        pdfDoc = fitz.open(file_path)
        page = pdfDoc[0]  # 只对第一页的二维码进行识别
        mat = fitz.Matrix(3.0, 3.0).prerotate(0)
        # rect = page.rect
        # mp = rect.tl + (rect.br - rect.tl) * 1 / 4
        # clip = fitz.Rect(rect.tl, mp)
        # pix = page.get_pixmap(matrix=mat, alpha=False, clip=clip)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        barcodes = decode(img, symbols=[ZBarSymbol.QRCODE])
        for barcode in barcodes:
            result = barcode.data.decode("utf-8")
            return result

    def extract_invoice_data_single_page(self, data):
        # 关键节点标识
        nodes = {
            "items_start": r"项目名称",
            "total": r"合\s?计",
            "price_with_tax": r"价税合计",
        }

        invoice = {
            "basic_info": {},
            "buyer": {},
            "seller": {},
            "items": [],
            "tag": None,
        }

        current_section = "buyer"
        current_item = None
        item_pattern = re.compile(r"\*([^*]+)\*")  # 提取标签

        for line in data:
            line = line.strip()
            if not line:
                continue
            # 基础信息提取
            print(line)
            if "发票号码" in line:
                invoice_code = re.search(r"[:：]\s?(\S+)", line).group(1)
                invoice["basic_info"]["invoice_code"] = invoice_code
            elif "开票日期" in line:
                date = re.search(r"[:：]\s?(\S+)", line).group(1)
                invoice["basic_info"]["date"] = date

            # 买方/卖方信息提取
            if "名称" in line:
                entity = re.findall(r"[:：]\s?(\S+)", line)
                if current_section == "buyer" and entity:
                    invoice["buyer"]["name"] = entity[0]
                    entity.pop(0)
                    current_section = "seller"  # 切换到卖方
                if current_section == "seller" and entity:
                    invoice["seller"]["name"] = entity[0]
                    entity.pop(0)
            elif "统一社会信用代码" in line:
                codes = re.findall(r"\b[A-Z0-9]{18}\b", line)
                if len(codes) >= 2:
                    invoice["buyer"]["tax_id"], invoice["seller"]["tax_id"] = (
                        codes[0],
                        codes[1],
                    )
                else:
                    if invoice["buyer"].get("tax_id"):
                        invoice["seller"]["tax_id"] = codes[0]
                    else:
                        invoice["buyer"]["tax_id"] = codes[0]

            # 商品条目处理
            if re.search(nodes["items_start"], line):
                current_section = "items"
                continue
            elif re.search(nodes["total"], line):
                if current_item:  # 保存商品信息
                    invoice["items"].append(current_item)
                    current_section = None
                total_values = re.findall(r"¥([\d.-]+)", line)
                if len(total_values) >= 2:
                    invoice["total_amount"] = total_values[0]
                    invoice["total_tax"] = total_values[1]

            # 价税合计
            if re.search(nodes["price_with_tax"], line):
                price_with_tax = re.findall(r"¥([\d.-]+)", line)
                invoice["price_with_tax"] = price_with_tax[0]

            # 商品行智能合并
            if current_section == "items":
                if "*" in line:  # 新商品开始
                    if current_item:  # 保存前一个商品
                        invoice["items"].append(current_item)
                    current_item = self.parse_item(line)
                    # 提取标签（仅首次出现）
                    if not invoice["tag"]:
                        if match := item_pattern.search(line):
                            invoice["tag"] = match.group(1)
                elif current_item:  # 合并多行商品名
                    current_item["name"] += line

        return invoice

    def parse_item(self, line):
        parts = re.split(r"\s+", line)
        # 发票中的"数量"和"单价"列可能被合并为同一个文本，需手动拆分
        if len(parts) > 6:
            try:
                int(parts[-5])  # 正常来说-5是"单位"项，不可能被转换成整型
            except ValueError:
                parts.insert(-5, parts[-4][0])
                parts[-4] = parts[-4][1:]

        return {
            "name": parts[0],
            "spec": parts[-7] if len(parts) > 7 else "",
            "unit": parts[-6] if len(parts) > 6 else "",
            "quantity": parts[-5] if len(parts) > 5 else "",
            "unit_price": parts[-4] if len(parts) > 4 else "",
            "amount": parts[-3] if len(parts) > 3 else "",
            "tax_rate": parts[-2] if len(parts) > 2 else "",
            "tax": parts[-1] if len(parts) > 1 else "",
        }
