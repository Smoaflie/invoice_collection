from InvoiceParserWithBaiduApi import Invoice, InvoiceItem, InvoiceDB
import json


db = InvoiceDB("./bak/invoice.db")
with open("bak\报销单.json", "r", encoding="utf-8") as f:
    data = json.load(f)

db.update_reimbursement_tables(data)
# db.output_to_excel("./bak")
db.output_all_invoices_with_reimbursement_tables("./bak/cache", "./bak/output")
print(len(data))
