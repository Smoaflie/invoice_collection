import os
import sys
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

def export_invoice(invoice: Invoice, raw_file_name: str, status: str, belonger: str, output_dir: str):
    def hardlink(src, dst):
        if not os.path.exists(dst):
                os.link(src, dst)

    raw_file_path = os.path.join(output_dir, "raw", raw_file_name)
    _, ext = os.path.splitext(raw_file_name)

    # 示例1: 按{收款人-金额-发票号-file_token}命名,按标签分组导出
    file_name = f"{belonger}-{invoice.totalAmount}-{invoice.number}-{raw_file_name}" + ext
    dst_path = os.path.join(output_dir, "by_state", status)
    os.makedirs(dst_path, exist_ok=True)
    hardlink(raw_file_path, os.path.join(dst_path, file_name))

    # 示例2： 按{标签-金额-发票号-file_token}命名,按收款人分组导出
    file_name = f"{status}-{invoice.totalAmount}-{invoice.number}-{raw_file_name}" + ext
    dst_path = os.path.join(output_dir, "by_belonger", belonger)
    os.makedirs(dst_path, exist_ok=True)
    hardlink(raw_file_path, os.path.join(dst_path, file_name))

    # 示例3：按{金额-发票号}命名,用status=="0"筛选发票,按收款人分组导出
    file_name = f"{invoice.totalAmount}-{invoice.number}" + ext
    dst_path = os.path.join(output_dir, "by_filter", belonger)
    os.makedirs(dst_path, exist_ok=True)
    hardlink(raw_file_path, os.path.join(dst_path, file_name))