import sqlite3
import json
import os
from collections import defaultdict
import shutil


class InvoiceDB:

    def __init__(self, db_path):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            # 发票主表
            conn.execute(
                """CREATE TABLE IF NOT EXISTS invoices
                         (id INTEGER PRIMARY KEY,
                         invoice_code TEXT UNIQUE,
                         file_name TEXT UNIQUE,
                         total_amount REAL,
                         uploader TEXT,
                         upload_time DATETIME,
                         record_index INTEGER,
                         file_in_record_index INTEGER,
                         state INTEGER DEFAULT 0)"""
            )

            # 分组记录
            conn.execute(
                """CREATE TABLE IF NOT EXISTS records
                         (id TEXT PRIMARY KEY,
                         record_index INTEGER,
                         remark TEXT,
                         creator_name TEXT)"""
            )

            # 商品明细表
            # conn.execute(
            #     """CREATE TABLE IF NOT EXISTS items
            #              (id INTEGER PRIMARY KEY,
            #              invoice_code INTEGER,
            #              product_name TEXT,
            #              quantity REAL,
            #              unit_price REAL,
            #              amount REAL,
            #              FOREIGN KEY(invoice_code) REFERENCES invoices(id))"""
            # )

            # 标签系统
            conn.execute(
                """CREATE TABLE IF NOT EXISTS tags
                         (id INTEGER PRIMARY KEY,
                         name TEXT UNIQUE)"""
            )

            conn.execute(
                """CREATE TABLE IF NOT EXISTS invoice_tags
                         (invoice_code TEXT,
                         tag_id INTEGER,
                         PRIMARY KEY (invoice_code, tag_id),
                         FOREIGN KEY(tag_id) REFERENCES tags(id),
                         FOREIGN KEY(invoice_code) REFERENCES invoices(invoice_code))"""
            )

            conn.execute(
                """CREATE TABLE IF NOT EXISTS record_tags
                         (record_index INTEGER,
                         tag_id INTEGER,
                         PRIMARY KEY (record_index, tag_id),
                         FOREIGN KEY(record_index) REFERENCES records(record_index),
                         FOREIGN KEY(tag_id) REFERENCES tags(id))"""
            )

            # # 支付记录
            # conn.execute(
            #     """CREATE TABLE IF NOT EXISTS payments
            #              (id INTEGER PRIMARY KEY,
            #              invoice_code INTEGER,
            #              payment_file_path TEXT,
            #              FOREIGN KEY(invoice_code) REFERENCES invoices(invoice_code))"""
            # )

            conn.commit()

    def process_invoices_data(
        self, invoice_data: dict, uploader, tags=[], record_index=0
    ):
        """
        输入发票数据，添加进数据库内

        发票数据格式示例:
        {
            "index": 1,
            "file_name": "Anb2bhomloSX2vxV6r8cmlr1nOf",
            "invoice_info": {
                "basic_info": {
                    "invoice_code": "24332000000374240000",
                    "date": "20241022"
                },
                "buyer": {},
                "seller": {},
                "items": [],
                "tag": null,
                "total_amount": "17.9"
            }
        }
        """
        try:
            invoice_info = invoice_data["invoice_info"]
            # Step 1: 建立数据库连接
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                # Step 2: 检查重复
                invoice_code = invoice_info["basic_info"]["invoice_code"]
                cursor.execute(
                    "SELECT file_name, record_index, file_in_record_index FROM invoices WHERE invoice_code=?",
                    (invoice_code,),
                )
                existing = cursor.fetchone()

                if existing:
                    is_new = False
                    if existing[0] != invoice_data["file_name"]:
                        return {
                            "status": "error",
                            "message": "Duplicate invoice code with different file name.",
                            "elder": {
                                "file_name": existing[0],
                                "index": f"{existing[1]}-{existing[2]}",
                            },
                            "new": {
                                "file_name": invoice_data["file_name"],
                                "index": f"{record_index}-{invoice_info['index']}",
                            },
                        }

                else:
                    # TODO 添加商品明细
                    # Step 3: 插入新发票
                    cursor.execute(
                        """INSERT INTO invoices 
                                (invoice_code, file_name, total_amount, uploader, upload_time, record_index, file_in_record_index)
                                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (
                            invoice_code,
                            invoice_data["file_name"],
                            invoice_info["total_amount"],
                            uploader,
                            (invoice_info["basic_info"]["date"]),
                            record_index,
                            invoice_data["index"],
                        ),
                    )
                    is_new = True

                # TODO Step 4: 插入商品明细
                # for item in invoice_data["items"]:
                #     cursor.execute(
                #         """INSERT INTO items
                #                 (invoice_id, product_name, quantity, unit_price, amount)
                #                 VALUES (?, ?, ?, ?, ?)""",
                #         (invoice_id, self._process_items(invoice_info["items"])),
                #     )

                # Step 5: 处理标签
                self._process_tags(cursor, tags, invoice_code=invoice_code)

                conn.commit()
                return {"status": "success", "is_new": is_new}

        except Exception as e:
            return {"status": "error", "message": str(e)}

    def update_record_info(
        self, record_id, record_index, remark, creator_name, tags=[]
    ):
        """更新发票对应的表单记录信息"""
        try:
            # Step 1: 建立数据库连接
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                # Step 2: 检查重复
                cursor.execute(
                    "SELECT id FROM records WHERE id=?",
                    (record_id,),
                )
                existing = cursor.fetchone()

                if existing:
                    is_new = False

                else:
                    # TODO 添加商品明细
                    # Step 3: 添加新记录信息
                    cursor.execute(
                        """INSERT INTO records 
                                (id, record_index, remark, creator_name)
                                VALUES (?, ?, ?, ?)""",
                        (record_id, record_index, remark, creator_name),
                    )
                    is_new = True

                    # Step 4: 处理标签
                    self._process_tags(cursor, tags, record_index=record_index)

                    conn.commit()
                return {"status": "success", "is_new": is_new}
        except Exception as e:
            raise
            return {"status": "error", "message": str(e)}

    def _process_items(self, items):
        """解析商品信息

        Args:
            items (dict): _description_

        Returns:
            product_name, quantity, unit_price, amount
        """
        return None, None, None, None
        pass

    def _process_tags(self, cursor, tags, invoice_code=None, record_index=None):
        """标签处理子系统"""
        if invoice_code:
            # 删除旧标签关联
            cursor.execute(
                "DELETE FROM invoice_tags WHERE invoice_code=?", (invoice_code,)
            )

            # 插入新标签
            for tag_name in tags:
                cursor.execute(
                    "INSERT OR IGNORE INTO tags (name) VALUES (?)", (tag_name,)
                )
                cursor.execute("SELECT id FROM tags WHERE name=?", (tag_name,))
                tag_id = cursor.fetchone()[0]
                cursor.execute(
                    "INSERT OR IGNORE INTO invoice_tags VALUES (?,?)",
                    (invoice_code, tag_id),
                )
        elif record_index:
            # 删除旧标签关联
            cursor.execute(
                "DELETE FROM record_tags WHERE record_index=?", (record_index,)
            )

            # 插入新标签
            for tag_name in tags:
                cursor.execute(
                    "INSERT OR IGNORE INTO tags (name) VALUES (?)", (tag_name,)
                )
                cursor.execute("SELECT id FROM tags WHERE name=?", (tag_name,))
                tag_id = cursor.fetchone()[0]
                cursor.execute(
                    "INSERT OR IGNORE INTO record_tags VALUES (?,?)",
                    (record_index, tag_id),
                )

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

    def update_invoice_state(self, invoice_code: str, new_state: int):
        """更新发票状态"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE invoices SET state = ? WHERE invoice_code = ?",
                    (int(new_state), invoice_code),
                )
                conn.commit()
                return cursor.rowcount > 0
        except sqlite3.Error as e:
            print(f"状态更新失败: {e}")
            return False

    def get_invoices_sorted(self, sort_by: str = "record_index"):
        """获取排序后的发票数据"""
        valid_sorts = ["record_index", "upload_time", "uploader", "state"]
        sort_by = sort_by if sort_by in valid_sorts else "record_index"

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(f"SELECT * FROM invoices ORDER BY {sort_by} DESC")
            return [dict(row) for row in cursor.fetchall()]

    def output_invoices_to_upload(self, file_DIR="cache", output_DIR="output"):
        """
        @param file_DIR 存储发票文件的位置，会按照 file_DIR/{file_name}.pdf 的路径查找文件
        @param output_DIR 输出目录，会将发票文件重命名并存放至 {uploader}/{price}.pdf
        """
        ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
        output_DIR = os.path.join(ROOT_DIR, output_DIR)
        file_DIR = os.path.join(ROOT_DIR, file_DIR)
        # Check if itemfolder exists(If not, create it)
        if not os.path.isdir(output_DIR):
            os.makedirs(output_DIR)

        data = {}
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(f"SELECT * FROM invoices WHERE state = ?", (1,))
            # 处理查询结果
            for row in cursor.fetchall():
                # 将 Row 对象转为普通字典
                row_dict = dict(row)

                # 获取上传者名称
                uploader = row_dict["uploader"]

                # 初始化该上传者的数据列表
                if uploader not in data:
                    data[uploader] = []

                # 添加当前记录到对应上传者的列表
                data[uploader].append(
                    {
                        "file_name": row_dict["file_name"],
                        "total_amount": row_dict["total_amount"],
                        "upload_time": str(row_dict["upload_time"]),
                    }
                )

        for name in data:
            price_counter = defaultdict(int)
            total_amount = 0
            total_amount_2024 = 0
            total_amount_2025 = 0
            for item in data[name]:
                if item["upload_time"].startswith("2024"):
                    total_amount_2024 += float(item["total_amount"])
                elif item["upload_time"].startswith("2025"):
                    total_amount_2025 += float(item["total_amount"])
                else:
                    total_amount += float(item["total_amount"])
            user_dir = os.path.join(output_DIR, name + f"{float(total_amount):.2f}")
            user_dir_2024 = os.path.join(
                output_DIR, "2024", name + f"{float(total_amount_2024):.2f}"
            )
            user_dir_2025 = os.path.join(
                output_DIR, "2025", name + f"{float(total_amount_2025):.2f}"
            )
            os.makedirs(user_dir, exist_ok=True)
            os.makedirs(user_dir_2024, exist_ok=True)
            os.makedirs(user_dir_2025, exist_ok=True)
            for item in data[name]:
                # 格式化价格
                formatted_price = f"{float(item['total_amount']):.2f}"

                # 生成基础文件名
                base_name = f"{formatted_price}.pdf"

                # 计算序号
                price_counter[formatted_price] += 1
                count = price_counter[formatted_price]

                # 生成最终文件名
                final_name = (
                    base_name if count == 1 else f"{formatted_price}_{count}.pdf"
                )

                # 构建路径
                src_path = os.path.join(file_DIR, f"{item['file_name']}.pdf")
                # dst_path = os.path.join(user_dir, final_name)

                if item["upload_time"].startswith("2024"):
                    dst_path = os.path.join(user_dir_2024, final_name)
                elif item["upload_time"].startswith("2025"):
                    dst_path = os.path.join(user_dir_2025, final_name)
                else:
                    dst_path = os.path.join(user_dir, final_name)

                # 复制文件
                try:
                    shutil.copy2(src_path, dst_path)
                    print(f"已复制: {src_path} -> {dst_path}")
                except FileNotFoundError:
                    print(f"文件不存在: {src_path}")
                except Exception as e:
                    print(f"复制失败: {src_path} -> {dst_path} ({str(e)})")

        return data

    def output_all_invoices(self, file_DIR="cache", output_DIR="output"):
        """
        @param file_DIR 存储发票文件的位置，会按照 file_DIR/{file_name}.pdf 的路径查找文件
        @param output_DIR 输出目录，会将发票文件重命名并存放至 {uploader}/{price}.pdf
        """
        ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
        output_DIR = os.path.join(ROOT_DIR, output_DIR)
        file_DIR = os.path.join(ROOT_DIR, file_DIR)
        # Check if itemfolder exists(If not, create it)
        if not os.path.isdir(output_DIR):
            os.makedirs(output_DIR)

        data = {}
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(f"SELECT * FROM invoices")
            # 处理查询结果
            for row in cursor.fetchall():
                # 将 Row 对象转为普通字典
                row_dict = dict(row)

                # 获取上传者名称
                uploader = row_dict["uploader"]

                # 初始化该上传者的数据列表
                if uploader not in data:
                    data[uploader] = []

                # 添加当前记录到对应上传者的列表
                data[uploader].append(
                    {
                        "file_name": row_dict["file_name"],
                        "total_amount": row_dict["total_amount"],
                        "invoice_code": row_dict["invoice_code"],
                    }
                )

        for name in data:
            price_counter = defaultdict(int)
            user_dir = os.path.join(output_DIR, name)
            os.makedirs(user_dir, exist_ok=True)
            for item in data[name]:
                # 格式化价格
                formatted_price = f"{float(item['total_amount']):.2f}"

                # 生成基础文件名
                base_name = f"{formatted_price}.pdf"

                # 计算序号
                price_counter[formatted_price] += 1
                count = price_counter[formatted_price]

                # 生成最终文件名
                final_name = (
                    base_name if count == 1 else f"{formatted_price}_{count}.pdf"
                )

                # 构建路径
                src_path = os.path.join(file_DIR, f"{item['file_name']}.pdf")
                dst_path = os.path.join(user_dir, final_name)

                # 复制文件
                try:
                    shutil.copy2(src_path, dst_path)
                    print(f"已复制: {src_path} -> {dst_path}")
                except FileNotFoundError:
                    print(f"文件不存在: {src_path}")
                except Exception as e:
                    print(f"复制失败: {src_path} -> {dst_path} ({str(e)})")

        return data


# 手动更新数据库
if __name__ == "__main__":
    system = InvoiceDB("invoices.db")

    record_stats = {"total": 0, "added": 0, "duplicates": 0, "errors": []}
    stats = {"total": 0, "added": 0, "duplicates": 0, "errors": []}

    with open("result.json", "r") as f:
        test_cases = json.load(f)

    for case in test_cases["info"]:
        result = system.update_record_info(
            case["record_id"],
            case["index"],
            case["remark"],
            case["creator_name"],
            [case["purpose"], case["concrete_purpose"]],
        )
        if result["status"] == "success":
            record_stats["total"] += 1
            if result["is_new"]:
                record_stats["added"] += 1
            else:
                record_stats["duplicates"] += 1
        else:
            record_stats["errors"].append(
                {"index": case["index"], "error": result["message"]}
            )

        for invoice_data in case["result"]["data"]:
            result = system.process_invoices_data(
                invoice_data,
                case["creator_name"],
                [case["purpose"], case["concrete_purpose"]],
                case.get("index"),
            )
            if result["status"] == "success":
                stats["total"] += 1
                if result["is_new"]:
                    stats["added"] += 1
                else:
                    stats["duplicates"] += 1
            else:
                stats["errors"].append(
                    {"index": case["index"], "error": result["message"]}
                )

    # 打印统计结果
    print(
        f"处理完成：\n",
        f"记录共处理 {record_stats['total']} 条， 新增 {record_stats['added']} 条，已存在 {record_stats['duplicates']} 条，错误 {len(record_stats['errors'])} 条\n",
        f"发票共新增 {stats['added']} 张，已存在 {stats['duplicates']} 张，错误 {len(stats['errors'])} 张",
    )

    # 保存错误日志
    with open("error_log.json", "w") as f:
        json.dump(
            record_stats["errors"].extend(stats["errors"]),
            f,
            indent=2,
            ensure_ascii=False,
        )
