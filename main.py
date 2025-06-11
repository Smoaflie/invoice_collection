import os
import requests
from datetime import datetime
from typing import List
from api import *
import re
from InvoiceParser import InvoiceParser
import json

_fs = APIContainer("cli_a65443261b39d00d", "beUisVYWNEU8s0WCgdgUCh2yRJi7ut0i")
token = "GOvAbKyv3aOot1sy9emcTmpdn6d"
table_id = "tblgP75665t0WrOQ"
# 配置参数
CACHE_DIR = "./cache"
ERROR_LOG = "processing_errors.log"
HEADERS = headers = {
    "Authorization": _fs.tenant_access_token,
    "Content-Type": "application/json; charset=utf-8",
}  # 自定义包头


def fetch_records(token, table_id):
    """fetch records from feishu table"""

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
        response = _fs.cloud.app_table_search(
            token, table_id, page_token=response["data"]["page_token"]
        )
        table_items.extend(response["data"]["items"])

    result = []
    for item in table_items:
        fields = item["fields"]
        info = {
            "index": fields["序列号"],
            "creator_name": fields["创建人"][0]["name"],
            "create_time": fields["填写时间"],
            "purpose": fields["用途"],
            "concrete_purpose": _get_concrete_purpose(fields),
            "remark": fields["备注"][0]["text"] if fields.get("备注") else "",
            "invoices_list": [],
            "record_id": item["record_id"],
        }
        if fields["是否有发票？"] == "有":
            bill_list = fields["发票"]
            for bill in bill_list:
                info["invoices_list"].append(
                    {
                        "url": bill["url"],
                        "file_type": bill["type"],
                        "file_token": bill["file_token"],
                        "size": bill["size"],
                    }
                )
        else:
            info["price"] = fields["金额"]
        result.append(info)
    return result


def update_price(result):
    """更新表格内金额栏"""
    records = []
    for item in result["info"]:
        if item.get("total_amount"):
            records.append(
                {
                    "record_id": item["record_id"],
                    "fields": {
                        "金额": float(item["total_amount"]),
                    },
                }
            )
    _fs.cloud.app_table_record_batch_update(
        token, table_id, records=records, ignore_consistency_check=False
    )


def vertify_duplicates(result):
    invoices = []
    sum = 0
    duplicate = 0
    for item in result["info"]:
        for i in item.get("result").get("data"):
            sum += 1
            invoice_code = i["invoice_info"]["basic_info"]["invoice_code"]

            p = False
            if any(invoice_code == iv["code"] for iv in invoices):
                p = True
                duplicate += 1
            invoices.append(
                {
                    "code": invoice_code,
                    "unique_index": f'{item["index"]}_{i["index"]}',
                    "same": p,
                }
            )
    return invoices, duplicate


def batch_process(entries: List[dict]):
    """
    批量处理入口函数
    :param entries: 输入参数列表
    """

    def ensure_directories():
        """确保必要的目录存在"""
        os.makedirs(CACHE_DIR, exist_ok=True)

    def download_file(url: str, file_token: str) -> str:
        """
        下载文件到缓存目录
        :param url: 文件下载地址
        :param file_token: 文件唯一标识
        :return: 本地文件路径
        """
        try:
            response = requests.get(url, headers=HEADERS, stream=True, timeout=30)
            response.raise_for_status()

            cache_path = os.path.join(CACHE_DIR, f"{file_token}.pdf")
            with open(cache_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            return cache_path
        except Exception as e:
            raise RuntimeError(f"文件下载失败: {str(e)}")

    def analyze_invoice(file_path: str) -> str:
        parser = InvoiceParser(file_path)
        return parser.parse()  # 返回解析结果

    def process_invoice_entry(entry: dict) -> dict:
        """
        处理发票条目
        :param entry: 输入参数信息
        :return: 处理结果字典
        """
        result = {
            "status": "success",
            "total": len(entry["invoices_list"]),
            "success": 0,
            "error": [],
            "data": [],
        }

        for index, invoice in enumerate(entry["invoices_list"]):
            try:
                # 步骤1：下载文件(如果未缓存)
                local_path = os.path.join(CACHE_DIR, f"{invoice["file_token"]}.pdf")
                if not os.path.exists(local_path):
                    download_file(invoice["url"], invoice["file_token"])

                # 步骤2：解析发票
                invoice_info = analyze_invoice(local_path)

                # 步骤3：保存解析结果
                result["data"].append(
                    {
                        "index": index + 1,
                        "file_name": invoice["file_token"],
                        "invoice_info": invoice_info,
                    }
                )
                result["success"] += 1

            except Exception as e:
                result["error"].append(
                    {
                        "index": index + 1,
                        "file_name": invoice["file_token"],
                        "error": str(e),
                    }
                )

        return result

    ensure_directories()
    stats = {
        "total": len(entries),
        "success": 0,
        "errors": 0,
        "info": [],
        "start_time": datetime.now(),
    }

    for idx, entry in enumerate(entries):
        info = {
            "index": entry["index"],
            "creator_name": entry["creator_name"],
            "create_time": entry["create_time"],
            "purpose": entry["purpose"],
            "concrete_purpose": entry["concrete_purpose"],
            "remark": entry["remark"],
            "record_id": entry["record_id"],
        }
        try:
            result = process_invoice_entry(entry)

            total_amount = entry.get("price") if entry.get("price") else 0
            for data in result["data"]:
                total_amount += float(data["invoice_info"]["total_amount"])
            stats["info"].append(
                {
                    **info,
                    "total_amount": total_amount,
                    "result": result,
                }
            )
            if not result["error"]:
                stats["success"] += 1
            else:
                stats["errors"] += 1
        except Exception as e:
            stats["info"].append(
                {
                    **info,
                    "error": f"未处理的异常: {str(e)}",
                }
            )

    # 生成报告
    stats["end_time"] = datetime.now()
    stats["duration"] = str(stats["end_time"] - stats["start_time"])
    stats["end_time"] = str(stats["end_time"])
    stats["start_time"] = str(stats["start_time"])

    # 打印统计信息
    print(f"\n处理完成：")
    print(f"总计处理：{stats['total']} 条数据")
    print(f"成功处理：{stats['success']} 条")
    print(f"异常数量：{stats['errors']} 条")

    # 保存错误日志
    if stats["errors"]:
        with open(ERROR_LOG, "a") as f:
            f.write(f"\n===== 处理时间：{stats['start_time']} =====\n")
            json.dump(stats["errors"], f, indent=2, ensure_ascii=False)

    return stats


# 使用示例
if __name__ == "__main__":
    # 1 从收集表中拉取发票信息
    print("\n正在从收集表中拉取所有记录...")
    records = fetch_records(token, table_id)
    print(
        f"成功拉取{len(records)}条记录，共{sum([len(i["invoices_list"]) for i in records])}张发票"
    )

    # 2 从记录中提取发票信息
    print("\n正在从记录中提取发票信息...")
    result = batch_process(records)
    print(f"成功提取{sum([len(i["invoices_list"]) for i in records])}张发票信息")

    # 3 保存结果
    result_file_path = "result.json"
    print(f"\n将保存结果到{result_file_path}")
    with open(result_file_path, "w", encoding="gbk", errors="replace") as f:
        f.write(
            ujson.dumps(
                result, indent=4, ensure_ascii=False, escape_forward_slashes=False
            )
        )

    # 4 根据发票金额修改表格内"金额"栏
    print('\n正在根据发票金额修改飞书表格内"金额"栏...')
    update_price(result)

    # 5 去重
    print("正在检测去重项...")
    duplicates, sum = vertify_duplicates(result)
    if sum:
        print("发现重复项，数量:", sum)
        print("请检查duplicates.json文件")
        with open("duplicates.json", "w", encoding="gbk", errors="replace") as f:
            f.write(
                ujson.dumps(
                    duplicates,
                    indent=4,
                    ensure_ascii=False,
                    escape_forward_slashes=False,
                )
            )
    else:
        print("没有发现重复项")
