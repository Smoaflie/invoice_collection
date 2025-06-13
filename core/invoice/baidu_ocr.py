import os
import requests
import urllib.parse
import re
from .base import *

BAIDU_API_KEY = os.getenv("BAIDU_API_KEY")
BAIDU_SECRET_KEY = os.getenv("BAIDU_SECRET_KEY")


class BaiduOCR(object):
    access_token = None

    @staticmethod
    def is_valid():
        """
        检查百度OCR的API Key和Secret Key是否有效
        """
        if not BAIDU_API_KEY or not BAIDU_SECRET_KEY:
            return False
        BaiduOCR.refresh_access_token()
        if not BaiduOCR.access_token:
            return False
        return True

    @staticmethod
    def refresh_access_token():
        """
        获取百度OCR的Access Token
        """
        url = "https://aip.baidubce.com/oauth/2.0/token"
        params = {
            "grant_type": "client_credentials",
            "client_id": BAIDU_API_KEY,
            "client_secret": BAIDU_SECRET_KEY,
        }
        response = requests.post(url, params=params)
        BaiduOCR.access_token = response.json().get("access_token", None)

    @staticmethod
    def vat_invoice_recognition(file_type: str, base64_data) -> Invoice:
        """
        增值税发票识别

        doc: https://cloud.baidu.com/doc/OCR/s/nk3h7xy2t
        """
        if not BaiduOCR.access_token:
            BaiduOCR.refresh_access_token()

        url = f"https://aip.baidubce.com/rest/2.0/ocr/v1/vat_invoice?access_token={BaiduOCR.access_token}"
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }

        results = []
        if file_type == "pdf":
            pdf_page_max = float("inf")
            pdf_page = 1
            while pdf_page < pdf_page_max:
                payload = f"pdf_file={urllib.parse.quote_plus(base64_data)}&pdf_file_num={pdf_page}&seal_tag=false"
                response = requests.request("POST",
                                            url,
                                            headers=headers,
                                            data=payload.encode("utf-8"))
                page = response.json()

                pdf_page += 1
                pdf_page_max = min(pdf_page_max,
                                   int(page.get("pdf_file_size")))
                results.append(page["words_result"])
        elif file_type == "image":
            payload = f"image={urllib.parse.quote_plus(base64_data)}&seal_tag=false"
            response = requests.request("POST",
                                        url,
                                        headers=headers,
                                        data=payload.encode("utf-8"))
            page = response.json()

            results.append(page["words_result"])
        elif file_type == "ofd":
            pass

        invoice = Invoice()
        try:
            invoice.set_field('type', results[0].get("InvoiceType"))
        except StopIteration or ValueError:
            if results[0].get("InvoiceType"):
                raise ValueError(
                    f"Unkown invoice type {{{results[0].get('InvoiceType')}}}")
            else:
                raise ValueError(
                    f"BaiduApi parse error. Lack of necessary parameters.")

        invoice.set_field("province", results[-1].get("Province", ""))
        invoice.set_field("city", results[-1].get("City", ""))
        invoice.set_field("code", results[-1].get("InvoiceCode", ""))
        invoice.set_field("number", results[-1].get("InvoiceNum", ""))
        invoice.set_field("date", results[-1].get("InvoiceDate", ""))
        invoice.set_field("machineCode", results[-1].get("MachineCode", ""))
        invoice.set_field("password", results[-1].get("Password", ""))
        invoice.set_field("verificationCode", results[-1].get("CheckCode", ""))

        invoice.set_field("totalAmount",
                          results[-1].get("AmountInFiguers", ""))
        invoice.set_field("amount", results[-1].get("TotalAmount", ""))
        invoice.set_field("taxAmount", results[-1].get("TotalTax", ""))

        invoice.set_field("sellerTaxID",
                          results[-1].get("SellerRegisterNum", ""))
        invoice.set_field("sellerName", results[-1].get("SellerName", ""))
        invoice.set_field("sellerAddress",
                          results[-1].get("SellerAddress", ""))
        invoice.set_field("sellerBankAccount",
                          results[-1].get("SellerBank", ""))

        invoice.set_field("buyerTaxID",
                          results[-1].get("PurchaserRegisterNum", ""))
        invoice.set_field("buyerName", results[-1].get("PurchaserName", ""))
        invoice.set_field("buyerAddress",
                          results[-1].get("PurchaserAddress", ""))
        invoice.set_field("buyerBankAccount",
                          results[-1].get("PurchaserBank", ""))

        invoice.set_field("payee", results[-1].get("Payee", ""))
        invoice.set_field("reviewer", "")
        invoice.set_field("noteDrawer", results[-1].get("NoteDrawer", ""))
        invoice.set_field("remark", results[-1].get("Remarks", ""))
        invoice.set_field("crc", results[-1].get("CheckCode", ""))

        all_lists = (
            "CommodityName",
            "CommodityType",
            "CommodityUnit",
            "CommodityNum",
            "CommodityPrice",
            "CommodityAmount",
            "CommodityTaxRate",
            "CommodityTax",
        )
        next_row_index = 0
        items = {}
        for key in all_lists:
            items[key] = []
        for page in results:
            cache = {}
            max_row = 0
            for key in all_lists:
                cache[key] = page.get(key, [])
                if cache[key]:
                    max_row = max(int(cache[key][-1]["row"]), max_row)
            for key in all_lists:
                for i in cache[key]:
                    items[key].append({
                        **i, "row":
                        str(int(i["row"]) + next_row_index)
                    })
            next_row_index += max_row

        format_str_list = {}
        for key in all_lists:
            format_str_list[key] = []
            index = 0
            for i in items[key]:
                while index < int(i["row"]):
                    format_str_list[key].append("")
                    index += 1
                format_str_list[key].append(i["word"])
                index += 1

        items_start_row_index = []
        splice_string = lambda str_list, start, end: "".join(
            [i for i in str_list[start:end]])
        for i in items["CommodityAmount"]:
            items_start_row_index.append(int(i["row"]))
        items_start_row_index.append(int(next_row_index) + 1)
        for i in range(len(items_start_row_index) - 1):
            item = InvoiceItem()
            item.set_name(
                splice_string(
                    format_str_list["CommodityName"],
                    items_start_row_index[i],
                    items_start_row_index[i + 1],
                ))
            item.set_type(
                splice_string(
                    format_str_list["CommodityType"],
                    items_start_row_index[i],
                    items_start_row_index[i + 1],
                ))
            item.set_unit(
                splice_string(
                    format_str_list["CommodityUnit"],
                    items_start_row_index[i],
                    items_start_row_index[i + 1],
                ))
            item.set_num(
                splice_string(
                    format_str_list["CommodityNum"],
                    items_start_row_index[i],
                    items_start_row_index[i + 1],
                ))
            item.set_unit_price(
                splice_string(
                    format_str_list["CommodityPrice"],
                    items_start_row_index[i],
                    items_start_row_index[i + 1],
                ))
            item.set_amount(
                splice_string(
                    format_str_list["CommodityAmount"],
                    items_start_row_index[i],
                    items_start_row_index[i + 1],
                ))
            item.set_tax_rate(
                splice_string(
                    format_str_list["CommodityTaxRate"],
                    items_start_row_index[i],
                    items_start_row_index[i + 1],
                ))
            item.set_tax(
                splice_string(
                    format_str_list["CommodityTax"],
                    items_start_row_index[i],
                    items_start_row_index[i + 1],
                ))
            invoice.add_item(item)

        item_tag = re.findall(r"\*\S+\*", invoice._items[0].name)

        invoice.set_field("item_tag", item_tag[0] if item_tag else "")
        invoice.set_field(
            "items_brief",
            invoice._items[0].name + (" 等" if len(invoice._items) > 1 else ""))
        invoice.set_field("items_unit", invoice._items[0].unit)
        invoice.set_field("item_num", len(invoice._items))
        invoice.set_field("total_items_num",
                          sum(item.num for item in invoice._items))
        return invoice
