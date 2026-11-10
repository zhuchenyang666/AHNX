"""表单请求与服务端分页结果表格。"""
import tkinter as tk
from tkinter import ttk, messagebox

from app.models import (CardProgressLogisticsQueryBizBody, CardProgressLogisticsRecordBizBody,
                        SocialCardFeedbackQueryBizBody, SocialCardFeedbackRecordBizBody)
from ui.grid_table import GridTable
from ui.widgets import DatePicker

ENUM_VALUES = {"cardBizType": ("newcard", "changecard"), "crdPrdTp": ("newcard", "changecard"),
               "cardbiztype": ("newcard", "changecard"), "crdprdtp": ("newcard", "changecard"),
               "crdprdsts": ("pending", "making", "finished")}

MODELS = {
    "ICCARD12001001": (CardProgressLogisticsQueryBizBody, CardProgressLogisticsRecordBizBody),
    "ICCARD12001002": (SocialCardFeedbackQueryBizBody, SocialCardFeedbackRecordBizBody),
}


def filter_records(records, filters):
    return [record for record in records if all(
        value.strip().casefold() in str(record.get(key) or "").casefold()
        for key, value in filters.items() if value != "全部"
    )]


class FormQuery(ttk.Frame):
    def __init__(self, parent, client):
        super().__init__(parent, padding=4)
        self.client = client
        self.records = []
        self.total = 0
        self.current_page = 1
        self.current_limit = 10
        self.last_query = None
        self.last_name = None
        interface_bar = ttk.Frame(self)
        interface_bar.pack(fill="x", pady=3)
        ttk.Label(interface_bar, text="查询接口").pack(side="left")
        self.client.interface_box = ttk.Combobox(interface_bar, textvariable=self.client.interface,
            values=list(self.client.interfaces), state="readonly", width=26)
        self.client.interface_box.pack(side="left", padx=5)
        self.client.interface_box.bind("<<ComboboxSelected>>", self.client.change_interface)
        self.status = tk.StringVar(value="查询条件留空表示不限；页码、每页条数留空时使用 1、10。")
        self.inputs_frame = ttk.LabelFrame(self, text="查询条件（日期 yyyyMMdd；机构、文件名等按接口精确匹配）", padding=3)
        self.inputs_frame.pack(fill="x")
        self.filter_frame = ttk.LabelFrame(self, text="当前页各字段模糊筛选（多条件同时满足；不改变接口总数）", padding=3)
        self.filter_frame.pack(fill="x", pady=3)
        table_frame = ttk.Frame(self)
        table_frame.pack(fill="both", expand=True)
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)
        self.table = GridTable(table_frame)
        self.table.grid(row=0, column=0, sticky="nsew")
        vertical = ttk.Scrollbar(table_frame, orient="vertical", command=self.table.yview)
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal = ttk.Scrollbar(table_frame, orient="horizontal", command=self.table.xview)
        horizontal.grid(row=1, column=0, sticky="ew")
        self.table.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        navigation = ttk.Frame(self)
        table_frame.pack_forget()
        navigation.pack(side="bottom", fill="x", pady=5)
        ttk.Label(self, textvariable=self.status, padding=3).pack(side="bottom", fill="x")
        table_frame.pack(fill="both", expand=True)
        self.previous = ttk.Button(navigation, text="上一页", command=lambda: self.change_page(-1), state="disabled")
        self.previous.pack(side="left")
        self.next = ttk.Button(navigation, text="下一页", command=lambda: self.change_page(1), state="disabled")
        self.next.pack(side="left", padx=5)
        self.summary = tk.StringVar(value="尚未查询")
        ttk.Label(navigation, textvariable=self.summary).pack(side="left", padx=8)
        self.reset()

    def reset(self):
        code = self.client.interface_code()
        query_model, record_model = MODELS[code]
        for frame in (self.inputs_frame, self.filter_frame):
            for widget in frame.winfo_children():
                widget.destroy()
        self.inputs = {}
        for i, (key, field) in enumerate(query_model.model_fields.items()):
            ttk.Label(self.inputs_frame, text=field.description.split("；")[0].split("，")[0].split("：")[0]).grid(row=i//4, column=(i%4)*2, sticky="w")
            variable = tk.StringVar()
            if key in ENUM_VALUES:
                widget = ttk.Combobox(self.inputs_frame, textvariable=variable, values=("",) + ENUM_VALUES[key], state="readonly", width=15)
            elif key in ("startDate", "endDate"):
                widget = DatePicker(self.inputs_frame, variable, width=11)
            elif key in ("page", "limit"):
                widget = ttk.Spinbox(self.inputs_frame, textvariable=variable, from_=1 if key == "page" else 10, to=1000000 if key == "page" else 1000, width=15)
            else:
                widget = ttk.Entry(self.inputs_frame, textvariable=variable, width=15)
            widget.grid(row=i//4, column=(i%4)*2+1, padx=3, pady=2, sticky="ew")
            self.inputs[key] = variable
        self.inputs_frame.columnconfigure(8, weight=0)
        self.query_button = ttk.Button(self.inputs_frame, text="查询", command=self.query)
        self.query_button.grid(row=(len(query_model.model_fields)-1)//4, column=((len(query_model.model_fields)-1)%4+1)*2, padx=8, pady=2, sticky="sw")
        self.columns = [field.alias for field in record_model.model_fields.values()]
        self.table.configure(columns=["row_number"] + self.columns)
        self.table.heading("row_number", text="序号")
        self.table.column("row_number", width=58)
        self.filters = {}
        for i, field in enumerate(record_model.model_fields.values()):
            key = field.alias
            label = field.description.split('；')[0].split('，')[0].split('：')[0].split('，')[0].split('：')[0]
            self.table.heading(key, text=label)
            self.table.column(key, width=360 if key == "cardfilename" else 150, minwidth=100, stretch=False)
            ttk.Label(self.filter_frame, text=label).grid(row=i//4, column=(i%4)*2, sticky="w")
            variable = tk.StringVar()
            if key in ENUM_VALUES:
                widget = ttk.Combobox(self.filter_frame, textvariable=variable, values=("",) + ENUM_VALUES[key], state="readonly", width=14)
            elif key in ("orderdate", "crdprddt"):
                widget = DatePicker(self.filter_frame, variable, width=11, allow_text=True)
            else:
                widget = ttk.Entry(self.filter_frame, textvariable=variable, width=14)
            widget.grid(row=i//4, column=(i%4)*2+1, padx=4, pady=2)
            variable.trace_add("write", lambda *_: self.render())
            self.filters[key] = variable
        self.filter_frame.columnconfigure(8, weight=0)
        self.clear_button = ttk.Button(self.filter_frame, text="清空模糊筛选", command=self.clear_filters)
        self.clear_button.grid(row=(len(record_model.model_fields)-1)//4, column=((len(record_model.model_fields)-1)%4+1)*2, padx=8, pady=2, sticky="sw")
        self.records = []
        self.total = 0
        self.last_query = None
        self.last_name = None
        self.current_page, self.current_limit = 1, 10
        self.render()

    def payload(self):
        payload = self.client.new_request()
        body = {}
        for key, variable in self.inputs.items():
            value = variable.get().strip()
            if key in ("page", "limit"):
                try:
                    value = int(value or (1 if key == "page" else 10))
                except ValueError:
                    raise ValueError("page and limit must be integers")
                if (key == "page" and value < 1) or (key == "limit" and not 10 <= value <= 1000):
                    raise ValueError("page must be at least 1; limit must be between 10 and 1000")
            elif not value:
                continue
            query_model = MODELS[self.client.interface_code()][0]
            body[query_model.model_fields[key].alias] = value
        payload["Transaction"]["Body"]["request"]["bizBody"] = body
        return payload

    def query(self):
        try:
            self.client.submit(self.payload(), "form")
        except ValueError as exc:
            messagebox.showerror("Query error", str(exc).encode("ascii", "backslashreplace").decode("ascii"))

    def change_page(self, delta):
        if self.last_query is None or self.client.busy:
            return
        # 翻页沿用上次成功查询的条件，避免未提交的输入改变结果范围。
        payload = self.client.new_request()
        body = dict(self.last_query)
        body["page"] = self.current_page + delta
        payload["Transaction"]["Body"]["request"]["bizBody"] = body
        self.client.submit(payload, "form")

    def display(self, body, query, name):
        if name != self.client.interface.get():
            return
        self.last_name = name
        self.last_query = dict(query)
        self.current_page, self.current_limit = query["page"], query["limit"]
        self.inputs["page"].set(str(self.current_page))
        self.inputs["limit"].set(str(self.current_limit))
        self.records = body["records"]
        self.total = body["count"]
        self.render()

    def render(self):
        self.table.delete(*self.table.get_children())
        filtered = filter_records(self.records, {key: var.get() for key, var in self.filters.items()})
        for number, record in enumerate(filtered, 1):
            self.table.insert("", "end", values=[number] + [record.get(key) if record.get(key) is not None else "" for key in self.columns])
        pages = max(1, (self.total + self.current_limit - 1)//self.current_limit)
        self.summary.set(f"第 {self.current_page}/{pages} 页 · 每页 {self.current_limit} 条 · 共 {self.total} 条 · 本页显示 {len(filtered)}/{len(self.records)} 条")
        busy = self.client.busy
        self.previous.configure(state="normal" if not busy and self.last_query and self.current_page > 1 else "disabled")
        self.next.configure(state="normal" if not busy and self.last_query and self.current_page < pages else "disabled")

    def clear_filters(self):
        for variable in self.filters.values():
            variable.set("")
