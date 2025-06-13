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
    def parse_vat_invoice(results):

        def extract_param(data, key):
            items = data.get(key, "")
            if isinstance(items, list) and len(items) > 0 and isinstance(
                    items[0], dict):
                return items[0].get("word", "")
            else:
                return items

        invoice = Invoice()

        params_dict = {
            'type': 'InvoiceType',
            'province': 'Province',
            'city': 'City',
            'code': 'InvoiceCode',
            'number': 'InvoiceNum',
            'date': 'InvoiceDate',
            'machineCode': 'MachineCode',
            'password': 'Password',
            'verificationCode': 'CheckCode',
            'totalAmount': 'AmountInFiguers',
            'amount': 'TotalAmount',
            'taxAmount': 'TotalTax',
            'sellerTaxID': 'SellerRegisterNum',
            'sellerName': 'SellerName',
            'sellerAddress': 'SellerAddress',
            'sellerBankAccount': 'SellerBank',
            'buyerTaxID': 'PurchaserRegisterNum',
            'buyerName': 'PurchaserName',
            'buyerAddress': 'PurchaserAddress',
            'buyerBankAccount': 'PurchaserBank',
            'payee': 'Payee',
            'reviewer': 'reviewer',
            'noteDrawer': 'NoteDrawer',
            'remark': 'Remarks',
            'crc': 'CheckCode',
        }
        for field, key in params_dict.items():
            invoice.set_field(field, extract_param(results[-1], key))

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

        if not invoice._items:
            raise ValueError("No items found in the invoice.")

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

    @staticmethod
    def parse_train_ticket(results):

        def extract_param(data, key):
            items = data.get(key, "")
            if isinstance(items, list) and len(items) > 0 and isinstance(
                    items[0], dict):
                return items[0].get("word", "")
            else:
                return items

        invoice = Invoice()

        invoice.set_field('type', "电子发票（铁路电子客票）")
        invoice.set_field('number', extract_param(results[-1], 'invoice_num'))
        invoice.set_field('date', extract_param(results[-1], 'date'))
        invoice.set_field('buyerName',
                          extract_param(results[-1], 'purchaser_name'))
        invoice.set_field('buyerTaxID',
                          extract_param(results[-1], 'purchaser_register_num'))

        price = extract_param(results[-1], 'ticket_rates')
        price_value = re.search(r"\d+(?:\.\d+)?", price).group()
        invoice.set_field('totalAmount', price_value)

        remark = (f"电子客票号: {extract_param(results[-1], 'elec_ticket_num')}, "
                  f"始发站: {extract_param(results[-1], 'starting_station')}, "
                  f"终点站: {extract_param(results[-1], 'destination_station')}, "
                  f"乘车人: {extract_param(results[-1], 'name')}, "
                  f"车次: {extract_param(results[-1], 'train_num')}, "
                  f"发车时间: {extract_param(results[-1], 'time')}, "
                  f"座次: {extract_param(results[-1], 'seat_num')}, "
                  f"座位类型: {extract_param(results[-1], 'seat_category')}, ")
        invoice.set_field('remark', remark)

        return invoice

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

        return BaiduOCR.parse_vat_invoice(results)

    @staticmethod
    def multiple_invoice_recognition(file_type: str, base64_data) -> Invoice:
        """
        智能财务票据识别

        doc: https://cloud.baidu.com/doc/OCR/s/7ktb8md0j
        """
        if not BaiduOCR.access_token:
            BaiduOCR.refresh_access_token()

        url = f"https://aip.baidubce.com/rest/2.0/ocr/v1/multiple_invoice?access_token={BaiduOCR.access_token}"
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
        }

        results = []
        invoice_type = ""
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
                invoice_type = page['words_result'][0]['type']
                results.append(page["words_result"][0]['result'])
        elif file_type == "image":
            payload = f"image={urllib.parse.quote_plus(base64_data)}&seal_tag=false"
            response = requests.request("POST",
                                        url,
                                        headers=headers,
                                        data=payload.encode("utf-8"))
            page = response.json()
            invoice_type = page['words_result'][0]['type']
            results.append(page["words_result"][0]['result'])
        elif file_type == "ofd":
            pass

        if invoice_type == "vat_invoice":
            return BaiduOCR.parse_vat_invoice(results)
        elif invoice_type == "train_ticket":
            return BaiduOCR.parse_train_ticket(results)
        else:
            raise ValueError(f"Unkown invoice type {{{invoice_type}}}")
