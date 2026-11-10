"""统一显示样式与无需额外依赖的日期选择器。"""
import calendar
import ctypes
import sys
import tkinter as tk
from datetime import date, datetime
from tkinter import ttk, font


def enable_high_dpi():
    if sys.platform == "win32":
        try:
            # 创建任何窗口前启用 DPI 感知，避免 Windows 放大位图造成文字模糊。
            if ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
                return
        except (AttributeError, OSError):
            pass
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            ctypes.windll.user32.SetProcessDPIAware()


def configure_style(root):
    for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
        font.nametofont(name, root=root).configure(family="Microsoft YaHei UI", size=10)
    style = ttk.Style(root)
    style.theme_use("vista" if "vista" in style.theme_names() else "default")
    style.configure(".", font="TkDefaultFont", foreground="#17212b")
    # 页签单独使用可绘制边框的元素，输入控件保留系统原生样式。
    style.element_create("BorderedNotebook.tab", "from", "clam", "tab")
    layout = style.layout("TNotebook.Tab")
    element, options = layout[0]
    style.layout("TNotebook.Tab", [("BorderedNotebook.tab", options)])
    style.configure("TNotebook", borderwidth=1, relief="solid", bordercolor="#657383")
    style.configure("TNotebook.Tab", padding=(16, 8), borderwidth=1,
                    bordercolor="#657383", lightcolor="#657383", darkcolor="#657383")
    style.map("TNotebook.Tab",
              background=[("selected", "#ffffff"), ("!selected", "#e4eaf0")],
              padding=[("selected", (16, 8)), ("!selected", (16, 8))],
              expand=[("selected", (0, 0, 0, 0)), ("!selected", (0, 0, 0, 0))])
    style.configure("Treeview", rowheight=30, borderwidth=1, relief="solid")
    style.configure("Treeview.Heading", padding=6)
    root.option_add("*TCombobox*Listbox.font", "TkDefaultFont")


class DatePicker(ttk.Frame):
    def __init__(self, parent, textvariable, width=16, date_format="%Y%m%d", allow_text=False):
        super().__init__(parent)
        self.variable = textvariable
        self.date_format = date_format
        self.popup = None
        tk.Entry(self, textvariable=textvariable, width=width, background="white", readonlybackground="white", relief="sunken", borderwidth=1, state="normal" if allow_text else "readonly").pack(side="left", fill="x", expand=True)
        ttk.Button(self, text="▾", width=2, command=self.open_calendar).pack(side="left")

    def open_calendar(self):
        if self.popup is not None and self.popup.winfo_exists():
            self.popup.lift()
            return
        try:
            selected = datetime.strptime(self.variable.get(), self.date_format).date()
        except ValueError:
            selected = date.today()
        self.year, self.month = selected.year, selected.month
        popup = self.popup = tk.Toplevel(self)
        popup.title("选择日期")
        popup.resizable(False, False)
        popup.transient(self.winfo_toplevel())
        popup.geometry(f"+{self.winfo_rootx()}+{self.winfo_rooty()+self.winfo_height()}")
        popup.bind("<Escape>", lambda _: self.close_calendar())
        popup.bind("<ButtonPress-1>", self.dismiss_outside)
        popup.bind("<FocusOut>", lambda _: popup.after_idle(self.dismiss_unfocused))
        popup.protocol("WM_DELETE_WINDOW", self.close_calendar)
        navigation = ttk.Frame(popup, padding=5)
        navigation.pack(fill="x")
        ttk.Button(navigation, text="‹", width=3, command=lambda: self.move_month(-1)).pack(side="left")
        self.month_label = ttk.Label(navigation, anchor="center", width=18)
        self.month_label.pack(side="left", expand=True)
        ttk.Button(navigation, text="›", width=3, command=lambda: self.move_month(1)).pack(side="right")
        self.days = ttk.Frame(popup, padding=5)
        self.days.pack()
        actions = ttk.Frame(popup, padding=5)
        actions.pack(fill="x")
        ttk.Button(actions, text="今天", command=lambda: self.choose(date.today())).pack(side="left")
        ttk.Button(actions, text="清空", command=lambda: self.choose(None)).pack(side="right")
        self.draw_calendar()
        popup.update_idletasks()
        popup.grab_set()
        popup.focus_set()

    def close_calendar(self):
        popup = self.popup
        self.popup = None
        if popup is not None and popup.winfo_exists():
            if popup.grab_current() == popup:
                popup.grab_release()
            popup.destroy()

    def dismiss_outside(self, event):
        popup = self.popup
        if popup is not None and popup.winfo_exists():
            inside = (popup.winfo_rootx() <= event.x_root < popup.winfo_rootx()+popup.winfo_width()
                      and popup.winfo_rooty() <= event.y_root < popup.winfo_rooty()+popup.winfo_height())
            if not inside:
                self.close_calendar()
                return "break"

    def dismiss_unfocused(self):
        popup = self.popup
        if popup is not None and popup.winfo_exists():
            focused = popup.focus_get()
            if focused is None or focused.winfo_toplevel() != popup:
                self.close_calendar()

    def destroy(self):
        self.close_calendar()
        super().destroy()

    def move_month(self, delta):
        index = self.year * 12 + self.month - 1 + delta
        year, month = divmod(index, 12)
        if 1 <= year <= 9999:
            self.year, self.month = year, month + 1
            self.draw_calendar()

    def draw_calendar(self):
        for widget in self.days.winfo_children():
            widget.destroy()
        self.month_label.configure(text=f"{self.year} 年 {self.month:02d} 月")
        for column, label in enumerate("一二三四五六日"):
            ttk.Label(self.days, text=label, anchor="center", width=4).grid(row=0, column=column)
        for row, week in enumerate(calendar.monthcalendar(self.year, self.month), 1):
            for column, day in enumerate(week):
                if day:
                    value = date(self.year, self.month, day)
                    ttk.Button(self.days, text=str(day), width=4,
                               command=lambda value=value: self.choose(value)).grid(row=row, column=column, padx=1, pady=1)

    def choose(self, value):
        self.variable.set(value.strftime(self.date_format) if value else "")
        self.close_calendar()
