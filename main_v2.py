# --- load environment variables from .env file before importing anything using them
from dotenv import load_dotenv

load_dotenv()

from core import *

import lark_oapi as lark
from lark_oapi.api.bitable.v1 import *
from sqlite_utils import Database

db = Database("chickens.db")
APP_TOKEN = "GOvAbKyv3aOot1sy9emcTmpdn6d"
TABLE_ID = "tblgP75665t0WrOQ"

KEY_WORDS = {
    "invoice_file": "发票",
    "estimated_amount": "金额",
    "actual_amount": "实际金额",
    "record_primary_key": "序列号",
}

# TODO: 自定义判断，满足条件的记录才会被处理
# 不满足条件的记录会被忽略

# TODO：新建一个表，存储发票和记录的对应关系
# TODO: 修改当前记录表的主键，更改成一个处在多个文档间也不会重合的值
# TODO: 测试百度API的识别效果，是否能满足需求（不止识别发票）

def main():
    # 创建client
    client = lark.Client.builder() \
        .app_id(lark.APP_ID) \
        .app_secret(lark.APP_SECRET) \
        .log_level(lark.LogLevel.DEBUG) \
        .build()

    page_token = ""
    while True:
        # 构造请求对象
        request: SearchAppTableRecordRequest = SearchAppTableRecordRequest.builder() \
            .app_token(APP_TOKEN) \
            .table_id(TABLE_ID) \
            .page_token(page_token) \
            .page_size(100) \
            .request_body(SearchAppTableRecordRequestBody.builder()
                      .build()) \
            .build()

        # 发起请求
        response: SearchAppTableRecordResponse = client.bitable.v1.app_table_record.search(request)

        # 处理失败返回
        if not response.success():
            lark.logger.error(
                f"client.bitable.v1.app_table_record.search failed, code: {response.code}, msg: {response.msg}, log_id: {response.get_log_id()}")
            return

        # 处理业务结果
        records = [record.fields for record in response.data.items]
        lark.logger.info(f"Fetched {len(records)} records from the table.")
        lark.logger.info(f"{records[0]}")
        db["records"].insert_all(records, pk=KEY_WORDS["record_primary_key"], replace=True, alter=True)
        
        if not response.data.has_more:
            break
        page_token = response.data.page_token

if __name__ == "__main__":
    main()
