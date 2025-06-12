from core.invoice import Invoice

KEY_WORDS = {
    "record_invoice_file": "发票",
    "record_estimated_amount": "金额",
    "record_actual_amount": "实际金额",
    "record_error": "错误信息",
}


def vertify_invoice(invoice: Invoice):
    if invoice.buyerName != "南京理工大学":
        return {"status": "error", "message": "发票抬头不匹配"}
    elif "客运服务" in invoice.items_brief:
        return {"status": "error", "message": "客运服务费不允许报销"}
    else:
        return {"status": "success"}


def update_record():
    pass
