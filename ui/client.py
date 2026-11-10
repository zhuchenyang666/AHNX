"""运行 python -m ui.client，连接已启动的 HTTP 服务。"""
import json
from http.client import responses
import queue
import threading
import time
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk, font
from tkinter.scrolledtext import ScrolledText
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

from ui.form_query import FormQuery
from ui.widgets import enable_high_dpi, configure_style
from app.core import ahnx_server_config
from app.models import (CardProgressLogisticsRequest, CardProgressLogisticsResponse,
                        SocialCardFeedbackRequest, SocialCardFeedbackResponse)

INTERFACES = {
    "制卡进度及物流查询": ("ICCARD12001001", CardProgressLogisticsRequest, CardProgressLogisticsResponse),
    "社保卡回盘文件查询": ("ICCARD12001002", SocialCardFeedbackRequest, SocialCardFeedbackResponse),
}
SERVICE_CODES = {"HB": ("3033000313", "3033000314")}


def make_request(name, vendor="HB"):
    code = INTERFACES[name][0]
    now = datetime.now().astimezone()
    sequence = "029" + uuid4().hex[:26]
    header = dict(servCd=SERVICE_CODES[vendor][int(code[-1]) - 1], globalSq=sequence,
                  msgId=sequence, initRqstSysCd="029", rqstDate=now.strftime("%Y-%m-%d"),
                  rqstTime=now.strftime("%H:%M:%S.%f")[:12], rqstSysCd="029",
                  prvdSysCd="662", tranCode=code)
    return {"Transaction": {"Header": {"sysHeader": header},
                            "Body": {"request": {"bizBody": {"page": 1, "limit": 10}}}}}


class TestClient(tk.Tk):
    def __init__(self):
        enable_high_dpi()
        super().__init__()
        configure_style(self)
        self.title("安徽农信接口测试 · v1.7")
        self.geometry("1280x760")
        self.poll_timer = None
        self.results = queue.Queue()
        self.busy = False
        controls = ttk.Frame(self, padding=10)
        controls.pack(fill="x")
        self.environment = tk.StringVar(value="local")
        ttk.Label(controls, text="环境").pack(side="left")
        environment_box = ttk.Combobox(
            controls, textvariable=self.environment,
            values=["local", "production"], state="readonly", width=11,
        )
        environment_box.pack(side="left", padx=6)
        environment_box.bind("<<ComboboxSelected>>", self.select_environment)
        ttk.Label(controls, text="服务地址").pack(side="left")
        self.url = tk.StringVar(value=ahnx_server_config.environments.local.base_url)
        ttk.Entry(controls, textvariable=self.url, width=34).pack(side="left", padx=6)
        ttk.Label(controls, text="卡商：HB").pack(side="left", padx=6)
        self.interfaces = INTERFACES
        self.interface = tk.StringVar(value=next(iter(INTERFACES)))
        self.json_interface = tk.StringVar(value=next(iter(INTERFACES)))
        self.tabs = ttk.Notebook(self)
        self.tabs.pack(fill="both", expand=True)
        self.json_tab = ttk.Frame(self.tabs)
        self.tabs.add(self.json_tab, text="JSON 请求测试")
        json_controls = ttk.Frame(self.json_tab, padding=6)
        json_controls.pack(fill="x")
        self.json_interface_box = ttk.Combobox(json_controls, textvariable=self.json_interface,
                                               values=list(INTERFACES), state="readonly", width=26)
        self.json_interface_box.pack(side="left", padx=5)
        ttk.Button(json_controls, text="生成请求", command=self.generate).pack(side="left")
        self.method = tk.StringVar(value="POST")
        ttk.Combobox(json_controls, textvariable=self.method, values=["POST", "GET"], state="readonly", width=6).pack(
            side="left", padx=5)
        self.request_path = tk.StringVar(value="/" + INTERFACES[self.json_interface.get()][0])
        ttk.Label(json_controls, text="路径").pack(side="left")
        ttk.Entry(json_controls, textvariable=self.request_path, width=25).pack(side="left", padx=5)
        self.send_button = ttk.Button(json_controls, text="发送请求", command=self.send)
        self.send_button.pack(side="left", padx=6)
        self.status = tk.StringVar(value="请先启动服务：python main.py")
        ttk.Label(self.json_tab, textvariable=self.status, padding=6).pack(side="bottom", fill="x")
        panels = ttk.Panedwindow(self.json_tab, orient="horizontal")
        panels.pack(fill="both", expand=True, padx=10)
        self.request_text = self.panel(panels, "请求 JSON（可编辑）")
        self.response_text = self.panel(panels, "响应 JSON")
        self.form = FormQuery(self.tabs, self)
        self.tabs.add(self.form, text="表单查询与表格")
        self.generate()
        if self.poll_timer is not None:
            self.after_cancel(self.poll_timer)
        self.poll_timer = self.after(100, self.poll)

    def destroy(self):
        if self.poll_timer is not None:
            self.after_cancel(self.poll_timer)
        super().destroy()

    def select_environment(self, event=None):
        config = getattr(ahnx_server_config.environments, self.environment.get())
        self.url.set(config.base_url)

    def panel(self, parent, label):
        frame = ttk.Labelframe(parent, text=label, padding=5)
        text = ScrolledText(frame, wrap="none", font=("Consolas", 11), width=45, undo=True, autoseparators=True,
                            maxundo=-1)
        text.editor_font = font.Font(text, family="Consolas", size=11)
        text.configure(font=text.editor_font)
        text.bind("<Control-MouseWheel>", lambda event: self.zoom_text(text, event))
        text.bind("<Control-z>", lambda event: self.undo_text(text))
        text.pack(fill="both", expand=True)
        parent.add(frame, weight=1)
        return text

    def zoom_text(self, text, event):
        size = text.editor_font.cget("size")
        text.editor_font.configure(size=max(8, min(32, size + (1 if event.delta > 0 else -1))))
        return "break"

    def undo_text(self, text):
        try:
            text.edit_undo()
        except tk.TclError:
            pass
        return "break"

    def interface_code(self):
        return INTERFACES[self.interface.get()][0]

    def new_request(self):
        return make_request(self.interface.get())

    def change_interface(self, event=None):
        self.form.reset()

    def generate(self):
        self.request_path.set("/" + INTERFACES[self.json_interface.get()][0])
        self.show_request(make_request(self.json_interface.get()))

    def show_request(self, payload):
        self.request_text.edit_separator()
        self.request_text.delete("1.0", "end")
        self.request_text.insert("1.0", json.dumps(payload, ensure_ascii=False, indent=2))
        self.request_text.edit_separator()

    def send(self):
        try:
            self.submit(self.request_text.get("1.0", "end-1c"), "json")
        except ValueError as exc:
            messagebox.showerror("Request error", str(exc).encode("ascii", "backslashreplace").decode("ascii"))

    def submit(self, payload, source):
        if self.busy:
            return
        name = self.json_interface.get() if source == "json" else self.interface.get()
        if source == "json":
            raw = payload
            # JSON 测试页按原文发送，允许测试缺失字段或业务错误报文。
            query = {}
        else:
            model = INTERFACES[name][1].from_dict(payload)
            raw = json.dumps(model.to_dict(), ensure_ascii=False)
            query = payload["Transaction"]["Body"]["request"]["bizBody"]
        self.pending = (source, name, query)
        path = self.request_path.get().strip() if source == "json" else "/" + INTERFACES[name][0]
        url = self.url.get().rstrip("/") + "/" + path.lstrip("/")
        method = self.method.get() if source == "json" else "POST"
        self.busy = True
        self.send_button.configure(state="disabled")
        self.form.query_button.configure(state="disabled")
        self.interface_box.configure(state="disabled")
        self.form.render()
        (self.status if source == "json" else self.form.status).set("请求中…")
        threading.Thread(target=self.perform, args=(url, raw, name, method, source), daemon=True).start()

    def perform(self, url, raw, name, method="POST", source="json"):
        start = time.monotonic()
        table_body = None
        try:
            req = Request(url, data=raw.encode("utf-8") if method == "POST" else None,
                          headers={"Content-Type": "application/json"}, method=method)
            try:
                response = urlopen(req, timeout=30)
            except HTTPError as exc:
                response = exc
            with response:
                status = response.code
                body = response.read().decode("utf-8")
            detail = ""
            if status in (404, 500) and not body:
                body = json.dumps(
                    {"msg": "url not found" if status == 404 else "ks server error", "code": status})
            if status not in (200, 404, 500):
                message = f"HTTP {status} {responses.get(status, 'Request failed')}"
                body = json.dumps({"Transaction": {"Header": {"sysHeader": {
                    "resText": message, "bizResText": message}}, "Body": {"response": {"bizBody": {}}}}})
            if body:
                try:
                    parsed = json.loads(body)
                except ValueError:
                    parsed = None
                if parsed is not None:
                    body = json.dumps(parsed, ensure_ascii=False, indent=2)
                if source == "form" and status == 200 and parsed is not None:
                    try:
                        model = INTERFACES[name][2].from_dict(parsed)
                        detail = " · " + model.transaction.header.sysHeader.bizResText
                        if model.transaction.header.sysHeader.bizResCd == "AAAAAAA":
                            candidate = model.to_dict()["Transaction"]["Body"]["response"]["bizBody"]
                            if "records" in candidate:
                                table_body = candidate
                    except ValueError as exc:
                        detail = " · Invalid response format: " + str(exc)
            self.results.put((body or "(Empty response body)",
                              f"HTTP {status} {responses.get(status, '')} · {time.monotonic() - start:.3f} 秒{detail}",
                              table_body))
        except (OSError, ValueError, URLError) as exc:
            message = str(exc).encode("ascii", "backslashreplace").decode("ascii")
            error = {"Transaction": {"Header": {"sysHeader": {
                "resText": message, "bizResText": message}}, "Body": {"response": {"bizBody": {}}}}}
            self.results.put((json.dumps(error, ensure_ascii=False, indent=2),
                              "Client request failed (no complete HTTP response received)", None))

    def poll(self):
        try:
            body, status, table_body = self.results.get_nowait()
        except queue.Empty:
            pass
        else:
            source, name, query = self.pending
            self.busy = False
            self.send_button.configure(state="normal")
            self.form.query_button.configure(state="normal")
            self.interface_box.configure(state="readonly")
            if source == "json":
                self.response_text.delete("1.0", "end")
                self.response_text.insert("1.0", body)
                self.status.set(status)
            else:
                self.form.status.set(status)
                if table_body is not None:
                    self.form.display(table_body, query, name)
                else:
                    self.form.records = []
                    self.form.total = 0
                    self.form.last_query = None
            self.form.render()
        if self.poll_timer is not None:
            self.after_cancel(self.poll_timer)
        self.poll_timer = self.after(100, self.poll)


if __name__ == "__main__":
    TestClient().mainloop()
