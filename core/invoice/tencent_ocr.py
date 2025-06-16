import os
import requests
import urllib.parse
import re
import hmac
import time
import hashlib
import json
from datetime import datetime, timezone
from .base import *
from ..log import logger

TENCENT_SecretId = os.getenv("TENCENT_SecretId")
TENCENT_SecretKey = os.getenv("TENCENT_SecretKey")


class TencentOCR(object):
    @staticmethod
    def is_valid():
        """
        检查腾讯API的SecretId和SecretKey是否存在
        暂时没找到验证值是否有效的办法
        """
        if not TENCENT_SecretId or not TENCENT_SecretKey:
            return False
        return True

    @staticmethod
    def post(host: str, header: dict, data: dict | str):
        """
        向腾讯API发送POST请求

        使用签名办法 v3
        doc: https://cloud.tencent.com/document/api/866/33519
        """
        def cal_HashedRequestPayload(data):
            if isinstance(data, dict):
                payload = json.dumps(data, separators=(',', ':'))
                hashed = hashlib.sha256(payload.encode('utf-8')).hexdigest()
            elif isinstance(data, str):
                hashed = hashlib.sha256(data.encode('utf-8')).hexdigest()
            return hashed
        def hmac_sha256(key: bytes, msg: str) -> bytes:
            return hmac.new(key, msg.encode('utf-8'), hashlib.sha256).digest()
        
        timestamp = int(time.time())  # 当前 UNIX 时间戳
        date = datetime.utcfromtimestamp(timestamp).strftime("%Y-%m-%d") # 格式化为 YYYY-MM-DD 字符串
        service = host.split('.')[0]
        # 1. 拼接规范请求串
        if True:
            HTTPRequestMethod = "POST"
            CanonicalURI = '/'
            CanonicalQueryString = ""
            CanonicalHeaders = f"content-type:{header['Content-Type']}\nhost:{header['Host']}\nx-tc-action:{header['X-TC-Action'].lower()}\n"
            SignedHeaders = "content-type;host;x-tc-action"
            HashedRequestPayload = cal_HashedRequestPayload(data)
            
            CanonicalRequest =(HTTPRequestMethod + '\n' +
                                CanonicalURI + '\n' +
                                CanonicalQueryString + '\n' +
                                CanonicalHeaders + '\n' +
                                SignedHeaders + '\n' +
                                HashedRequestPayload)
            logger.debug("\nCanonicalRequest: \n" + CanonicalRequest)
        # 2. 拼接待签名字符串
        if True:
            Algorithm = "TC3-HMAC-SHA256"
            RequestTimestamp = str(timestamp)
            CredentialScope = f"{date}/{service}/tc3_request"
            HashedCanonicalRequest = hashlib.sha256(CanonicalRequest.encode("utf-8")).hexdigest()
            StringToSign =(Algorithm + "\n" +
                            RequestTimestamp + "\n" +
                            CredentialScope + "\n" +
                            HashedCanonicalRequest)
            logger.debug("\nStringToSign: \n" + StringToSign)

        # 3. 计算签名
        if True:
            SecretDate = hmac_sha256(("TC3" + TENCENT_SecretKey).encode('utf-8'), date)
            SecretService = hmac_sha256(SecretDate, service)
            SecretSigning = hmac_sha256(SecretService, "tc3_request")

            Signature = hmac.new(SecretSigning, StringToSign.encode('utf-8'), hashlib.sha256).hexdigest()
            logger.debug("\nSignature: \n" + Signature)

        # 4. 拼接 Authorization
        if True:
            Authorization =(Algorithm + ' ' +
                            'Credential=' + TENCENT_SecretId + '/' + CredentialScope + ', ' +
                            'SignedHeaders=' + SignedHeaders + ', ' +
                            'Signature=' + Signature)
            logger.debug("\nAuthorization: \n" + Authorization)

        header['X-TC-Timestamp'] = str(timestamp)
        header['Authorization'] = Authorization
        
        logger.debug(f"\n{header}")
        response = requests.post(f"https://{host}", headers=header, data=json.dumps(data, separators=(',', ':')))
        return response

    @staticmethod
    def parse_vat_invoice(results, invoice_type):
        invoice_type_item_param_map = {
            "VatElectronicInvoiceBlockchain": "VatInvoiceItemInfos",
            "VatElectronicInvoiceFull": "VatElectronicItems",
            "default": "VatElectronicItems",
        }
        invoice_item_param = ''
        for key,value in invoice_type_item_param_map.items():
            if key == invoice_type or key == 'default':
                invoice_item_param = value

        invoice = Invoice()

        params_dict = {
            'type': 'SubTypeDescription',
            'number': 'Number',
            'date': 'Date',
            'buyerName': 'Buyer',
            'sellerName': 'Seller',
            'buyerTaxID': 'BuyerTaxID',
            'sellerTaxID': 'SellerTaxID',
            'amount': 'PretaxAmount',
            'taxAmount': 'Tax',
            'totalAmount': 'Total',
            'province': 'Province',
            'city': 'City',
            'code': 'Code',
            'password': 'Ciphertext',
            'verificationCode': 'CheckCode',
            'sellerAddress': 'SellerAddrTel',
            'sellerBankAccount': 'SellerBankAccount',
            'buyerAddress': 'PurchaserAddress',
            'buyerBankAccount': 'PurchaserBank',
            'payee': 'Issuer',
            'remark': 'Remark',
            'reviewer': 'Reviewer',
            'noteDrawer': 'NoteDrawer',
            'crc': 'CheckCode',
        }
        invoice_info = results[0]['SingleInvoiceInfos'][invoice_type]
        for field, key in params_dict.items():
            invoice.set_field(field, invoice_info.get(key, None))
        
        for result in results:
            invoice_info = result['SingleInvoiceInfos'][invoice_type]
            invoice_items = invoice_info.get(invoice_item_param,[])
            for item in invoice_items:
                invoice.add_item(InvoiceItem({
                    "name": item["Name"] + " " + item["Specification"],
                    "type": item["Name"],
                    "unit": item["Unit"],
                    "num": item["Quantity"],
                    "unit_price": item["Price"],
                    "amount": item["Total"],
                    "tax_rate": item["TaxRate"],
                    "tax": item["Tax"],
                }))
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
    def parse_train_ticket(results, invoice_type):
        invoice = Invoice()

        invoice_info = results[0]['SingleInvoiceInfos'][invoice_type]
        invoice.set_field('type', "电子发票（铁路电子客票）")
        invoice.set_field('number', invoice_info['Number'])
        invoice.set_field('date', invoice_info['Date'])
        invoice.set_field('buyerName',
                          invoice_info['Buyer'])
        invoice.set_field('buyerTaxID',
                          invoice_info['BuyerTaxID'])
        invoice.set_field('totalAmount', invoice_info['Fare'])

        remark = (f"电子客票号: {invoice_info['ElectronicTicketNum']}, "
                  f"始发站: {invoice_info['StationGetOn']}, "
                  f"终点站: {invoice_info['StationGetOff']}, "
                  f"乘车人: {invoice_info['UserName']}, "
                  f"车次: {invoice_info['SeatNumber']}, "
                  f"发车时间: {invoice_info['DateGetOn']}, "
                  f"座次: {invoice_info['SeatNumber']}, "
                  f"座位类型: {invoice_info['Seat']}, ")
        invoice.set_field('remark', remark)

        return invoice

    @staticmethod
    def multiple_invoice_recognition(file_type: str, base64_data) -> Invoice:
        """
        通用票据识别（高级版） 免费接口1000次/月

        doc: https://cloud.tencent.com/document/product/866/90802
        """
        if 'pdf' in file_type:
            base64_data_with_type = 'data:application/pdf;base64,' + base64_data
        elif 'image' in file_type:
            base64_data_with_type = 'data:image/jpeg;base64,' + base64_data

        host = "ocr.tencentcloudapi.com"
        headers = {
            "Content-Type": "application/json",
            "Host": host,
            "X-TC-Action": "RecognizeGeneralInvoice",
            "X-TC-Version": "2018-11-19",
            "X-TC-Language": "zh-CN",
        }
        data = {
            "ImageBase64": base64_data_with_type,
            "EnableMultiplePage": True,
        }
        results = []
    
        response = TencentOCR.post(host,headers,data)
        page = response.json().get('Response')
        
        results = page["MixedInvoiceItems"]

        invoice_type = results[0].get('SubType')
        # 非动车发票一律认为是增值税发票
        if invoice_type == "ElectronicTrainTicketFull":
            return TencentOCR.parse_train_ticket(results, invoice_type)
        else:
            return TencentOCR.parse_vat_invoice(results, invoice_type)
