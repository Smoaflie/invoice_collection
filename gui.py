import os
import logging
import json
import shutil
import tkinter as tk
import tkinter.messagebox as msgbox
from tkinter import filedialog
from glob import glob
from typing import Optional
import windnd
import fitz  # fitz就是pip install PyMuPDF
from pyzbar.pyzbar import decode
from PIL import Image
from tkinter import ttk
from tkinter.font import Font
from InvoiceItem import InvoiceItem
import sqlite3

# from tqdm import trange
# Directory Management
try:
    # Run in Terminal
    ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
except:
    # Run in ipykernel & interactive
    ROOT_DIR = os.getcwd()
DB_DIR = ROOT_DIR
TMP_DIR = os.path.join(ROOT_DIR, "Temp")
OUTPUT_DIR = os.path.join(ROOT_DIR, "Output")
CONFIG_DIR = os.path.join(ROOT_DIR, "config.json")

config = {}
# Config Data
if os.path.isfile(CONFIG_DIR):
    config: dict = json.load(open(CONFIG_DIR, "r", encoding="utf8"))
    if config.get("OUTPUT_DIR"):
        OUTPUT_DIR = config.get("OUTPUT_DIR")
    if config.get("DB_DIR"):
        DB_DIR = config.get("DB_DIR")

"""
TODO: 
1.内存管理！！！
"""
# Logger
format_str = "%(asctime)s - %(name)s - %(levelname)s - %(filename)s[:%(lineno)d] - %(funcName)s - %(message)s"
datefmt_str = "%y-%m-%d %H:%M:%S"
# Remove existing handlers for basicConfig to take effect.
# TODO: This may not be a good idea, because this will infect other modules.
root_logger = logging.getLogger()
for h in root_logger.handlers:
    root_logger.removeHandler(h)
logging.basicConfig(
    filename=os.path.join(ROOT_DIR, "log.txt"),
    format=format_str,
    datefmt=datefmt_str,
    level=logging.INFO,
)

cil_handler = logging.StreamHandler(os.sys.stderr)  # 默认是sys.stderr
cil_handler.setLevel(logging.INFO)  # TODO: 会被BasicConfig限制？(过滤树)
cil_handler.setFormatter(logging.Formatter(fmt=format_str, datefmt=datefmt_str))

global_logger = logging.getLogger("Global")
global_logger.addHandler(cil_handler)

global_logger.info("ROOT_DIR: " + ROOT_DIR)


class EntryFrame:
    def __init__(self, parent, name=""):
        self.parent = parent
        self.name = name
        self.font = ("黑体", 12)
        self.frame = tk.Frame(self.parent)
        self.file_address = tk.StringVar()

        self.label = tk.Label(self.frame, text=self.name + ": ", font=self.font)
        self.entry = tk.Entry(
            self.frame,
            textvariable=self.file_address,
            font=self.font,
            highlightcolor="Fuchsia",
            highlightthickness=1,
            width=80,
        )
        self.button = tk.Button(
            self.frame, text="Open...", font=self.font, command=self.select_file
        )

        self.label.grid(row=0, column=0)
        self.entry.grid(row=0, column=1)
        self.button.grid(row=0, column=2)

        windnd.hook_dropfiles(self.entry, func=self.dragged_files)

        self.frame.pack()

    def select_file(self):
        """选择文件"""
        file = filedialog.askopenfilename(initialdir=os.getcwd())
        self.file_address.set(file)

    def dragged_files(self, files):
        """拖放文件"""
        self.file_address.set(files[0].decode("gbk"))


class APP(object):
    """主程序"""

    state_icons = {
        0: "◻",  # 未提交
        1: "◼",  # 已提交
        2: "✔",  # 已完成
        -1: "✖",  # 已放弃
    }

    def __init__(self, width=840, height=350):
        # 初始化参数
        self.w = width
        self.h = height
        self.title = "Invoice Manager Ver1.0"
        self.data_dir = os.path.join(DB_DIR, "invoices.db")
        if not os.path.exists(DB_DIR):
            os.mkdir(DB_DIR)
        self.logger = logging.getLogger("App")
        self.logger.addHandler(cil_handler)
        # self.logger.addHandler(file_handler)
        self.root = tk.Tk(className=self.title)
        self.font = ("黑体", 12)
        self.itemlist = []
        self.last_selected_index = 0
        self.root.iconbitmap(default=os.path.join(ROOT_DIR, "icon.ico"))
        self.jpg_quality = 20  # PDF output quality
        # Config Para Import
        if config.get("PDF_JPG_QUALITY"):
            self.jpg_quality = config.get("PDF_JPG_QUALITY")
        # 定义文字
        self.itemname = tk.StringVar()
        self.total = tk.Variable()
        self.itemcnt = tk.Variable()
        self.info_disp = tk.StringVar()
        # Frame空间
        frame_records = ttk.Frame(self.root)
        frame_bottom = tk.Frame(self.root)

        # Menu菜单
        menu = tk.Menu(self.root)
        self.root.config(menu=menu)
        aboutmenu = tk.Menu(menu, tearoff=0)
        menu.add_cascade(label="Ver1.0 Author: Master Yip", menu=aboutmenu)
        menu.add_cascade(label="Ver2.0 Modifier: Smoalife", menu=aboutmenu)

        # 发票记录
        # 创建带滚动条的Treeview
        self.tree_records = ttk.Treeview(
            frame_records,
            columns=("col0", "col1", "col2", "col3", "col4", "col5", "col6"),
            show="headings",
            selectmode="browse",
        )
        self.item_id_map = {}
        # 配置滚动条
        vsb = ttk.Scrollbar(
            frame_records, orient="vertical", command=self.tree_records.yview
        )
        hsb = ttk.Scrollbar(
            frame_records, orient="horizontal", command=self.tree_records.xview
        )
        self.tree_records.configure(xscrollcommand=hsb.set, yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)
        # 定义列属性
        columns = {
            "col0": {"text": "状态", "width": 40, "anchor": tk.CENTER},
            "col1": {"text": "上传人", "width": 60, "anchor": tk.CENTER},
            "col2": {"text": "组序列", "width": 60, "anchor": tk.CENTER},
            "col3": {"text": "日期", "width": 80, "anchor": tk.CENTER},
            "col4": {"text": "发票号", "width": 100, "anchor": tk.CENTER},
            "col5": {"text": "金额", "width": 60, "anchor": tk.CENTER},
            "col6": {"text": "具体信息", "width": 100, "anchor": tk.CENTER},
        }
        for col, conf in columns.items():
            self.tree_records.heading(
                col,
                text=conf["text"],
                command=lambda c=col: self._sort_column(c, False),  # 点击排序
            )
            self.tree_records.column(col, width=conf["width"], anchor=conf["anchor"])
        #  修改风格
        style = ttk.Style()
        style.theme_use("clam")
        # style.configure(
        #     "Treeview.Heading", font=Font(family="微软雅黑", size=1, weight="bold")
        # )
        # style.configure("Treeview", rowheight=25, font=Font(family="宋体", size=10))
        # style.map("Treeview", background=[("selected", "#0078D7")])
        # 绑定按键（修改属性）
        self.tree_records.bind("<Return>", lambda event: self.sel_item_state_changed(1))
        self.tree_records.bind("<space>", lambda event: self.sel_item_state_changed(1))
        self.tree_records.bind(
            "<BackSpace>", lambda event: self.sel_item_state_changed(0)
        )

        # 底部控件
        self.name_entry = tk.Entry(
            frame_bottom,
            textvariable=self.itemname,
            font=self.font,
            highlightcolor="Fuchsia",
            highlightthickness=1,
            width=50,
        )
        self.info_label = tk.Entry(
            frame_bottom,
            textvariable=self.info_disp,
            font=self.font,
            highlightcolor="Fuchsia",
            highlightthickness=1,
            width=50,
        )
        self.button_add = tk.Button(
            frame_bottom,
            text="Add/Update",
            font=self.font,
            width=14,
            command=self.add_item,
        )
        self.button_batchimport = tk.Button(
            frame_bottom,
            text="Batch Import",
            font=self.font,
            width=14,
            # command=self.batch_import,
        )
        self.button_output = tk.Button(
            frame_bottom,
            text="Output Select",
            font=self.font,
            width=14,
            command=self.sel_item_output,
        )
        self.button_delete = tk.Button(
            frame_bottom,
            text="Del Select",
            font=self.font,
            width=14,
            command=self.sel_item_del,
        )

        self.button_state_unsubmitted = tk.Button(
            frame_bottom,
            text="▷",
            font=self.font,
            width=5,
            command=lambda: self.sel_item_state_changed(0),
        )
        self.button_state_submitted = tk.Button(
            frame_bottom,
            text="▶",
            font=self.font,
            width=5,
            command=lambda: self.sel_item_state_changed(1),
        )
        self.button_state_completed = tk.Button(
            frame_bottom,
            text="✔",
            font=self.font,
            width=5,
            command=lambda: self.sel_item_state_changed(2),
        )
        self.button_state_tag_star0 = tk.Button(
            frame_bottom,
            text="☆",
            font=self.font,
            width=5,
            command=self.sel_item_state_tag_star0,
        )
        self.button_state_tag_star1 = tk.Button(
            frame_bottom,
            text="★",
            font=self.font,
            width=5,
            command=self.sel_item_state_tag_star1,
        )
        self.button_state_dropped = tk.Button(
            frame_bottom,
            text="✖",
            font=self.font,
            width=5,
            command=self.sel_item_state_dropped,
        )

        # 控件布局
        frame_records.pack(fill="y", padx=10, expand=True)
        # self.invoice_frame = EntryFrame(self.root, "Invoice ")
        # self.order_frame = EntryFrame(self.root, "Order   ")
        # self.transfer_frame = EntryFrame(self.root, "Transfer")
        frame_bottom.pack(pady=10)

        self.tree_records.pack(fill=tk.BOTH, expand=True)

        # self.name_entry.grid(row=0, column=0)
        # self.info_label.grid(row=1, column=0)

        # self.button_add.grid(row=0, column=1)
        # self.button_batchimport.grid(row=0, column=2)
        # self.button_output.grid(row=1, column=1)
        # self.button_delete.grid(row=1, column=2)

        self.button_state_unsubmitted.grid(row=0, column=3)
        self.button_state_submitted.grid(row=0, column=4)
        self.button_state_completed.grid(row=0, column=5)
        # self.button_state_tag_star0.grid(row=1, column=3)
        # self.button_state_tag_star1.grid(row=1, column=4)
        # self.button_state_dropped.grid(row=1, column=5)

        self.load()

    # def itemselected_callback(self, event):
    #     """item被选中时的回调函数"""
    #     items_index = self.tree_records.selection()
    #     if len(items_index) == 1:
    #         item = self.itemlist[items_index[0]]
    #         if item[item.INVOICE_DIR].startswith("#"):
    #             self.invoice_frame.file_address.set(item[item.INVOICE_DIR])
    #         elif item[item.INVOICE_DIR]:
    #             self.invoice_frame.file_address.set(
    #                 item.abspath(item[item.INVOICE_DIR])
    #             )
    #         else:
    #             self.invoice_frame.file_address.set("")
    #         if item[item.ORDER_DIR]:
    #             self.order_frame.file_address.set(item.abspath(item[item.ORDER_DIR]))
    #         else:
    #             self.order_frame.file_address.set("")
    #         if item[item.TRANSFER_DIR]:
    #             self.transfer_frame.file_address.set(
    #                 item.abspath(item[item.TRANSFER_DIR])
    #             )
    #         else:
    #             self.transfer_frame.file_address.set("")
    #         self.itemname.set(item["name"])
    #     elif len(items_index) > 1:
    #         self.invoice_frame.file_address.set("")
    #         self.order_frame.file_address.set("")
    #         self.transfer_frame.file_address.set("")
    #         self.itemname.set("")

    #     self.total.set(0)
    #     self.itemcnt.set(items_index.__len__())
    #     for it in items_index:
    #         self.total.set(
    #             self.total.get() + float(self.itemlist[it][InvoiceItem.INVOICE_VALUE])
    #         )
    #     self.info_disp.set(
    #         "Total(taxfree):{:.2f}, Count:{:d}".format(
    #             self.total.get(), self.itemcnt.get()
    #         )
    #     )

    def _sort_column(self, col, reverse):
        # 获取列数据类型
        l = [
            (self.tree_records.set(k, col), k)
            for k in self.tree_records.get_children("")
        ]
        # 尝试转换为数字排序
        try:
            l.sort(key=lambda t: float(t[0]), reverse=reverse)
        except ValueError:
            l.sort(reverse=reverse)

        # 重新排列数据
        for index, (val, k) in enumerate(l):
            self.tree_records.move(k, "", index)

        # 切换排序箭头
        self.tree_records.heading(
            col, command=lambda: self._sort_column(col, not reverse)
        )

    # def sortmethod_callback(self, event):
    #     """排序方式改变时的回调函数"""
    #     # TODO: Add other sorting method.
    #     select = self.sortlist.curselection()
    #     attr = -1
    #     if select:
    #         attr = select[0]
    #     if attr == 0:  # Value Up
    #         self.itemlist.sort(key=lambda x: float(x[x.INVOICE_VALUE]))
    #     elif attr == 1:  # Value Down
    #         self.itemlist.sort(key=lambda x: float(x[x.INVOICE_VALUE]), reverse=True)
    #     elif attr == 2:  # Date Up
    #         self.itemlist.sort(key=lambda x: x[x.INVOICE_DATE])
    #     elif attr == 3:  # Date Down
    #         self.itemlist.sort(key=lambda x: x[x.INVOICE_DATE], reverse=True)
    #     elif attr == 4:  # State (Done/Order/Transfer)
    #         self.itemlist.sort(
    #             key=lambda x: 10 * int(x["state"]) + int(bool(x[x.ORDER_DIR]))
    #         )
    #     elif attr == 5:  # Name
    #         self.itemlist.sort(key=lambda x: x["name"])
    #     self.refresh_tree_records()
    #     self.save()

    def center(self):
        """
        函数说明:tkinter窗口居中
        """
        ws = self.root.winfo_screenwidth()
        hs = self.root.winfo_screenheight()
        x = int((ws / 2) - (self.w / 2))
        y = int((hs / 2) - (self.h / 2))
        self.root.geometry("{}x{}+{}+{}".format(self.w, self.h, x, y))

    def loop(self):
        """
        函数说明:loop等待用户事件
        """
        # 禁止修改窗口宽度
        self.root.resizable(False, True)
        # self.root.rowconfigure(index=0, weight=1, minsize=500)
        # 窗口居中
        self.center()
        self.root.mainloop()

    def __del__(self):

        if hasattr(self, "window"):
            self.root.destroy()

    def add_item(self):
        """添加item"""
        file = self.invoice_frame.file_address.get()
        if file:
            item_exists = False
            info = read_invoice_info(file)
            for item in self.itemlist:
                if item[item.INVOICE_CODE] == info.get(item.INVOICE_CODE) and item[
                    item.INVOICE_NUMBER
                ] == info.get(item.INVOICE_NUMBER):
                    item_exists = True
                    self.logger.info(
                        "Invoice(%s) already exists.", os.path.basename(file)
                    )
                    self.itemlist[self.itemlist.index(item)].edit(
                        self.itemname.get(),
                        self.invoice_frame.file_address.get(),
                        self.order_frame.file_address.get(),
                        self.transfer_frame.file_address.get(),
                    )
                    break
            if not item_exists:
                self.itemlist.append(
                    InvoiceItem(
                        self.itemname.get(),
                        self.invoice_frame.file_address.get(),
                        self.order_frame.file_address.get(),
                        self.transfer_frame.file_address.get(),
                    )
                )
        else:
            msgbox.showerror("Error", "Invoice is empty.")
        self.refresh_tree_records()
        self.save()

    # def batch_import(self):
    #     """批量导入"""
    #     invoice_files = filedialog.askopenfilenames(initialdir=os.getcwd())
    #     for file in invoice_files:
    #         # pdf check
    #         if os.path.isfile(file) and os.path.splitext(file)[1] == ".pdf":
    #             info = read_invoice_info(file)
    #             item_exists = False
    #             if info:
    #                 for item in self.itemlist:
    #                     if item[item.INVOICE_CODE] == info.get(
    #                         item.INVOICE_CODE
    #                     ) and item[item.INVOICE_NUMBER] == info.get(
    #                         item.INVOICE_NUMBER
    #                     ):
    #                         item_exists = True
    #                         break
    #             if not item_exists and info:
    #                 self.itemlist.append(
    #                     InvoiceItem(os.path.splitext(os.path.basename(file))[0], file)
    #                 )
    #             elif info:
    #                 self.logger.info("%s exists.", os.path.basename(file))
    #             else:
    #                 self.logger.warning("No info is found in %s", file)

    #         else:
    #             self.logger.warning("Not valid invoice file(pdf): %s", file)
    #     self.refresh_tree_records()
    #     self.save()

    def refresh_tree_records(self):

        self.tree_records.delete(*self.tree_records.get_children())
        self.item_id_map.clear()  # 清空旧映射
        for list_index, item in enumerate(self.itemlist):
            state_icon = APP.state_icons.get(item.state, "?")
            tree_item_id = self.tree_records.insert(
                "",
                tk.END,
                values=(
                    state_icon,  # 状态列
                    item.uploader,
                    item.record_index,
                    item.INVOICE_DATE,
                    f"\u200b{item.INVOICE_CODE}",  # 添加零宽空格
                    item.INVOICE_TOTAL_AMOUNT,
                    item.remark,
                ),
            )
            selected = self.tree_records.selection()
            self.last_selected_index = selected[0] if selected else ""
            self.item_id_map[tree_item_id] = list_index  # 记录对应关系
            self.tree_records.see(self.last_selected_index)

    def save(self, dir=""):
        """
        description: Save data to database.
        param {*} self
        param {*} dir
        return {*}
        """
        if not dir:
            dir = self.data_dir

    def load(self):
        """加载数据时使用排序方法"""
        sorted_invoices = InvoiceItem.db.get_invoices_sorted()
        for item in sorted_invoices:
            self.itemlist.append(
                InvoiceItem(
                    name=item["file_name"],
                    data={
                        "basic_info": {
                            "invoice_code": item["invoice_code"],
                            "date": item["upload_time"],
                        },
                        "total_amount": item["total_amount"],
                        "state": item["state"],  # 传递状态
                    },
                    uploader=item["uploader"],
                    record_index=item["record_index"],
                    remark="null",
                )
            )
        self.refresh_tree_records()

    def items_itemfiles_check(self):
        for item in self.itemlist:
            item.itemfiles_check()
        self.refresh_tree_records()
        self.save()

    def sel_item_output(self):
        if os.path.exists(OUTPUT_DIR):
            shutil.rmtree(OUTPUT_DIR)
        if not os.path.exists(OUTPUT_DIR):
            os.makedirs(OUTPUT_DIR)
        # img output
        self.logger.info("Images Outputing...")
        index_ls = self.tree_records.selection()
        for i in range(len(index_ls)):
            self.info_disp.set("Outputing Img: " + str(i) + "/" + str(len(index_ls)))
            self.root.update()
            self.itemlist[index_ls[i]].invoice_files_output(prefix="{:02d}_".format(i))
        # pdf output
        self.logger.info("PDF Outputing...")
        doc = fitz.open()
        for i in range(len(index_ls)):
            self.info_disp.set("Outputing PDF: " + str(i) + "/" + str(len(index_ls)))
            self.root.update()
            self.itemlist[index_ls[i]].invoice_files_output_pdf(
                doc, self.jpg_quality, footnote_prefix="{:02d}".format(i)
            )
        doc.save(os.path.join(OUTPUT_DIR, "output.pdf"))

        os.startfile(OUTPUT_DIR)

    def sel_item_del(self):
        for index in tuple(reversed(self.tree_records.selection())):
            shutil.rmtree(self.itemlist[index].itemfolder_abspath())
            self.itemlist.pop(index)
        self.refresh_tree_records()
        self.save()

    # Set Invoice State
    def sel_item_state_changed(self, new_state: int):
        """状态按钮统一处理"""
        selected = self.tree_records.selection()
        for tree_item_id in selected:
            print(self.tree_records.item(tree_item_id))
            invoice_code = self.tree_records.item(tree_item_id)["values"][4][
                1:
            ]  # 移除开头零宽空格
            list_index = self.item_id_map.get(tree_item_id)
            if InvoiceItem.db.update_invoice_state(invoice_code, new_state):
                self.itemlist[list_index].state = new_state
            current_values = list(self.tree_records.item(tree_item_id, "values"))
            current_values[0] = APP.state_icons.get(new_state)
            self.tree_records.item(tree_item_id, values=current_values)

    def sel_item_state_unsubmitted(self):
        for item in self.tree_records.selection():
            self.itemlist[item]["state"] = InvoiceItem.UNSUBMITTED
        self.refresh_tree_records()
        self.save()

    def sel_item_state_submitted(self):
        for item in self.tree_records.selection():
            self.itemlist[item]["state"] = InvoiceItem.SUBMITTED
        self.refresh_tree_records()
        self.save()

    def sel_item_state_completed(self):
        for item in self.tree_records.selection():
            self.itemlist[item]["state"] = InvoiceItem.COMPLETED
        self.refresh_tree_records()
        self.save()

    def sel_item_state_tag_star0(self):
        for item in self.tree_records.selection():
            self.itemlist[item]["state"] = InvoiceItem.TAG_STAR0
        self.refresh_tree_records()
        self.save()

    def sel_item_state_tag_star1(self):
        for item in self.tree_records.selection():
            self.itemlist[item]["state"] = InvoiceItem.TAG_STAR1
        self.refresh_tree_records()
        self.save()

    def sel_item_state_dropped(self):
        for item in self.tree_records.selection():
            self.itemlist[item]["state"] = InvoiceItem.DROPPED
        self.refresh_tree_records()
        self.save()


if __name__ == "__main__":
    app = APP()
    app.loop()
