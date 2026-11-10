"""带细线单元格边框的可滚动表格。"""
import tkinter as tk
from tkinter import font


class GridTable(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, background="white", highlightthickness=1, highlightbackground="#aeb8c2")
        self.header = tk.Canvas(self, background="#e6edf4", highlightthickness=0)
        self.header.pack(fill="x")
        self.body = tk.Canvas(self, background="white", highlightthickness=0)
        self.body.pack(fill="both", expand=True)
        self.xscroll_callback = None
        self.body.configure(xscrollcommand=self.sync_horizontal)
        self.columns = []
        self.headings = {}
        self.widths = {}
        self.display_widths = {}
        self.manual_widths = False
        self.resizing = None
        self.rows = {}
        self.serial = 0
        self.tooltip = None
        self.tooltip_timer = None
        self.hover_cell = None
        self.truncated_cells = {}
        self.selected = None
        self.pending_draw = None
        self.text_font = font.nametofont("TkDefaultFont")
        self.row_height = self.text_font.metrics("linespace") + 10
        self.header.configure(height=self.row_height)
        self.body.bind("<Motion>", self.hover)
        self.body.bind("<Leave>", lambda event: self.hide_tooltip())
        self.body.bind("<Button-1>", self.select_row)
        self.body.bind("<MouseWheel>", self.scroll_wheel)
        self.header.bind("<MouseWheel>", self.scroll_wheel)
        self.header.bind("<Motion>", self.resize_cursor)
        self.header.bind("<Leave>", lambda event: self.header.configure(cursor=""))
        self.header.bind("<Button-1>", self.start_resize)
        self.header.bind("<B1-Motion>", self.drag_resize)
        self.header.bind("<ButtonRelease-1>", self.end_resize)
        self.body.bind("<Configure>", lambda event: self.schedule_draw())
        self.body.configure(yscrollincrement=self.row_height)

    def configure(self, cnf=None, **kwargs):
        if "columns" in kwargs:
            self.columns = list(kwargs.pop("columns"))
            self.schedule_draw()
        if "xscrollcommand" in kwargs:
            self.xscroll_callback = kwargs.pop("xscrollcommand")
        if kwargs or cnf:
            return self.body.configure(cnf, **kwargs)

    def sync_horizontal(self, first, last):
        self.hide_tooltip()
        self.header.xview_moveto(first)
        if self.xscroll_callback:
            self.xscroll_callback(first, last)

    def xview(self, *args):
        return self.body.xview(*args)

    def yview(self, *args):
        self.hide_tooltip()
        return self.body.yview(*args)

    def scroll_wheel(self, event):
        self.hide_tooltip()
        self.body.yview_scroll(-1 if event.delta > 0 else 1, "units")
        return "break"

    def border_at(self, event):
        x = self.header.canvasx(event.x)
        edge = 0
        for key in self.columns:
            edge += self.display_widths.get(key, 160)
            if abs(x-edge) <= 5:
                return key
        return None

    def resize_cursor(self, event):
        self.header.configure(cursor="sb_h_double_arrow" if self.border_at(event) else "")

    def start_resize(self, event):
        key = self.border_at(event)
        if key is not None:
            self.hide_tooltip()
            self.widths.update(self.display_widths)
            self.manual_widths = True
            self.resizing = (key, event.x_root, self.widths[key])
            self.header.configure(cursor="sb_h_double_arrow")
            return "break"

    def drag_resize(self, event):
        if self.resizing is not None:
            key, start, width = self.resizing
            self.widths[key] = max(40, width + event.x_root-start)
            self.schedule_draw()
            return "break"

    def end_resize(self, event):
        self.resizing = None
        self.resize_cursor(event)

    def heading(self, key, text):
        self.headings[key] = text
        self.schedule_draw()

    def column(self, key, width, **kwargs):
        self.widths[key] = width
        self.schedule_draw()

    def get_children(self):
        return tuple(self.rows)

    def delete(self, *keys):
        for key in keys:
            self.rows.pop(key, None)
        self.schedule_draw()

    def insert(self, parent, index, values):
        self.serial += 1
        key = str(self.serial)
        self.rows[key] = values
        self.schedule_draw()
        return key

    def schedule_draw(self):
        if self.pending_draw is None:
            self.pending_draw = self.after_idle(self.draw)

    def select_row(self, event):
        index = int(self.body.canvasy(event.y) // self.row_height)
        keys = list(self.rows)
        self.selected = keys[index] if 0 <= index < len(keys) else None
        self.schedule_draw()

    def draw(self):
        self.pending_draw = None
        self.hide_tooltip()
        self.truncated_cells.clear()
        self.header.delete("all")
        self.body.delete("all")
        widths = {key: max(self.widths.get(key, 160),
                           40 if self.manual_widths else self.text_font.measure(self.headings.get(key, key)) + 16)
                  for key in self.columns}
        extra = max(0, self.body.winfo_width() - sum(widths.values()))
        if self.columns and not self.manual_widths:
            share, remainder = divmod(extra, len(self.columns))
            for index, key in enumerate(self.columns):
                widths[key] += share + (index < remainder)
        self.display_widths = widths
        x = 0
        for key in self.columns:
            width = widths[key]
            self.draw_cell(self.header, x, 0, width, self.headings.get(key, key), "#e6edf4")
            x += width
        for row, (key, values) in enumerate(self.rows.items()):
            x = 0
            for column, value in zip(self.columns, values):
                width = widths[column]
                self.draw_cell(self.body, x, row*self.row_height, width, value,
                               "#dcecff" if key == self.selected else "white")
                x += width
        total_width = sum(widths.values())
        self.header.configure(scrollregion=(0, 0, total_width, self.row_height))
        # 小数据集的滚动范围也覆盖可视区域，避免空表被 Canvas 居中或向下滚动。
        self.body.configure(scrollregion=(0, 0, total_width,
                            max(self.body.winfo_height(), len(self.rows)*self.row_height)))
        self.sync_horizontal(*self.body.xview())

    def hide_tooltip(self):
        if self.tooltip_timer is not None:
            self.after_cancel(self.tooltip_timer)
            self.tooltip_timer = None
        if self.tooltip is not None:
            self.tooltip.destroy()
            self.tooltip = None
        self.hover_cell = None

    def hover(self, event):
        x, y = self.body.canvasx(event.x), self.body.canvasy(event.y)
        cell = next((bounds for bounds in self.truncated_cells
                     if bounds[0] <= x < bounds[2] and bounds[1] <= y < bounds[3]), None)
        if cell == self.hover_cell:
            return
        self.hide_tooltip()
        if cell is not None:
            self.hover_cell = cell
            text = self.truncated_cells[cell]
            self.tooltip_timer = self.after(400, lambda: self.show_tooltip(text, event.x_root, event.y_root))

    def show_tooltip(self, text, x, y):
        self.tooltip_timer = None
        self.tooltip = tk.Toplevel(self)
        self.tooltip.overrideredirect(True)
        label = tk.Label(self.tooltip, text=text, background="#fffbdc", foreground="#17212b",
                         relief="solid", borderwidth=1, padx=8, pady=5, wraplength=600, justify="left")
        label.pack()
        self.tooltip.update_idletasks()
        x = min(x+12, self.winfo_screenwidth()-self.tooltip.winfo_reqwidth()-8)
        y = min(y+18, self.winfo_screenheight()-self.tooltip.winfo_reqheight()-8)
        self.tooltip.geometry(f"+{max(0,x)}+{max(0,y)}")

    def draw_cell(self, canvas, x, y, width, value, fill):
        canvas.create_rectangle(x, y, x+width, y+self.row_height,
                                fill=fill, outline="#c3cbd3", width=1)
        text = str(value)
        if self.text_font.measure(text) > width-12:
            while text and self.text_font.measure(text+"…") > width-12:
                text = text[:-1]
            text += "…"
            if canvas is self.body:
                self.truncated_cells[(x, y, x+width, y+self.row_height)] = str(value)
        canvas.create_text(x+6, y+self.row_height/2, text=text, anchor="w",
                           font=self.text_font, fill="#17212b")
