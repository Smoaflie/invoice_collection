import sqlite3
import json
from datetime import datetime
import pdfplumber
import os


class InvoiceSystem:
    def __init__(self, db_path):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            # 发票主表
            conn.execute(
                """CREATE TABLE IF NOT EXISTS invoices
                         (id INTEGER PRIMARY KEY,
                         unique_code TEXT UNIQUE,
                         total_amount REAL,
                         uploader TEXT,
                         upload_time DATETIME)"""
            )

            # 商品明细表
            conn.execute(
                """CREATE TABLE IF NOT EXISTS items
                         (id INTEGER PRIMARY KEY,
                         invoice_id INTEGER,
                         product_name TEXT,
                         quantity REAL,
                         unit_price REAL,
                         amount REAL,
                         FOREIGN KEY(invoice_id) REFERENCES invoices(id))"""
            )

            # 标签系统
            conn.execute(
                """CREATE TABLE IF NOT EXISTS tags
                         (id INTEGER PRIMARY KEY,
                         name TEXT UNIQUE)"""
            )

            conn.execute(
                """CREATE TABLE IF NOT EXISTS invoice_tags
                         (invoice_id INTEGER,
                         tag_id INTEGER,
                         PRIMARY KEY (invoice_id, tag_id),
                         FOREIGN KEY(invoice_id) REFERENCES invoices(id),
                         FOREIGN KEY(tag_id) REFERENCES tags(id))"""
            )
            conn.commit()

    def process_invoice(self, image_path, uploader, tags=[]):
        """核心处理方法"""
        try:
            # Step 1: 调用OCR识别
            invoice_data = self._read_invoice(image_path)

            # Step 2: 数据库事务开始
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                # Step 3: 检查重复
                cursor.execute(
                    "SELECT id FROM invoices WHERE unique_code=?",
                    (invoice_data["unique_code"],),
                )
                existing = cursor.fetchone()

                if existing:
                    is_new = False
                    invoice_id = existing["id"]
                else:
                    # Step 4: 插入新发票
                    cursor.execute(
                        """INSERT INTO invoices 
                                   (unique_code, total_amount, uploader, upload_time)
                                   VALUES (?, ?, ?, ?)""",
                        (
                            invoice_data["unique_code"],
                            invoice_data["total_amount"],
                            uploader,
                            datetime.now(),
                        ),
                    )
                    invoice_id = cursor.lastrowid
                    is_new = True

                # Step 5: 插入商品明细
                for item in invoice_data["items"]:
                    cursor.execute(
                        """INSERT INTO items 
                                   (invoice_id, product_name, quantity, unit_price, amount)
                                   VALUES (?, ?, ?, ?, ?)""",
                        (
                            invoice_id,
                            item["product_name"],
                            item["quantity"],
                            item["unit_price"],
                            item["amount"],
                        ),
                    )

                # Step 6: 处理标签
                self._process_tags(cursor, invoice_id, tags)

                # Step 7: 更新总金额
                cursor.execute(
                    """UPDATE invoices SET total_amount = 
                               (SELECT SUM(amount) FROM items WHERE invoice_id=?)
                               WHERE id=?""",
                    (invoice_id, invoice_id),
                )

                conn.commit()
                return {"status": "success", "is_new": is_new}

        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _process_tags(self, cursor, invoice_id, tags):
        """标签处理子系统"""
        # 删除旧标签关联
        cursor.execute("DELETE FROM invoice_tags WHERE invoice_id=?", (invoice_id,))

        # 插入新标签
        for tag_name in tags:
            cursor.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (tag_name,))
            cursor.execute("SELECT id FROM tags WHERE name=?", (tag_name,))
            tag_id = cursor.fetchone()[0]
            cursor.execute(
                "INSERT OR IGNORE INTO invoice_tags VALUES (?,?)", (invoice_id, tag_id)
            )

    def _read_invoice(self, file_path):
        """读取发票内容"""
        extension = os.path.splitext(file_path)[1]
        if extension == ".pdf":
            text = []
            with pdfplumber.open(file_path) as pdf:
                text.append(pdf[0].extract_text().split("\n"))

        # 示例数据模板
        # sample_data = {
        #     "unique_code": "INV20230921001",
        #     "total_amount": 568.0,
        #     "itemass": [
        #         {
        #             "product_name": "办公椅",
        #             "quantity": 2,
        #             "unit_price": 200,
        #             "amount": 400,
        #         },
        #         {
        #             "product_name": "打印纸",
        #             "quantity": 10,
        #             "unit_price": 16.8,
        #             "amount": 168,
        #         },
        #     ],
        # }
        return sample_data

    def search_by_tag(self, tag_name):
        """按标签查询"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """SELECT i.* FROM invoices i
                           JOIN invoice_tags it ON i.id = it.invoice_id
                           JOIN tags t ON t.id = it.tag_id
                           WHERE t.name=?""",
                (tag_name,),
            )
            return [dict(row) for row in cursor.fetchall()]


# 使用示例
if __name__ == "__main__":
    system = InvoiceSystem("invoices.db")

    # 模拟批量处理
    test_cases = [
        {"image": "sample1.jpg", "uploader": "张三", "tags": ["办公用品", "2023Q3"]},
        {"image": "sample2.jpg", "uploader": "李四", "tags": ["差旅费用"]},
        {"image": "duplicate.jpg", "uploader": "王五"},  # 重复发票测试
    ]

    stats = {"total": 0, "added": 0, "duplicates": 0, "errors": []}

    for idx, case in enumerate(test_cases):
        result = system.process_invoice(
            case["image"], case["uploader"], case.get("tags", [])
        )

        if result["status"] == "success":
            stats["total"] += 1
            if result["is_new"]:
                stats["added"] += 1
            else:
                stats["duplicates"] += 1
        else:
            stats["errors"].append(
                {"index": idx, "error": result["message"], "case": case}
            )

    # 打印统计结果
    print(
        f"处理完成：新增 {stats['added']} 张，重复 {stats['duplicates']} 张，错误 {len(stats['errors'])} 条"
    )

    # 保存错误日志
    with open("error_log.json", "w") as f:
        json.dump(stats["errors"], f, indent=2, ensure_ascii=False)

    # 标签查询示例
    print("\n办公用品标签下的发票：")
    for inv in system.search_by_tag("办公用品"):
        print(f"{inv['unique_code']} - ¥{inv['total_amount']}")
