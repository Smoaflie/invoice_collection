# --- load environment variables from .env file before importing anything using them
from dotenv import load_dotenv

load_dotenv()
print("飞书sdk模块初始需要较长时间，请耐心等待...")

import base64
from core import *
import lark_oapi as lark
from lark_oapi.api.bitable.v1 import *
from lark_oapi.api.drive.v1 import *
from sqlite_utils import Database
from core.invoice.baidu_ocr import BaiduOCR
from tqdm import tqdm
from yaspin import yaspin
from core.invoice import Invoice
from custom_rule import vertify_invoice

APP_TOKEN = "GOvAbKyv3aOot1sy9emcTmpdn6d"
TABLE_ID = "tblgP75665t0WrOQ"
INVOICE_COLUMN_NAME = "发票"
TOTAL_AMOUNT_COLUMN_NAME = "审批后金额"
APPROVAL_REMARKS_COLUMN_NAME = "审批备注"
db = Database("invoices.db")

# TODO: 对表格的自定义规则
# TODO: 标签系统(同自定义规则)


def main():
    logger.info("Creating client for Lark API.")
    with yaspin(text="", spinner="dots") as spinner:
        if not (lark.APP_ID and lark.APP_SECRET):
            logger.error(
                "lark APP_ID and APP_SECRET must be set in environment variables."
            )
            return
        client = lark.Client.builder() \
            .app_id(lark.APP_ID) \
            .app_secret(lark.APP_SECRET) \
            .log_level(lark.LogLevel.INFO) \
            .build()
        spinner.ok("✅ Done")

    logger.info("Fetching records from the table...")
    with yaspin(text="", spinner="dots") as spinner:
        page_token = ""
        while True:
            request: SearchAppTableRecordRequest = SearchAppTableRecordRequest.builder() \
                .app_token(APP_TOKEN) \
                .table_id(TABLE_ID) \
                .page_token(page_token) \
                .page_size(100) \
                .request_body(SearchAppTableRecordRequestBody.builder()
                        .build()) \
                .build()

            response: SearchAppTableRecordResponse = client.bitable.v1.app_table_record.search(
                request)

            if not response.success():
                lark.logger.error(
                    f"client.bitable.v1.app_table_record.search failed, code: {response.code}, msg: {response.msg}, log_id: {response.get_log_id()}"
                )
                return

            records = [{
                **record.fields, "uid": f"{TABLE_ID}_{record.record_id}"
            } for record in response.data.items]
            lark.logger.debug(
                f"Fetched {len(records)} records from the table.")
            db['records'].delete_where("uid LIKE ?", (f"{TABLE_ID}_%", ))
            db["records"].insert_all(records,
                                     pk="uid",
                                     replace=True,
                                     alter=True)

            if not response.data.has_more:
                break
            page_token = response.data.page_token
        spinner.ok("✅ Done")

    logger.info("Processing invoice files...")
    logger.info("Using Baidu OCR API")
    with yaspin(text="", spinner="dots") as spinner:
        logger.info("Collecting invoices files...")
        result = db.execute(f"""
            SELECT
                records.uid,
                json_extract(value, '$.file_token') AS file_token,
                json_extract(value, '$.type') AS type
            FROM records, json_each(records.{INVOICE_COLUMN_NAME})
        """).fetchall()
        invoice_files = [{
            "record_uid": row[0],
            "file_token": row[1],
            "type": row[2],
        } for row in result]

        for invoice_file in tqdm(invoice_files, desc="Processing invoices"):
            if "invoices" in db.table_names():
                row = next(
                    db["invoices"].rows_where("file_token = ?",
                                              (invoice_file['file_token'], )),
                    None)
                if row and row.get("processed", False):
                    logger.debug(
                        f"File {invoice_file['file_token']} already processed, skipping."
                    )
                    continue

            try:
                request: DownloadMediaRequest = DownloadMediaRequest.builder() \
                    .file_token(invoice_file['file_token']) \
                    .build()

                response: DownloadMediaResponse = client.drive.v1.media.download(
                    request)

                if not response.success():
                    lark.logger.error(
                        f"client.drive.v1.media.download failed, code: {response.code}, msg: {response.msg},log_id: {response.get_log_id()}"
                    )
                    return

                # Read the file content and encode it to base64
                if response.file is not None:
                    base64_data = base64.b64encode(
                        response.file.read()).decode("utf-8")
                else:
                    invoice_file["error_message"] = "File is empty."
                    logger.warning(
                        f"File {invoice_file['file_token']} is empty or not found."
                    )

                # Prepare the data for the OCR API
                if "image" in invoice_file['type']:
                    ocr_result = BaiduOCR.vat_invoice_recognition(
                        "image", base64_data)
                elif "pdf" in invoice_file['type']:
                    ocr_result = BaiduOCR.vat_invoice_recognition(
                        "pdf", base64_data)

                if (not ocr_result.number or not ocr_result.totalAmount):
                    raise ValueError(
                        "Baidu OCR did not return required fields: 'number' or 'totalAmount'."
                    )

                # Check if the invoice number already exists in the database
                if "invoices" in db.table_names():
                    rows = list(db["invoices"].rows_where(
                        "number = ?", (ocr_result.data.get('number'), )))
                    for row in rows:
                        if not row.get("error_message"):
                            invoice_file["error_message"] = (
                                "This file has been processed in file_token: "
                                + row['file_token'])
                            logger.debug(
                                f"Invoice number {row['number']} (file {invoice_file['file_token']}) already processed, skipping."
                            )
                            break

                db['invoices'].insert(
                    ocr_result.data
                    | {
                        "file_token":
                        invoice_file['file_token'],
                        "processed":
                        True,
                        "error_message":
                        invoice_file.get("error_message"),
                        "status":
                        0 if not invoice_file.get("error_message") else -1
                    },
                    pk="file_token",
                    replace=True,
                    alter=True)
                logger.debug(
                    f"Processed file {invoice_file['file_token']} successfully."
                )
            except Exception as e:
                invoice_file[
                    "error_message"] = f"This file cannot be processed: {str(e)}"
                logger.error(
                    f"Error processing file {invoice_file['file_token']}: {str(e)}"
                )
                db['invoices'].insert(
                    {
                        "file_token": invoice_file['file_token'],
                        "processed": False,
                        "error_message": invoice_file.get("error_message"),
                        "status": -1
                    },
                    pk="file_token",
                    replace=True,
                    alter=True)

        spinner.ok("✅ Done")

    logger.info("Verifying invoice data with custom rules...")
    with yaspin(text="", spinner="dots") as spinner:
        invoices_data = db["invoices"].rows_where("processed = ?", (True, ))
        for invoice_data in tqdm(invoices_data, desc="Verifying invoices"):
            try:
                invoice = Invoice(invoice_data)
                verification_result = vertify_invoice(invoice)

                if verification_result["status"] == "error":
                    logger.debug(
                        f"Verification failed for file {invoice_data['file_token']}: {verification_result['message']}"
                    )
                    db["invoices"].update(
                        invoice_data['file_token'], {
                            "error_message": verification_result["message"],
                            "status": -1
                        })
                else:
                    logger.debug(
                        f"Verification passed for file {invoice_data['file_token']}."
                    )
            except Exception as e:
                logger.error(
                    f"Error verifying file {invoice_data['file_token']}: {str(e)}"
                )

        spinner.ok("✅ Done")

    logger.info("Updating records with invoice data...")
    with yaspin(text="", spinner="dots") as spinner:
        records_to_update = []
        result = db.execute("""
                SELECT 
                    invoices.file_token,
                    invoices.totalAmount,
                    invoices.error_message
                FROM invoices
            """).fetchall()
        invoices_by_token = {
            row[0]: {
                "total_amount": row[1],
                "error_message": row[2],
            }
            for row in result
        }

        records_in_current_table = list(db["records"].rows_where(
            "uid LIKE ?", (f"{TABLE_ID}_%", )))
        for record in tqdm(records_in_current_table,
                           desc="Generating records to update."):
            result = db.execute(
                f"""
                SELECT 
                    json_extract(value, '$.file_token') AS file_token
                FROM records, json_each(records.{INVOICE_COLUMN_NAME})
                WHERE records.uid = ?
            """, (record['uid'], )).fetchall()
            invoice_files_token = [row[0] for row in result]
            error_message = ""
            total_amount = 0.0
            for index, invoice_file_token in enumerate(invoice_files_token,
                                                       start=1):
                if invoice_file_token in invoices_by_token:
                    invoice_data = invoices_by_token[invoice_file_token]
                    if invoice_data["error_message"]:
                        error_message += f"file index {{{index}}}: " + invoice_data[
                            "error_message"] + "; \n"
                    else:
                        total_amount += invoice_data["total_amount"]
            records_to_update.append({
                "record_id": record['uid'].split("_")[1],
                "fields": {
                    TOTAL_AMOUNT_COLUMN_NAME: float(total_amount),
                    APPROVAL_REMARKS_COLUMN_NAME: error_message,
                },
            })
        request: BatchUpdateAppTableRecordRequest = BatchUpdateAppTableRecordRequest.builder() \
            .app_token(APP_TOKEN) \
            .table_id(TABLE_ID) \
            .request_body(BatchUpdateAppTableRecordRequestBody.builder()
                .records([AppTableRecord(update_data)
                    for update_data in records_to_update])
                .build()) \
            .build()
        response: BatchUpdateAppTableRecordResponse = client.bitable.v1.app_table_record.batch_update(
            request)
        if not response.success():
            lark.logger.error(
                f"client.bitable.v1.app_table_record.batch_update failed, code: {response.code}, msg: {response.msg}, log_id: {response.get_log_id()}"
            )
            return
        logger.debug(f"Updating record {record['uid']} with invoice data.")
        spinner.ok("✅ Done")


if __name__ == "__main__":
    main()
