import re
import pandas as pd
from collections import defaultdict


class InvoiceParser:
    def __init__(self):
        self.patterns = {
            "invoice_no": r"发票号码[:：]\s*(\S+)",
            "date": r"开票日期[:：]\s*(\d{4}[年\-]\d{1,2}[月\-]\d{1,2}日?)",
            "buyer": (r"购\s*买\s*方\s*名\s*称[:：]", r"名称[:：]([^\s]+)"),
            "seller": (r"销\s*售\s*方\s*名\s*称[:：]", r"名称[:：]([^\s]+)"),
            "tax_id": r"统一社会信用代码/纳税人识别号[:：](\w{18})",
            "amount": r"¥\s*([\d,]+\.\d{2})",
            "item_start": r"(项目名称\s*规格型号)",
            "tag": r"\*([^*]+)\*",  # 星号标签提取
        }

    def parse(self, text):
        result = defaultdict(list)
        current_item = None
        in_items = False

        # 预处理文本
        lines = [
            line.strip()
            for page in text.split("=====")
            if page
            for line in page.split("\n")
            if line.strip()
        ]

        for line in lines:
            # 基础信息提取
            if not result.get("invoice_no"):
                if match := re.search(self.patterns["invoice_no"], line):
                    result["invoice_no"] = match.group(1)

            if not result.get("date"):
                if match := re.search(self.patterns["date"], line):
                    result["date"] = match.group(1).replace(" ", "")

            # 买卖方信息提取
            if "buyer" not in result and re.search(self.patterns["buyer"][0], line):
                if match := re.search(self.patterns["buyer"][1], line):
                    result["buyer"] = match.group(1)

            if "seller" not in result and re.search(self.patterns["seller"][0], line):
                if match := re.search(self.patterns["seller"][1], line):
                    result["seller"] = match.group(1)

            # 商品明细处理
            if re.search(self.patterns["item_start"], line):
                in_items = True
                continue

            if in_items:
                if "合" in line and "计" in line:  # 结束标志
                    in_items = False
                    if current_item:
                        self._finalize_item(result, current_item)
                    break

                # 商品行识别逻辑
                if self._is_item_line(line):
                    if current_item:  # 完成上一个商品
                        self._finalize_item(result, current_item)
                    current_item = self._parse_item_line(line)
                elif current_item:  # 合并跨行商品名
                    current_item["name"] += " " + line.split()[0]

        # 金额提取
        amount_matches = re.findall(self.patterns["amount"], text)
        if len(amount_matches) >= 2:
            result["total_amount"] = amount_matches[-2]
            result["total_tax"] = amount_matches[-1]

        return result

    def _is_item_line(self, line):
        """智能识别商品行"""
        return re.search(r"\*.*\*", line) or any(
            char in line for char in ["*", "¥", "%"]
        )

    def _parse_item_line(self, line):
        """解析商品行并提取标签"""
        item = {
            "name": "",
            "spec": "",
            "unit": "",
            "quantity": "",
            "unit_price": "",
            "amount": "",
            "tax_rate": "",
            "tag": "",
        }

        # 提取星号标签
        if tag_match := re.search(self.patterns["tag"], line):
            item["tag"] = tag_match.group(1)
            line = line.replace(tag_match.group(0), "")  # 移除标签避免干扰

        # 智能分割字段
        parts = re.split(r"\s{2,}", line)  # 按多个空格分割
        parts = [p for p in parts if p]

        # 动态字段映射
        fields = [
            "name",
            "spec",
            "unit",
            "quantity",
            "unit_price",
            "amount",
            "tax_rate",
        ]
        for i, field in enumerate(fields):
            if i < len(parts):
                item[field] = parts[i].strip()

        return item

    def _finalize_item(self, result, item):
        """完成商品处理"""
        # 清理无效字符
        for k, v in item.items():
            if isinstance(v, str):
                item[k] = re.sub(r"[^\w\.\*\-%]", " ", v).strip()
        result["items"].append(item)


def process_invoices(pdf_texts):
    parser = InvoiceParser()
    all_data = []

    for text in pdf_texts:
        data = parser.parse(text)
        # 转换为主表结构
        main_info = {
            "发票号码": data.get("invoice_no", ""),
            "开票日期": data.get("date", ""),
            "买方名称": data.get("buyer", ""),
            "卖方名称": data.get("seller", ""),
            "总金额": data.get("total_amount", ""),
            "标签": "|".join(
                set([item.get("tag", "") for item in data["items"] if item.get("tag")])
            ),
        }
        # 转换商品明细
        items_df = pd.DataFrame(data["items"])
        all_data.append((main_info, items_df))

    return all_data


import pdfplumber

# 使用示例（需配合PDF文本提取）
if __name__ == "__main__":
    pdf_path = "./invoices/_25957000000000267465.pdf"

    pdf_text = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            pdf_text.append(page.extract_text().split("\n"))
    t = pdf_text[0]
    processed = process_invoices(t)
    print(processed)
    # # 导出到Excel
    # with pd.ExcelWriter("invoices.xlsx") as writer:
    #     for i, (main_info, items_df) in enumerate(processed):
    #         # 主信息表
    #         pd.DataFrame([main_info]).to_excel(
    #             writer, sheet_name=f"发票{i+1}_概览", index=False
    #         )
    #         # 商品明细表
    #         items_df.to_excel(writer, sheet_name=f"发票{i+1}_明细", index=False)
