from core.invoice import Invoice

def vertify_invoice(invoice: Invoice):
    """
    自定义发票校验规则

    Returns:
        dict: 
        {
            "status": ["success","error],
            "message": str        
        }
    """
    if invoice.buyerName != "南京理工大学":
        if invoice.type == '电子发票（铁路电子客票）':
            return {"status": "error", "message": "需等待管理员确认动车发票的抬头是否有要求"}
        else:
            return {"status": "error", "message": "发票抬头不匹配"}
    elif "客运服务" in invoice.items_brief:
        return {"status": "error", "message": "客运服务费不允许报销"}
    else:
        return {"status": "success"}

