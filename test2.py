import tkinter as tk
from tkinter import ttk
from tkinter.font import Font


class DataTableApp:
    def __init__(self, root):
        self.root = root
        self.root.title("数据展示表")

        # 模拟数据（可替换为真实数据源）
        self.data = [
            [1, 1, 1, 100, "example1", "user1", 1],
            [1, 1, 1, 100, "example2", "user1", 1],
            [1, 1, 1, 100, "example3", "user1", 1],
            [1, 1, 1, 100, "example4", "user2", 2],
            [1, 1, 1, 100, "example5", "user3", 3],
        ]

        self._setup_ui()
        self._load_data()

    def _setup_ui(self):
        # 表格容器框架
        table_frame = ttk.Frame(self.root)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 创建带滚动条的Treeview
        self.tree = ttk.Treeview(
            table_frame,
            columns=("col1", "col2", "col3", "col4", "col5", "col6", "col7"),
            show="headings",
            selectmode="browse",
        )

        # 配置滚动条
        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(fill=tk.BOTH, expand=True)

        # 定义列属性
        columns = {
            "col1": {"text": "是否报销", "width": 80, "anchor": tk.CENTER},
            "col2": {"text": "支付记录", "width": 80, "anchor": tk.CENTER},
            "col3": {"text": "账单记录", "width": 80, "anchor": tk.CENTER},
            "col4": {"text": "金额", "width": 100, "anchor": tk.E},
            "col5": {"text": "具体信息", "width": 150, "anchor": tk.W},
            "col6": {"text": "上传人", "width": 100, "anchor": tk.CENTER},
            "col7": {"text": "所属序列号", "width": 100, "anchor": tk.CENTER},
        }

        # 设置列头
        for col, config in columns.items():
            self.tree.heading(
                col,
                text=config["text"],
                command=lambda c=col: self._sort_column(c, False),  # 点击排序
            )
            self.tree.column(col, width=config["width"], anchor=config["anchor"])

        # 设置现代风格
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Treeview.Heading", font=Font(family="微软雅黑", size=10, weight="bold")
        )
        style.configure("Treeview", rowheight=25, font=Font(family="宋体", size=10))
        style.map("Treeview", background=[("selected", "#0078D7")])

    def _load_data(self):
        for item in self.data:
            self.tree.insert("", tk.END, values=item)

    def _sort_column(self, col, reverse):
        # 获取列数据类型
        l = [(self.tree.set(k, col), k) for k in self.tree.get_children("")]

        # 尝试转换为数字排序
        try:
            l.sort(key=lambda t: float(t[0]), reverse=reverse)
        except ValueError:
            l.sort(reverse=reverse)

        # 重新排列数据
        for index, (val, k) in enumerate(l):
            self.tree.move(k, "", index)

        # 切换排序箭头
        self.tree.heading(col, command=lambda: self._sort_column(col, not reverse))


if __name__ == "__main__":
    root = tk.Tk()
    app = DataTableApp(root)
    root.geometry("900x400")
    root.mainloop()
