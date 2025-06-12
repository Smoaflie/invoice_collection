from typing import List


class InvoiceItem:

    def __init__(self):
        self.name = ""
        self.type = ""
        self.unit = ""
        self.num = 0
        self.unit_price = 0.0
        self.amount = 0.0
        self.tax_rate = "0.00%"
        self.tax = 0.0

    def set_name(self, name):
        self.name = name

    def set_type(self, type):
        self.type = type

    def set_unit(self, unit):
        self.unit = unit

    def set_num(self, num):
        try:
            self.num = int(num)
        except (ValueError, TypeError):
            self.num = 0

    def set_unit_price(self, unit_price):
        try:
            self.unit_price = float(unit_price)
        except (ValueError, TypeError):
            self.unit_price = 0.0

    def set_amount(self, amount):
        try:
            self.amount = float(amount)
        except (ValueError, TypeError):
            self.amount = 0.0

    def set_tax_rate(self, tax_rate):
        self.tax_rate = tax_rate

    def set_tax(self, tax):
        try:
            self.tax = float(tax)
        except (ValueError, TypeError):
            self.tax = 0.0

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

    def __init__(self, data=None):
        if data is not None:
            self._fields = data
        else:
            self._items: List[InvoiceItem] = []
            self._fields = {}

    def set_field(self, key, value):
        self._fields[key] = value

    def get_field(self, key, default=""):
        return self._fields.get(key, default)

    def get_float_field(self, key):
        try:
            return float(self._fields.get(key, 0.0))
        except (ValueError, TypeError):
            return 0.0

    @property
    def items(self):
        return [item.data for item in self._items]

    def add_item(self, item):
        if isinstance(item, InvoiceItem):
            self._items.append(item)

    @property
    def data(self):
        keys = [
            "type",
            "code",
            "number",
            "date",
            "buyerTaxID",
            "buyerName",
            "buyerAddress",
            "buyerBankAccount",
            "sellerTaxID",
            "sellerName",
            "sellerAddress",
            "sellerBankAccount",
            "items_brief",
            "items_unit",
            "item_tag",
            "payee",
            "reviewer",
            "noteDrawer",
            "verificationCode",
            "CRC",
            "remark",
            "item_num",
            "total_items_num",
        ]
        return {
            k: self.get_field(k, "")
            for k in keys
        } | {
            "items": self.items,
            "amount": self.amount,
            "taxAmount": self.taxAmount,
            "totalAmount": self.totalAmount,
        }

    @property
    def type(self):
        """发票类型"""
        return self.get_field("type", "未知发票类型")

    @property
    def code(self):
        """发票代码 - 仅 增值税电子普通发票 中存在"""
        return self.get_field("code")

    @property
    def number(self):
        """发票号码"""
        return self.get_field("number")

    @property
    def date(self):
        """开票日期"""
        return self.get_field("date")

    @property
    def sellerTaxID(self):
        """销售方识别号"""
        return self.get_field("sellerTaxID")

    @property
    def sellerName(self):
        """销售方名称"""
        return self.get_field("sellerName")

    @property
    def buyerTaxID(self):
        """购买方识别号"""
        return self.get_field("buyerTaxID")

    @property
    def buyerName(self):
        """购买方名称"""
        return self.get_field("buyerName")

    @property
    def items(self):
        """商品列表"""
        return [item.data for item in self._items]

    @property
    def amount(self):
        """金额"""
        return self.get_float_field("amount")

    @property
    def taxAmount(self):
        """税额"""
        return self.get_float_field("taxAmount")

    @property
    def totalAmount(self):
        """价税合计"""
        return self.get_float_field("totalAmount")

    @property
    def sellerAddress(self):
        """销售方地址、电话 - 仅 增值税电子普通发票 中存在"""
        return self.get_field("sellerAddress")

    @property
    def sellerBankAccount(self):
        """销售方开户行及账号 - 仅 增值税电子普通发票 中存在"""
        return self.get_field("sellerBankAccount")

    @property
    def buyerAddress(self):
        """购买方地址、电话 - 仅 增值税电子普通发票 中存在"""
        return self.get_field("buyerAddress")

    @property
    def buyerBankAccount(self):
        """购买方开户行及账号 - 仅 增值税电子普通发票 中存在"""
        return self.get_field("buyerBankAccount")

    @property
    def payee(self):
        """收款人 - 仅 增值税电子普通发票 中存在"""
        return self.get_field("payee")

    @property
    def reviewer(self):
        """复核 - 仅 增值税电子普通发票 中存在"""
        return self.get_field("reviewer")

    @property
    def noteDrawer(self):
        """开票人"""
        return self.get_field("noteDrawer")

    @property
    def verificationCode(self):
        """校验码 - 仅 增值税电子普通发票 中存在"""
        return self.get_field("verificationCode")

    @property
    def CRC(self):
        """CRC算法产生的机密信息"""
        return self.get_field("crc")

    @property
    def remark(self):
        """CRC算法产生的机密信息"""
        return self.get_field("remark")

    @property
    def item_num(self):
        """商品数量(发票上记录了多少种商品)"""
        return self.get_field("item_num")

    @property
    def total_items_num(self):
        """总商品数量(不同商品各自的数量的总和)"""
        return self.get_field("total_items_num")

    @property
    def items_brief(self):
        """商品简介 f"{第一个商品} 等" """
        return self.get_field("items_brief")

    @property
    def items_unit(self):
        """商品简介 f"{第一个商品} 等" """
        return self.get_field("items_unit")

    @property
    def item_tag(self):
        """商品标签 (取第一个商品的标签)"""
        return self.get_field("item_tag")
