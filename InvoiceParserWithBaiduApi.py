import base64
from datetime import datetime
import re
from typing import List
import urllib
import json
import urllib.parse
import pandas as pd
import requests
import sqlite3
import os
from collections import defaultdict
import shutil
import argparse
from pathlib import Path

from api.api_servers import APIContainer

API_KEY = "Hmtt6uHI2nXeYriVWYFRCK13"
SECRET_KEY = "jFoffth4rg7iD7jvtSI1ap9M0s521bWe"

# 读取历史发票数据
history_invoices = []
with open("history_invoices.json", "r", encoding="utf-8") as f:
    history_invoices = json.load(f)


class InvoiceItem:
    def __init__(self):
        self.name = ""
        self.type = ""
        self.unit = ""
        self.num = 0
        self.unit_price = 0.00
        self.amount = 0.00
        self.tax_rate = "0.00%"
        self.tax = 0.00

    def set_name(self, name):
        self.name = name

    def set_type(self, type):
        self.type = type

    def set_unit(self, unit):
        self.unit = unit

    def set_num(self, num):
        try:
            self.num = int(num)
        except ValueError or AttributeError:
            self.num = 0.00

    def set_unit_price(self, unit_price):
        try:
            self.price = float(unit_price)
        except ValueError or AttributeError:
            self.price = 0.00

    def set_amount(self, amount):
        try:
            self.amount = float(amount)
        except ValueError or AttributeError:
            self.amount = 0.00

    def set_tax_rate(self, tax_rate):
        self.tax_rate = tax_rate

    def set_tax(self, tax):
        try:
            self.tax = float(tax)
        except ValueError or AttributeError:
            self.tax = 0.00

    @property
    def data(self):
        return {
            "name": self.name,
            "type": self.type,
            "unit": self.unit,
            "num": self.num,
            "unit_price": self.unit_price,
            "amount": self.amount,
            "tax_rate": self.tax_rate,
            "tax": self.tax,
        }


class Invoice:
    invoice_type_map = {
        "04": "普通发票",
        "10": "增值税电子普通发票",
        "31": "电子发票(增值税专用发票)",
        "311": "区块链发票",
        "312": "电子发票(专用发票)",
        "32": "电子发票(普通发票)",
        "321": "电子普通发票",
        "-1": "深圳电子普通发票",
    }

    def __init__(self, path, parse_mode="Database", params: dict = None):
        self.file_path = path
        self.file_name = os.path.basename(path)
        self.params = params
        self._items = None
        if parse_mode == "BaiduApi":
            self.parse_with_BaiduApi()
        elif parse_mode == "Database":
            self.parse_with_Database()
        else:
            raise ValueError("Invalid parse mode. Use 'BaiduApi' or 'Database'.")

    def parse_with_Database(self):
        db_path = self.params.get("DB_PATH", "invoices.db")
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM invoices WHERE file_name=?",
                (self.file_name,),
            )
            columns = [col[0] for col in cursor.description]  # 动态获取字段名
            row = cursor.fetchone()
            if not row:
                raise ValueError(f"Invoice {self.file_name} not found in database.")

            invoice_data = dict(zip(columns, row))
            self._province = invoice_data.get("province", "")
            self._city = invoice_data.get("city", "")
            self._code = invoice_data.get("code", "")
            self._number = invoice_data.get("number", "")
            self._date = invoice_data.get("date", "")
            self._machineCode = invoice_data.get("machineCode", "")
            self._password = invoice_data.get("password", "")
            self._verificationCode = invoice_data.get("verificationCode", "")

            self._totalAmount = invoice_data.get("totalAmount", "")
            self._amount = invoice_data.get("amount", "")
            self._taxAmount = invoice_data.get("taxAmount", "")

            self._sellerTaxID = invoice_data.get("sellerTaxID", "")
            self._sellerName = invoice_data.get("sellerName", "")
            self._sellerAddress = invoice_data.get("sellerAddress", "")
            self._sellerBankAccount = invoice_data.get("sellerBankAccount", "")

            self._buyerTaxID = invoice_data.get("buyerTaxID", "")
            self._buyerName = invoice_data.get("buyerName", "")
            self._buyerAddress = invoice_data.get("buyerAddress", "")
            self._buyerBankAccount = invoice_data.get("buyerBankAccount", "")

            self._payee = invoice_data.get("payee", "")
            self._reviewer = invoice_data.get("reviewer", "")
            self._noteDrawer = invoice_data.get("noteDrawer", "")
            self._remark = invoice_data.get("remark", "")
            self._crc = invoice_data.get("crc", "")

    def parse_with_BaiduApi(self):
        parse_cache_dir = os.path.join(
            os.path.dirname(self.file_path), "parseByBaiduApi"
        )
        os.makedirs(parse_cache_dir, exist_ok=True)
        pages = []

        pdf_page_max = float("inf")
        pdf_page = 1
        while pdf_page < pdf_page_max:
            parse_result_path = os.path.join(
                parse_cache_dir,
                f"{os.path.splitext(self.file_name)[0]}_{pdf_page}.json",
            )

            if os.path.exists(parse_result_path):
                with open(parse_result_path, "r", encoding="utf-8") as f:
                    page = json.load(f)
            else:
                url = (
                    "https://aip.baidubce.com/rest/2.0/ocr/v1/vat_invoice?access_token="
                    + Invoice._get_BaiduApi_access_token(
                        self.params.get("API_KEY"), self.params.get("SECRET_KEY")
                    )
                )

                payload = f"pdf_file={Invoice._get_file_content_as_base64(self.file_path, True)}&pdf_file_num={pdf_page}&seal_tag=false"
                headers = {
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "application/json",
                }

                response = requests.request(
                    "POST", url, headers=headers, data=payload.encode("utf-8")
                )
                page = response.json()
                with open(parse_result_path, "w", encoding="utf-8") as f:
                    f.write(json.dumps(page, ensure_ascii=False, indent=2))

            pdf_page += 1
            pdf_page_max = min(pdf_page_max, int(page.get("pdf_file_size")))
            pages.append(page["words_result"])

        try:
            self._type = next(
                key
                for key, value in self.invoice_type_map.items()
                if value == pages[0].get("InvoiceType")
            )
        except StopIteration or ValueError:
            if pages[0].get("InvoiceType"):
                raise ValueError(
                    f"Unkown invoice type {self.file_path} : {pages[0].get('InvoiceType')}"
                )
            else:
                raise ValueError(f"BaiduApi can not parse {self.file_path}")
        self._province = pages[-1].get("Province", "")
        self._city = pages[-1].get("City", "")
        self._code = pages[-1].get("InvoiceCode", "")
        self._number = pages[-1].get("InvoiceNum", "")
        self._date = pages[-1].get("InvoiceDate", "")
        self._machineCode = pages[-1].get("MachineCode", "")
        self._password = pages[-1].get("Password", "")
        self._verificationCode = pages[-1].get("CheckCode", "")

        self._totalAmount = pages[-1].get("AmountInFiguers", "")
        self._amount = pages[-1].get("TotalAmount", "")
        self._taxAmount = pages[-1].get("TotalTax", "")

        self._sellerTaxID = pages[-1].get("SellerRegisterNum", "")
        self._sellerName = pages[-1].get("SellerName", "")
        self._sellerAddress = pages[-1].get("SellerAddress", "")
        self._sellerBankAccount = pages[-1].get("SellerBank", "")

        self._buyerTaxID = pages[-1].get("PurchaserRegisterNum", "")
        self._buyerName = pages[-1].get("PurchaserName", "")
        self._buyerAddress = pages[-1].get("PurchaserAddress", "")
        self._buyerBankAccount = pages[-1].get("PurchaserBank", "")

        self._payee = pages[-1].get("Payee", "")
        self._reviewer = ""
        self._noteDrawer = pages[-1].get("NoteDrawer", "")
        self._remark = pages[-1].get("Remarks", "")
        self._crc = pages[-1].get("CheckCode", "")

        self._items = []
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
        for page in pages:
            cache = {}
            max_row = 0
            for key in all_lists:
                cache[key] = page.get(key, [])
                if cache[key]:
                    max_row = max(int(cache[key][-1]["row"]), max_row)
            for key in all_lists:
                for i in cache[key]:
                    items[key].append({**i, "row": str(int(i["row"]) + next_row_index)})
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
            [i for i in str_list[start:end]]
        )
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
                )
            )
            item.set_type(
                splice_string(
                    format_str_list["CommodityType"],
                    items_start_row_index[i],
                    items_start_row_index[i + 1],
                )
            )
            item.set_unit(
                splice_string(
                    format_str_list["CommodityUnit"],
                    items_start_row_index[i],
                    items_start_row_index[i + 1],
                )
            )
            item.set_num(
                splice_string(
                    format_str_list["CommodityNum"],
                    items_start_row_index[i],
                    items_start_row_index[i + 1],
                )
            )
            item.set_unit_price(
                splice_string(
                    format_str_list["CommodityPrice"],
                    items_start_row_index[i],
                    items_start_row_index[i + 1],
                )
            )
            item.set_amount(
                splice_string(
                    format_str_list["CommodityAmount"],
                    items_start_row_index[i],
                    items_start_row_index[i + 1],
                )
            )
            item.set_tax_rate(
                splice_string(
                    format_str_list["CommodityTaxRate"],
                    items_start_row_index[i],
                    items_start_row_index[i + 1],
                )
            )
            item.set_tax(
                splice_string(
                    format_str_list["CommodityTax"],
                    items_start_row_index[i],
                    items_start_row_index[i + 1],
                )
            )
            self._items.append(item)

        item_tag = re.findall(r"\*\S+\*", self._items[0].name)
        self._item_tag = item_tag[0] if item_tag else ""
        self._items_brief = self._items[0].name + (
            " 等" if len(self._items) > 1 else ""
        )
        self._items_unit = self._items[0].unit
        self._item_num = len(self._items)
        self._total_items_num = sum(item.num for item in self._items)

    def check(self, custom_check_function=None):
        """
        Args:
            custom_check_function (_type_, optional): e.g:
                def vertify_invoice_title(invoice):
                    if invoice.buyerName != "xxx" and invoice.buyerTaxID != "xxx":
                        return {"status":"error", "message":"发票抬头不匹配"}
                    else:
                        return {"status":"success"}

        Returns:
            {
                "status": "success" or "error",
                "message": "error message" or ""
            }
        """
        necessary_parameters_to_query = [
            "type",
            "number",
            "date",
            "sellerTaxID",
            "sellerName",
            "items",
            "totalAmount",
            "buyerTaxID",
            "buyerName",
        ]
        unkown_fields = []
        for field in necessary_parameters_to_query:
            if not getattr(self, field):
                unkown_fields.append(field)
        if unkown_fields:
            return {
                "status": "error",
                "message": f"File '{self.file_path}' is missing bellow fields: {', '.join(unkown_fields)}",
            }

        if custom_check_function:
            custom_check_result = custom_check_function(self)
            if custom_check_result["status"] == "error":
                return {
                    "status": "error",
                    "message": f"Custom check failed: {custom_check_result['message']}",
                }

        return {"status": "success", "message": ""}

    def _get_file_content_as_base64(path, urlencoded=False):
        """
        获取文件base64编码
        :param path: 文件路径
        :param urlencoded: 是否对结果进行urlencoded
        :return: base64编码信息
        """
        with open(path, "rb") as f:
            content = base64.b64encode(f.read()).decode("utf8")
            if urlencoded:
                content = urllib.parse.quote_plus(content)
        return content

    def _get_BaiduApi_access_token(API_KEY, SECRET_KEY):
        """
        使用 AK，SK 生成鉴权签名（Access Token）
        :return: access_token，或是None(如果错误)
        """
        url = "https://aip.baidubce.com/oauth/2.0/token"
        params = {
            "grant_type": "client_credentials",
            "client_id": API_KEY,
            "client_secret": SECRET_KEY,
        }
        return str(requests.post(url, params=params).json().get("access_token"))

    @property
    def type(self):
        """发票类型"""
        if hasattr(self, "_type"):
            return self.invoice_type_map[self._type]
        else:
            return ""

    @property
    def code(self):
        """发票代码 - 仅 增值税电子普通发票 中存在"""
        if hasattr(self, "_code"):
            return self._code
        else:
            return ""

    @property
    def number(self):
        """发票号码"""
        if hasattr(self, "_number"):
            return self._number
        else:
            return ""

    @property
    def date(self):
        """开票日期"""
        if hasattr(self, "_date"):
            return self._date
        else:
            return ""

    @property
    def sellerTaxID(self):
        """销售方识别号"""
        if hasattr(self, "_sellerTaxID"):
            return self._sellerTaxID
        else:
            return ""

    @property
    def sellerName(self):
        """销售方名称"""
        if hasattr(self, "_sellerName"):
            return self._sellerName
        else:
            return ""

    @property
    def buyerTaxID(self):
        """购买方识别号"""
        if hasattr(self, "_buyerTaxID"):
            return self._buyerTaxID
        else:
            return ""

    @property
    def buyerName(self):
        """购买方名称"""
        if hasattr(self, "_buyerName"):
            return self._buyerName
        else:
            return ""

    @property
    def items(self):
        """商品列表"""
        if hasattr(self, "_items") and self._items:
            return [item.data for item in self._items]
        else:
            return []

    @property
    def amount(self):
        """金额"""
        try:
            return float(self._amount)
        except ValueError or AttributeError:
            return 0.00

    @property
    def taxAmount(self):
        """税额"""
        try:
            return float(self._taxAmount)
        except ValueError or AttributeError:
            return 0.00

    @property
    def totalAmount(self):
        """价税合计"""
        try:
            return float(self._totalAmount)
        except ValueError or AttributeError:
            return 0.00

    @property
    def sellerAddress(self):
        """销售方地址、电话 - 仅 增值税电子普通发票 中存在"""
        if hasattr(self, "_sellerAddress"):
            return self._sellerAddress
        else:
            return ""

    @property
    def sellerBankAccount(self):
        """销售方开户行及账号 - 仅 增值税电子普通发票 中存在"""
        if hasattr(self, "_sellerBankAccount"):
            return self._sellerBankAccount
        else:
            return ""

    @property
    def buyerAddress(self):
        """购买方地址、电话 - 仅 增值税电子普通发票 中存在"""
        if hasattr(self, "_buyerAddress"):
            return self._buyerAddress
        else:
            return ""

    @property
    def buyerBankAccount(self):
        """购买方开户行及账号 - 仅 增值税电子普通发票 中存在"""
        if hasattr(self, "_buyerBankAccount"):
            return self._buyerBankAccount
        else:
            return ""

    @property
    def payee(self):
        """收款人 - 仅 增值税电子普通发票 中存在"""
        if hasattr(self, "_payee"):
            return self._payee
        else:
            return ""

    @property
    def reviewer(self):
        """复核 - 仅 增值税电子普通发票 中存在"""
        if hasattr(self, "_reviewer"):
            return self._reviewer
        else:
            return ""

    @property
    def noteDrawer(self):
        """开票人"""
        if hasattr(self, "_noteDrawer"):
            return self._noteDrawer
        else:
            return ""

    @property
    def verificationCode(self):
        """校验码 - 仅 增值税电子普通发票 中存在"""
        if hasattr(self, "_verificationCode"):
            return self._verificationCode
        else:
            return ""

    @property
    def CRC(self):
        """CRC算法产生的机密信息"""
        if hasattr(self, "_crc"):
            return self._crc
        else:
            return ""

    @property
    def remark(self):
        """CRC算法产生的机密信息"""
        if hasattr(self, "_remark"):
            return self._remark
        else:
            return ""

    @property
    def item_num(self):
        """商品数量(发票上记录了多少种商品)"""
        if hasattr(self, "_item_num"):
            return self._item_num
        else:
            return ""

    @property
    def total_items_num(self):
        """总商品数量(不同商品各自的数量的总和)"""
        if hasattr(self, "_total_items_num"):
            return self._total_items_num
        else:
            return ""

    @property
    def items_brief(self):
        """商品简介 f"{第一个商品} 等" """
        if hasattr(self, "_items_brief"):
            return self._items_brief
        else:
            return ""

    @property
    def items_unit(self):
        """商品简介 f"{第一个商品} 等" """
        if hasattr(self, "_items_unit"):
            return self._items_unit
        else:
            return ""

    @property
    def item_tag(self):
        """商品标签 (取第一个商品的标签)"""
        if hasattr(self, "_item_tag"):
            return self._item_tag
        else:
            return ""

    @property
    def data(self):
        return {
            "file_name": self.file_name,
            "file_path": self.file_path,
            "type": self.type,
            "code": self.code,
            "number": self.number,
            "date": self.date,
            "buyerTaxID": self.buyerTaxID,
            "buyerName": self.buyerName,
            "buyerAddress": self.buyerAddress,
            "buyerBankAccount": self.buyerBankAccount,
            "sellerTaxID": self.sellerTaxID,
            "sellerName": self.sellerName,
            "sellerAddress": self.sellerAddress,
            "sellerBankAccount": self.sellerBankAccount,
            "items_brief": self.items_brief,
            "items_unit": self.items_unit,
            "item_tag": self.item_tag,
            "payee": self.payee,
            "reviewer": self.reviewer,
            "noteDrawer": self.noteDrawer,
            "verificationCode": self.verificationCode,
            "CRC": self.CRC,
            "remark": self.remark,
            "items": self.items,
            "amount": self.amount,
            "taxAmount": self.taxAmount,
            "totalAmount": self.totalAmount,
            "item_num": self.item_num,
            "total_items_num": self.total_items_num,
        }


class InvoiceDB:
    InvoiceState = {
        "DROPPED": -1,  # 放弃
        "UNSUBMITTED": 0,  # 未提交
        "SUBMITTED": 1,  # 已提交
        "COMPLETED": 2,  # 已完成
    }

    def __init__(self, db_path="invoices.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            # 发票主表
            conn.execute(
                """CREATE TABLE IF NOT EXISTS invoices
                         (id INTEGER PRIMARY KEY,
                         file_name TEXT UNIQUE,
                         file_path TEXT UNIQUE,
                         type INTEGER,
                         code TEXT,
                         number TEXT UNIQUE,
                         date TEXT,
                         sellerTaxID TEXT,
                         sellerName TEXT,
                         buyerTaxID TEXT,
                         buyerName TEXT,
                         amount REAL,
                         taxAmount REAL,
                         totalAmount REAL,
                         sellerAddress TEXT,
                         sellerBankAccount TEXT,
                         buyerAddress TEXT,
                         buyerBankAccount TEXT,
                         payee TEXT,
                         reviewer TEXT,
                         noteDrawer TEXT,
                         verificationCode TEXT,
                         CRC TEXT,
                         remark TEXT,
                         items_brief TEXT,
                         items_unit TEXT,
                         item_tag TEXT,
                         item_num INTEGER,
                         total_items_num INTEGER,
                         record_index INTEGER,
                         file_index_in_record INTEGER,
                         belonger TEXT,
                         state INTEGER DEFAULT 0,
                         error_message TEXT)"""
            )

            # (多维表格)记录主表
            conn.execute(
                """CREATE TABLE IF NOT EXISTS records
                         (id TEXT PRIMARY KEY,
                         record_index INTEGER,
                         remark TEXT,
                         creator_name TEXT)"""
            )

            # 商品明细表
            conn.execute(
                """CREATE TABLE IF NOT EXISTS items
                         (id INTEGER PRIMARY KEY,
                         invoice_number TEXT,
                         name TEXT,
                         type TEXT,
                         unit TEXT,
                         num REAL,
                         unit_price REAL,
                         amount REAL,
                         tax_rate TEXT,
                         tax REAL,
                         FOREIGN KEY(invoice_number) REFERENCES invoices(number))"""
            )

            # 标签系统
            conn.execute(
                """CREATE TABLE IF NOT EXISTS tags
                         (id INTEGER PRIMARY KEY,
                         name TEXT UNIQUE)"""
            )
            conn.execute(
                """CREATE TABLE IF NOT EXISTS invoice_tags
                         (invoice_number TEXT,
                         tag_id INTEGER,
                         PRIMARY KEY (invoice_number, tag_id),
                         FOREIGN KEY(tag_id) REFERENCES tags(id),
                         FOREIGN KEY(invoice_number) REFERENCES invoices(number))"""
            )
            conn.execute(
                """CREATE TABLE IF NOT EXISTS record_tags
                         (record_index INTEGER,
                         tag_id INTEGER,
                         PRIMARY KEY (record_index, tag_id),
                         FOREIGN KEY(record_index) REFERENCES records(record_index),
                         FOREIGN KEY(tag_id) REFERENCES tags(id))"""
            )

            # (optional)报销单
            conn.execute(
                """CREATE TABLE IF NOT EXISTS reimbursement_tables
                         (table_id TEXT,
                         invoice_number TEXT PRIMARY KEY)"""
            )

            conn.commit()

    def add_invoice(
        self,
        invoice: Invoice,
        tags=[],
        record_index=-1,
        file_index_in_record=-1,
        belonger="Unkown",
    ):
        """
        添加发票信息到数据库
        """
        try:
            # Step 1: 建立数据库连接
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                # Step 2: 检查重复
                cursor.execute(
                    "SELECT file_name, record_index, file_index_in_record FROM invoices WHERE number=?",
                    (invoice.number,),
                )
                existing = cursor.fetchone()

                if existing:
                    is_new = False
                    if existing[0] != invoice.file_name:
                        return {
                            "status": "error",
                            "message": "Duplicate invoice code with different file name.",
                            "elder": {
                                "file_name": existing[0],
                                "index": f"{existing[1]}-{existing[2]}",
                            },
                            "new": {
                                "file_name": invoice.file_name,
                                "index": f"{record_index}-{file_index_in_record}",
                            },
                        }

                else:
                    # Step 3: 插入新发票
                    invoice_data = invoice.data
                    invoice_data.pop("items", None)
                    fixed_columns = [
                        "record_index",
                        "file_index_in_record",
                        "belonger",
                        "state",
                        "error_message",
                    ]
                    columns = ", ".join(list(invoice_data.keys()) + fixed_columns)
                    placeholders = ", ".join(
                        [f":{key}" for key in invoice_data.keys()]
                        + [f":{col}" for col in fixed_columns]  # 关键修复点
                    )

                    invoice_check_info = invoice.check(vertify_invoice_title)
                    params = {
                        **invoice_data,
                        "record_index": int(record_index),
                        "file_index_in_record": int(file_index_in_record),
                        "belonger": belonger,
                        "state": 0 if invoice_check_info["status"] == "success" else -1,
                        "error_message": invoice_check_info["message"],
                    }
                    cursor.execute(
                        f"""
                        INSERT INTO invoices ({columns})
                        VALUES ({placeholders})
                        """,
                        params,
                    )
                    is_new = True

                # Step 4: 插入商品明细
                for item_data in invoice.items:
                    columns = ", ".join(item_data.keys())
                    placeholders = ", ".join([f":{key}" for key in item_data.keys()])
                    cursor.execute(
                        f"""
                        INSERT INTO items ({columns})
                        VALUES ({placeholders})
                        """,
                        item_data,
                    )

                # Step 5: 处理标签
                InvoiceDB._process_tags(cursor, tags, invoice_number=invoice.number)

                conn.commit()
                return {"status": "success", "is_new": is_new}

        except Exception as e:
            raise
            return {"status": "error", "message": str(e)}

    def update_record_info(
        self, record_id, record_index, remark, creator_name, tags=[]
    ):
        """更新发票对应的表单记录信息"""
        try:
            # Step 1: 建立数据库连接
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                # Step 2: 检查重复
                cursor.execute(
                    "SELECT id FROM records WHERE id=?",
                    (record_id,),
                )
                existing = cursor.fetchone()

                if existing:
                    is_new = False

                else:
                    # Step 3: 添加新记录信息
                    cursor.execute(
                        """INSERT INTO records 
                                (id, record_index, remark, creator_name)
                                VALUES (?, ?, ?, ?)""",
                        (record_id, record_index, remark, creator_name),
                    )
                    is_new = True

                    # Step 4: 处理标签
                    InvoiceDB._process_tags(cursor, tags, record_index=record_index)

                    conn.commit()
                return {"status": "success", "is_new": is_new}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _process_tags(cursor, tags, invoice_number=None, record_index=None):
        """标签处理子系统"""
        if invoice_number:
            # 删除旧标签关联
            cursor.execute(
                "DELETE FROM invoice_tags WHERE invoice_number=?", (invoice_number,)
            )

            # 插入新标签
            for tag_name in tags:
                cursor.execute(
                    "INSERT OR IGNORE INTO tags (name) VALUES (?)", (tag_name,)
                )
                cursor.execute("SELECT id FROM tags WHERE name=?", (tag_name,))
                tag_id = cursor.fetchone()[0]
                cursor.execute(
                    "INSERT OR IGNORE INTO invoice_tags VALUES (?,?)",
                    (invoice_number, tag_id),
                )
        elif record_index:
            # 删除旧标签关联
            cursor.execute(
                "DELETE FROM record_tags WHERE record_index=?", (record_index,)
            )

            # 插入新标签
            for tag_name in tags:
                cursor.execute(
                    "INSERT OR IGNORE INTO tags (name) VALUES (?)", (tag_name,)
                )
                cursor.execute("SELECT id FROM tags WHERE name=?", (tag_name,))
                tag_id = cursor.fetchone()[0]
                cursor.execute(
                    "INSERT OR IGNORE INTO record_tags VALUES (?,?)",
                    (record_index, tag_id),
                )

    def search_by_tag(self, tag_name):
        """按标签查询"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """SELECT i.* FROM invoices i
                           JOIN invoice_tags it ON i.number = it.invoice_number
                           JOIN tags t ON t.id = it.tag_id
                           WHERE t.name=?""",
                (tag_name,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def update_invoice_state(self, invoice_number: str, new_state: int):
        """更新发票状态"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE invoices SET state = ? WHERE number = ?",
                    (int(new_state), invoice_number),
                )
                conn.commit()
                return cursor.rowcount > 0
        except sqlite3.Error as e:
            print(f"状态更新失败: {e}")
            return False

    def get_invoices_sorted(self, sort_by: str = "record_index"):
        """获取排序后的发票数据"""
        valid_sorts = ["record_index", "date", "belonger", "state"]
        sort_by = sort_by if sort_by in valid_sorts else "record_index"

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(f"SELECT * FROM invoices ORDER BY {sort_by} DESC")
            return [dict(row) for row in cursor.fetchall()]

    def update_reimbursement_tables(self, reimbursement_tables: dict, state=1):
        """
        更新报销单信息

        Args:
            reimbursement_tables (dict):
                {
                    "reimbursement_table_id": [
                        "invoice_number1",
                        "invoice_number2",
                        ...
                    ]
                }
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                for table_id, invoice_numbers in reimbursement_tables.items():
                    for invoice_number in invoice_numbers:
                        cursor.execute(
                            """INSERT OR IGNORE INTO reimbursement_tables 
                               (table_id, invoice_number) 
                               VALUES (?, ?)""",
                            (table_id, invoice_number),
                        )

                        cursor.execute(
                            """SELECT * from invoices
                                        WHERE number = ?""",
                            (invoice_number,),
                        )
                        if not cursor.fetchone():
                            print(f"{table_id} : {invoice_number} can't find.")
                        else:
                            cursor.execute(
                                """UPDATE invoices 
                                    SET state = ?
                                    WHERE number = ?""",
                                (state, invoice_number),
                            )
                conn.commit()

                return True
        except sqlite3.Error as e:
            print(f"报销单更新失败: {e}")
            return False

    def output_invoices_to_upload(self, file_DIR="cache", output_DIR="output"):
        """
        :param file_DIR 存储发票文件的位置，会按照 file_DIR/{file_name}.pdf 的路径查找文件
        :param output_DIR 输出目录，会将发票文件重命名并存放至 {uploader}/{price}.pdf
        """
        ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
        output_DIR = os.path.join(ROOT_DIR, output_DIR)
        file_DIR = os.path.join(ROOT_DIR, file_DIR)
        # Check if itemfolder exists(If not, create it)
        if not os.path.isdir(output_DIR):
            os.makedirs(output_DIR)

        data = {}
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(f"SELECT * FROM invoices WHERE state = ?", (1,))
            # 处理查询结果
            for row in cursor.fetchall():
                # 将 Row 对象转为普通字典
                row_dict = dict(row)

                # 获取上传者名称
                uploader = row_dict["uploader"]

                # 初始化该上传者的数据列表
                if uploader not in data:
                    data[uploader] = []

                # 添加当前记录到对应上传者的列表
                data[uploader].append(
                    {
                        "file_name": row_dict["file_name"],
                        "total_amount": row_dict["total_amount"],
                        "upload_time": str(row_dict["upload_time"]),
                    }
                )

        for name in data:
            price_counter = defaultdict(int)
            total_amount = 0
            total_amount_2024 = 0
            total_amount_2025 = 0
            for item in data[name]:
                if item["upload_time"].startswith("2024"):
                    total_amount_2024 += float(item["total_amount"])
                elif item["upload_time"].startswith("2025"):
                    total_amount_2025 += float(item["total_amount"])
                else:
                    total_amount += float(item["total_amount"])
            user_dir = os.path.join(output_DIR, name + f"{float(total_amount):.2f}")
            user_dir_2024 = os.path.join(
                output_DIR, "2024", name + f"{float(total_amount_2024):.2f}"
            )
            user_dir_2025 = os.path.join(
                output_DIR, "2025", name + f"{float(total_amount_2025):.2f}"
            )
            os.makedirs(user_dir, exist_ok=True)
            os.makedirs(user_dir_2024, exist_ok=True)
            os.makedirs(user_dir_2025, exist_ok=True)
            for item in data[name]:
                # 格式化价格
                formatted_price = f"{float(item['total_amount']):.2f}"

                # 生成基础文件名
                base_name = f"{formatted_price}.pdf"

                # 计算序号
                price_counter[formatted_price] += 1
                count = price_counter[formatted_price]

                # 生成最终文件名
                final_name = (
                    base_name if count == 1 else f"{formatted_price}_{count}.pdf"
                )

                # 构建路径
                src_path = os.path.join(file_DIR, f"{item['file_name']}.pdf")
                # dst_path = os.path.join(user_dir, final_name)

                if item["upload_time"].startswith("2024"):
                    dst_path = os.path.join(user_dir_2024, final_name)
                elif item["upload_time"].startswith("2025"):
                    dst_path = os.path.join(user_dir_2025, final_name)
                else:
                    dst_path = os.path.join(user_dir, final_name)

                # 复制文件
                try:
                    shutil.copy2(src_path, dst_path)
                    print(f"已复制: {src_path} -> {dst_path}")
                except FileNotFoundError:
                    print(f"文件不存在: {src_path}")
                except Exception as e:
                    print(f"复制失败: {src_path} -> {dst_path} ({str(e)})")

        return data

    def output_all_invoices(self, file_DIR="cache", output_DIR="output"):
        """
        :param file_DIR 存储发票文件的位置，会按照 file_DIR/{file_name}.pdf 的路径查找文件
        :param output_DIR 输出目录，会将发票文件重命名并存放至 {uploader}/{price}.pdf
        """
        ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
        output_DIR = os.path.join(ROOT_DIR, output_DIR)
        file_DIR = os.path.join(ROOT_DIR, file_DIR)
        # Check if itemfolder exists(If not, create it)
        if not os.path.isdir(output_DIR):
            os.makedirs(output_DIR)

        data = {}
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(f"SELECT * FROM invoices")
            # 处理查询结果
            for row in cursor.fetchall():
                # 将 Row 对象转为普通字典
                row_dict = dict(row)

                # 获取上传者名称
                uploader = row_dict["uploader"]

                # 初始化该上传者的数据列表
                if uploader not in data:
                    data[uploader] = []

                # 添加当前记录到对应上传者的列表
                data[uploader].append(
                    {
                        "file_name": row_dict["file_name"],
                        "total_amount": row_dict["total_amount"],
                        "invoice_number": row_dict["invoice_number"],
                    }
                )

        for name in data:
            price_counter = defaultdict(int)
            user_dir = os.path.join(output_DIR, name)
            os.makedirs(user_dir, exist_ok=True)
            for item in data[name]:
                # 格式化价格
                formatted_price = f"{float(item['total_amount']):.2f}"

                # 生成基础文件名
                base_name = f"{formatted_price}.pdf"

                # 计算序号
                price_counter[formatted_price] += 1
                count = price_counter[formatted_price]

                # 生成最终文件名
                final_name = (
                    base_name if count == 1 else f"{formatted_price}_{count}.pdf"
                )

                # 构建路径
                src_path = os.path.join(file_DIR, f"{item['file_name']}.pdf")
                dst_path = os.path.join(user_dir, final_name)

                # 复制文件
                try:
                    shutil.copy2(src_path, dst_path)
                    print(f"已复制: {src_path} -> {dst_path}")
                except FileNotFoundError:
                    print(f"文件不存在: {src_path}")
                except Exception as e:
                    print(f"复制失败: {src_path} -> {dst_path} ({str(e)})")

        return data

    def output_all_invoices_with_reimbursement_tables(
        self, file_DIR="cache", output_DIR="output"
    ):
        """
        :param file_DIR 存储发票文件的位置，会按照 file_DIR/{file_name}.pdf 的路径查找文件
        :param output_DIR 输出目录，会将发票文件重命名并存放至 {uploader}/{price}.pdf
        """
        ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
        output_DIR = os.path.join(ROOT_DIR, output_DIR)
        file_DIR = os.path.join(ROOT_DIR, file_DIR)
        # Check if itemfolder exists(If not, create it)
        if not os.path.isdir(output_DIR):
            os.makedirs(output_DIR)
        data = self.data
        data.sort(key=lambda x: x["reimbursement_table_id"])

        reimbursement_table_id = None
        for info in data:
            if int(info["state"]) == -1:
                continue
            if reimbursement_table_id != info["reimbursement_table_id"]:
                reimbursement_table_id = info["reimbursement_table_id"]
                file_index = 1
            user_dir = os.path.join(output_DIR, reimbursement_table_id)
            file_name = (
                f"{file_index}_{info['belonger']}_{float(info['totalAmount']):.2f}.pdf"
            )
            file_index += 1
            os.makedirs(user_dir, exist_ok=True)
            # 构建路径
            src_path = os.path.join(file_DIR, f"{info['file_name']}")
            dst_path = os.path.join(user_dir, file_name)
            # 复制文件
            try:
                shutil.copy2(src_path, dst_path)
                print(f"已复制: {src_path} -> {dst_path}")
            except FileNotFoundError:
                print(f"文件不存在: {src_path}")
            except Exception as e:
                print(f"复制失败: {src_path} -> {dst_path} ({str(e)})")

    @property
    def data(self):
        """获取数据库中的所有发票数据"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(f"SELECT * FROM invoices")
            invoices = cursor.fetchall()

            cursor.execute(f"SELECT * FROM records")
            records = cursor.fetchall()
            # 处理查询结果
            invoice_data = [dict(row) for row in invoices]
            record_data = [dict(row) for row in records]

            record_remark_data = {}
            for record in record_data:
                record_remark_data[record["record_index"]] = record["remark"]

            # (optional)检查是否有报销单记录
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?;",
                ("reimbursement_tables",),
            )
            if cursor.fetchone():
                cursor.execute(f"SELECT * FROM reimbursement_tables")
                reimbursement_tables = cursor.fetchall()
                reimbursement_tables_data = [dict(row) for row in reimbursement_tables]
                invoice_reimbursement_tables_map = {}
                for record in reimbursement_tables_data:
                    invoice_reimbursement_tables_map[record["invoice_number"]] = record[
                        "table_id"
                    ]

            data = []
            for i in invoice_data:
                data.append(
                    {
                        **i,
                        "record_mark": record_remark_data[i["record_index"]],
                        "reimbursement_table_id": invoice_reimbursement_tables_map.get(
                            i["number"], ""
                        ),
                    }
                )
            return data

    def output_to_excel(self, output_DIR="output"):
        """
        :param output_DIR 输出目录，会将数据库信息输出到 {output_DIR}/{self.db_name}.xlsx
        """
        ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
        output_DIR = os.path.join(ROOT_DIR, output_DIR)
        # Check if itemfolder exists(If not, create it)
        if not os.path.isdir(output_DIR):
            os.makedirs(output_DIR, exist_ok=True)

        # 将数据转换为 DataFrame
        df = pd.DataFrame(self.data)

        # 保存为 Excel 文件
        excel_path = os.path.join(output_DIR, "invoices.xlsx")
        df.to_excel(excel_path, index=False)
        print(f"已保存 Excel 文件: {excel_path}")


class LarkInvoiceBitableRecord:
    def __init__(self):
        self.record_id = None
        self.record_index = None
        self.creator = None
        self.belonger = None
        self.create_time = None
        self.purpose = None
        self.concrete_purpose = None
        self.remark = None
        self.invoice_file_info_list = []  # List of dicts containing invoice file info
        """ e.g.
        {
            "url": "https://open.feishu.cn/open-apis/drive/v1/medias/Anb2bhomloSX2vxV6r8cmlr1nOf/download",
            "file_type": "application/pdf",
            "file_token": "Anb2bhomloSX2vxV6r8cmlr1nOf",
            "size": 127832
        }
        """
        self.price = None


class LarkInvoicesBitable:
    def __init__(self, app_id, app_secret, token, table_id, db_path="invoices.db"):
        """
        :param app_id   飞书应用的app_id
        :param app_secret   飞书应用的app_secret
        :param token 多为表格的app_token
        :param table_id 多维表格的table_id
        token, table_id参数的获取请参考： https://open.feishu.cn/document/server-docs/docs/bitable-v1/bitable-overview#-752212c
        """
        self.api = APIContainer(app_id, app_secret)
        self.db_path = db_path
        self.token = token
        self.table_id = table_id

    def fetch_records(self):
        def _get_concrete_purpose(data):
            """获取具体用途"""
            pattern = re.compile(r"(^具体用途.*)")
            for key in data.keys():
                match = pattern.match(key)
                if match:
                    result = data[key]
                    if type(result) == str:
                        return result
                    elif type(result) == list:  # TODO 其他异常情况判断
                        return result[0]["text"]
            return "Unkown"

        response = {"data": {"has_more": True, "page_token": None, "items": []}}
        table_items = []
        while response["data"]["has_more"]:
            response = self.api.bitable.search(
                self.token, self.table_id, page_token=response["data"]["page_token"]
            )
            table_items.extend(response["data"]["items"])

        result = []
        for item in table_items:
            fields = item["fields"]
            record = LarkInvoiceBitableRecord()
            record.record_id = item["record_id"]
            record.record_index = fields["序列号"]
            record.creator = fields["创建人"][0]["name"]
            record.belonger = fields["收款人"][0]["name"]
            record.create_time = fields["填写时间"]
            record.purpose = fields["用途"]
            record.concrete_purpose = _get_concrete_purpose(fields)
            record.remark = fields["备注"][0]["text"] if fields.get("备注") else ""
            record.invoice_file_info_list = []

            if fields["是否有发票？"] == "有":
                bill_list = fields["发票"]
                for bill in bill_list:
                    record.invoice_file_info_list.append(
                        {
                            "url": bill["url"],
                            "file_type": bill["type"],
                            "file_token": bill["file_token"],
                            "size": bill["size"],
                        }
                    )
            else:
                record.price = fields["金额"]
            result.append(record)
        return result

    def batch_process_invoices(
        self, records: List[LarkInvoiceBitableRecord], cache_dir="cache"
    ):
        """
        批量处理入口函数
        :param records: 输入记录列表
        """
        os.makedirs(cache_dir, exist_ok=True)
        status = {
            "records_total": len(records),
            "record_success": 0,
            "record_error": 0,
            "invoices_total": 0,
            "invoices_success": 0,
            "invoices_error": 0,
            "total_amount": 0.00,
            "info": [],
            "start_time": str(datetime.now()),
        }

        invoice_db = InvoiceDB(self.db_path)
        for record in records:
            result = {
                "id": record.record_id,
                "index": record.record_index,
                "status": "success",
                "total": len(record.invoice_file_info_list),
                "success": 0,
                "error": 0,
                "data": [],
                "error_info": [],
                "total_amount": 0.00,
            }
            # 更新数据库内记录信息
            result["db_state"] = invoice_db.update_record_info(
                record.record_id, record.record_index, record.remark, record.creator
            )
            for index, invoice_file_info in enumerate(record.invoice_file_info_list):
                try:
                    # 步骤1：下载文件(先检查是否缓存)
                    file_path = os.path.join(
                        cache_dir, f"{invoice_file_info["file_token"]}.pdf"
                    )
                    if not os.path.exists(file_path):
                        response = self.api.cloud.download_medias(
                            invoice_file_info["file_token"]
                        )
                        with open(file_path, "wb") as f:
                            f.write(response.content)

                    # 步骤2：解析发票(先检查数据库内是否有记录)
                    try:
                        invoice = Invoice(
                            file_path,
                            parse_mode="Database",
                            params={
                                "DB_PATH": self.db_path,
                            },
                        )
                    except ValueError:
                        invoice = Invoice(
                            file_path,
                            parse_mode="BaiduApi",
                            params={
                                "API_KEY": API_KEY,
                                "SECRET_KEY": SECRET_KEY,
                            },
                        )

                        # 更新数据库
                        invoice_db.add_invoice(
                            invoice,
                            record_index=record.record_index,
                            file_index_in_record=index,
                            belonger=record.belonger,
                        )

                    # 步骤3：(optional)记录解析结果
                    result["success"] += 1
                    result["data"].append(
                        {
                            "index": index + 1,
                            "file_name": invoice.file_name,
                            "invoice_info": invoice.data,
                        }
                    )
                    result["total_amount"] += invoice.totalAmount

                except Exception as e:
                    result["status"] = "error"
                    result["error"] += 1
                    result["error_info"].append(
                        {
                            "index": index + 1,
                            "file_name": invoice_file_info["file_token"],
                            "error_message": str(e),
                        }
                    )

            status["info"].append(result)
            status["total_amount"] += result["total_amount"]
            status["invoices_total"] += result["total"]
            status["invoices_success"] += result["success"]
            status["invoices_error"] += result["error"]

            if not result["error"]:
                status["record_success"] += 1
            else:
                status["record_error"] += 1

        status["end_time"] = str(datetime.now())
        return status

    def update_price(self, records, result):
        """根据batch_process_invoices处理后的返回信息更新表格内金额栏"""
        update_records = []
        for info in result["info"]:
            record = next(
                record for record in records if record.record_id == info["id"]
            )
            record_total_amount = record.price
            update_total_amount = info["total_amount"]
            if update_total_amount != record_total_amount:
                update_records.append(
                    {
                        "record_id": record.record_id,
                        "fields": {
                            "金额": float(update_total_amount),
                        },
                    }
                )
        self.api.bitable.batch_update_records(
            self.token,
            self.table_id,
            records=update_records,
            ignore_consistency_check=False,
        )


def vertify_invoice_title(invoice: Invoice):
    if (
        invoice.buyerName != "南京理工大学"
        or invoice.buyerTaxID != "12100000466007597C"
    ):
        return {"status": "error", "message": "发票抬头不匹配"}
    elif "客运服务" in invoice.items_brief:
        return {"status": "error", "message": "客运服务费不允许报销"}
    elif invoice.number in history_invoices:
        return {"status": "error", "message": "系统中已经报过这张票了"}
    else:
        return {"status": "success"}


def main():
    lark_invoice_bitable = LarkInvoicesBitable(
        "cli_a65443261b39d00d",
        "beUisVYWNEU8s0WCgdgUCh2yRJi7ut0i",
        "GOvAbKyv3aOot1sy9emcTmpdn6d",
        "tblgP75665t0WrOQ",
        "./bak/invoice.db",
    )
    records = lark_invoice_bitable.fetch_records()
    records_output = {
        "num": len(records),
        "records": [record.__dict__ for record in records],
    }
    with open("./bak/records.json", "w", encoding="utf-8") as f:
        f.write(json.dumps(records_output, ensure_ascii=False, indent=4))
    result = lark_invoice_bitable.batch_process_invoices(
        records, cache_dir="./bak/cache"
    )
    with open("./bak/result.json", "w", encoding="utf-8") as f:
        f.write(json.dumps(result, ensure_ascii=False, indent=4))

    lark_invoice_bitable.update_price(records, result)
    # # 解析命令行参数
    # parser = argparse.ArgumentParser(description="Extract PDF text with positions")
    # group = parser.add_mutually_exclusive_group(required=True)
    # group.add_argument("-f", "--file", help="Input PDF file path")
    # group.add_argument("-d", "--dir", help="Input directory path")
    # parser.add_argument(
    #     "-r",
    #     "--recursive",
    #     action="store_true",
    #     help="Recursively search subdirectories (requires --dir)",
    # )
    # parser.add_argument(
    #     "-o",
    #     "--output",
    #     default="result",
    #     required=True,
    #     help="Output directory path (default: 'result')",
    # )
    # args = parser.parse_args()

    # # 验证参数逻辑
    # if args.recursive and not args.dir:
    #     parser.error("--recursive 必须与 --dir 同时使用")

    # # 准备输出目录
    # output_dir = Path(args.output)
    # output_dir.mkdir(parents=True, exist_ok=True)

    # pdf_files = list()
    # input_dir = Path()
    # # 处理单个文件模式
    # if args.file:
    #     pdf_path = Path(args.file)
    #     if not pdf_path.is_file():
    #         print(f"错误：输入文件 {args.file} 不存在")
    #         return
    #     pdf_files.append(pdf_path)

    # # 处理目录模式
    # else:
    #     input_dir = Path(args.dir)
    #     if not input_dir.is_dir():
    #         print(f"错误：输入目录 {args.dir} 不存在")
    #         return

    #     # 收集所有PDF文件路径
    #     if args.recursive:
    #         pdf_files = list(input_dir.rglob("*.pdf"))
    #     else:
    #         pdf_files = list(input_dir.glob("*.pdf"))

    #     if not pdf_files:
    #         print(f"错误：目录 {args.dir} 中未找到PDF文件")
    #         return

    # # 处理每个PDF文件
    # invoice_db = InvoiceDB("baiduApi.db")
    # params = {}
    # for pdf_path in pdf_files:

    #     invoice = Invoice(
    #         pdf_path,
    #         params=params,
    #     )
    #     invoice_db.add_invoice(invoice)


if __name__ == "__main__":
    main()
