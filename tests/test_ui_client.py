from datetime import date
import unittest
from unittest.mock import patch

from ui.client import TestClient, INTERFACES, SERVICE_CODES
from ui.form_query import filter_records


class FormClientTests(unittest.TestCase):
    def setUp(self):
        self.app = TestClient()
        self.app.withdraw()

    def tearDown(self):
        self.app.destroy()

    def test_payload_and_interface_switch(self):
        self.assertEqual(list(SERVICE_CODES), ["HB"])
        self.assertEqual(len(self.app.tabs.tabs()), 2)
        for name in INTERFACES:
            self.app.interface.set(name)
            self.app.change_interface()
            payload = self.app.form.payload()
            INTERFACES[name][1].from_dict(payload)
            body = payload["Transaction"]["Body"]["request"]["bizBody"]
            self.assertEqual(body["page"], 1)
            self.assertEqual(body["limit"], 10)
            self.assertEqual(body, {"page":1,"limit":10})
            self.assertTrue(all(not value.get() for value in self.app.form.inputs.values()))
            self.assertTrue(all(not value.get() for value in self.app.form.filters.values()))
        self.app.form.inputs["limit"].set("9")
        with self.assertRaises(ValueError):
            self.app.form.payload()

    def test_table_filters_and_pagination(self):
        form = self.app.form
        name = self.app.interface.get()
        form.clear_filters()
        form.display({"count":21, "records":[{"orderid":"ABC123", "branchcode":"3401"}, {"orderid":"xyz", "branchcode":"3402"}]}, {"page":1, "limit":10}, name)
        form.filters["orderid"].set("abc")
        self.assertEqual(len(form.table.get_children()), 1)
        form.filters["branchcode"].set("3402")
        self.assertEqual(len(form.table.get_children()), 0)
        form.clear_filters()
        self.assertEqual(len(form.table.get_children()), 2)
        form.inputs["branchCode"].set("unsubmitted")
        with patch.object(self.app, "submit") as submit:
            form.change_page(1)
            query = submit.call_args.args[0]["Transaction"]["Body"]["request"]["bizBody"]
            self.assertEqual(query, {"page":2, "limit":10})
        form.display({"count":21, "records":[]}, {"page":3, "limit":10}, name)
        self.assertEqual(str(form.next["state"]), "disabled")
        form.display({"count":0, "records":[]}, {"page":1, "limit":10}, name)
        self.assertEqual(str(form.previous["state"]), "disabled")
        self.assertEqual(str(form.next["state"]), "disabled")

    def test_null_and_case_insensitive_filter(self):
        records = [{"a": None, "b":"AbCd"}]
        self.assertEqual(filter_records(records, {"a":"", "b":"BC"}), records)
        self.assertEqual(filter_records(records, {"a":"null"}), [])


    def test_fixed_header_and_resizing(self):
        form = self.app.form
        self.app.deiconify()
        self.app.tabs.select(form)
        self.app.update()
        table = form.table
        header_y = table.header.winfo_y()
        table.scroll_wheel(type("Wheel", (), {"delta": -120})())
        self.app.update()
        self.assertEqual(table.body.canvasy(0), 0)
        self.assertEqual(table.header.winfo_y(), header_y)
        form.clear_filters()
        form.display({"count":100,"records":[{"orderid":str(i)} for i in range(100)]},
                     {"page":1,"limit":100}, self.app.interface.get())
        self.app.update()
        table.yview("moveto", 0.5)
        self.app.update()
        self.assertGreater(table.body.canvasy(0), 0)
        self.assertEqual(table.header.winfo_y(), header_y)
        self.app.geometry("1700x900")
        self.app.update()
        labels = [table.header.itemcget(item, "text") for item in table.header.find_all()
                  if table.header.type(item) == "text"]
        self.assertEqual(labels, [table.headings[key] for key in table.columns])


    def test_pages_are_independent(self):
        original_request = self.app.request_text.get("1.0", "end")
        self.app.response_text.insert("1.0", "JSON response stays")
        with patch("ui.client.threading.Thread"):
            self.app.submit(self.app.form.payload(), "form")
        self.assertEqual(self.app.request_text.get("1.0", "end"), original_request)
        self.app.results.put(("form response", "form done", {"count":0,"records":[]}))
        self.app.poll()
        self.assertEqual(self.app.response_text.get("1.0", "end-1c"), "JSON response stays")
        self.assertEqual(self.app.form.status.get(), "form done")
        self.app.form.inputs["branchCode"].set("unchanged")
        with patch("ui.client.threading.Thread") as thread:
            self.app.submit('{"invalid_request": true}', "json")
            self.assertEqual(thread.call_args.kwargs["args"][1], '{"invalid_request": true}')
        self.app.results.put(("raw json result", "json done", None))
        self.app.poll()
        self.assertEqual(self.app.form.inputs["branchCode"].get(), "unchanged")
        self.assertEqual(self.app.form.status.get(), "form done")
        self.assertEqual(self.app.response_text.get("1.0", "end-1c"), "raw json result")

    def test_bottom_controls_remain_visible(self):
        self.app.deiconify()
        self.app.tabs.select(self.app.form)
        for geometry in ("1280x760", "1700x900"):
            self.app.geometry(geometry)
            self.app.update()
            button = self.app.form.previous
            self.assertGreater(button.winfo_height(), 20)
            self.assertLessEqual(button.winfo_rooty()+button.winfo_height(),
                                 self.app.winfo_rooty()+self.app.winfo_height())


    def test_button_locations_and_column_resize(self):
        from types import SimpleNamespace
        form = self.app.form
        self.assertEqual(form.query_button.master, form.inputs_frame)
        self.assertEqual(form.clear_button.master, form.filter_frame)
        self.app.deiconify()
        self.app.tabs.select(form)
        self.app.update()
        table = form.table
        key = table.columns[1]
        edge = sum(table.display_widths[column] for column in table.columns[:2])
        original = table.display_widths[key]
        table.start_resize(SimpleNamespace(x=edge-table.header.canvasx(0), x_root=500))
        table.drag_resize(SimpleNamespace(x_root=580))
        self.app.update()
        self.assertEqual(table.display_widths[key], original+80)
        table.drag_resize(SimpleNamespace(x_root=-1000))
        self.app.update()
        self.assertEqual(table.display_widths[key], 40)
        table.end_resize(SimpleNamespace(x=0))
        self.assertIsNone(table.resizing)


    def test_calendar_dismissal_and_compact_buttons(self):
        from types import SimpleNamespace
        from ui.widgets import DatePicker
        self.app.deiconify()
        self.app.tabs.select(self.app.form)
        self.app.update()
        picker = next(widget for widget in self.app.form.inputs_frame.winfo_children()
                      if isinstance(widget, DatePicker))
        picker.open_calendar()
        self.app.update()
        popup = picker.popup
        picker.dismiss_outside(SimpleNamespace(x_root=popup.winfo_rootx()+10,
                                               y_root=popup.winfo_rooty()+10))
        self.assertIsNotNone(picker.popup)
        picker.dismiss_outside(SimpleNamespace(x_root=popup.winfo_rootx()-10,
                                               y_root=popup.winfo_rooty()-10))
        self.assertIsNone(picker.popup)
        self.assertIsNone(self.app.grab_current())
        picker.open_calendar()
        popup = picker.popup
        popup.focus_force()
        self.app.update()
        popup.event_generate("<Escape>")
        self.app.update()
        self.assertIsNone(picker.popup)
        self.assertEqual(int(self.app.form.query_button.grid_info()["column"]), 6)
        self.assertEqual(int(self.app.form.clear_button.grid_info()["column"]), 2)


    def test_json_page_accepts_version_response(self):
        import io
        import json
        response = io.BytesIO(json.dumps({"version":"1.7.0", "title":"Test service"}).encode())
        response.code = 200
        with patch("ui.client.urlopen", return_value=response) as open_request:
            self.app.perform("http://127.0.0.1:8000/", "", next(iter(INTERFACES)), "GET", "json")
        body, status, table = self.app.results.get_nowait()
        self.assertEqual(json.loads(body), {"version":"1.7.0", "title":"Test service"})
        self.assertNotIn("Invalid response", status)
        self.assertIn("200 OK", status)
        self.assertIsNone(table)
        self.assertEqual(open_request.call_args.args[0].method, "GET")
