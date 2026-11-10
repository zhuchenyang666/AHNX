import json
import unittest
from app.app import create_app
from ui.client import make_request, INTERFACES


class HttpErrorTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app()

    def request(self, path, method="POST", body=b""):
        messages = []
        async def receive():
            return {"type":"http.request", "body":body, "more_body":False}
        async def send(message):
            messages.append(message)
        scope = {"type":"http", "asgi":{"version":"3.0"}, "http_version":"1.1", "method":method,
                 "scheme":"http", "path":path, "raw_path":path.encode(), "query_string":b"",
                 "root_path":"", "headers":[(b"content-type", b"application/json")],
                 "client":("127.0.0.1",123), "server":("localhost",8000)}
        coro = self.app(scope, receive, send)
        try:
            coro.send(None)
        except StopIteration:
            pass
        except Exception:
            if not messages or messages[0].get("status") != 500:
                raise
        finally:
            coro.close()
        return messages[0]["status"], b"".join(item.get("body",b"") for item in messages[1:])

    def test_not_found_and_internal_error_have_json_body(self):
        for method in ("GET", "POST"):
            status, body = self.request("/missing", method)
            self.assertEqual(status, 404)
            self.assertEqual(json.loads(body), {"msg":"url not found", "code":404})
            status, body = self.request("/ICCARD12001001/", method)
            self.assertEqual(status, 404)
            self.assertEqual(json.loads(body)["code"], 404)
        @self.app.get("/broken")
        async def broken():
            raise RuntimeError("private internal details")
        status, body = self.request("/broken", "GET")
        self.assertEqual(status, 500)
        self.assertEqual(json.loads(body), {"msg":"ks server error", "code":500})

    def test_validation_and_method_errors_return_esb_200(self):
        payload = make_request(next(iter(INTERFACES)))
        payload["Transaction"]["Body"]["request"]["bizBody"]["page"] = "invalid"
        cases = [("POST", b"{}"), ("POST", b"{invalid"), ("GET", b""),
                 ("POST", json.dumps(payload).encode())]
        for method, body in cases:
            with self.subTest(method=method, body=body):
                status, response = self.request("/ICCARD12001001", method, body)
                self.assertEqual(status,200)
                header = json.loads(response)["Transaction"]["Header"]["sysHeader"]
                self.assertNotEqual(header["bizResCd"],"AAAAAAA")
                self.assertTrue(header["resText"])
                self.assertTrue(header["bizResText"])
                self.assertTrue(header["resText"].isascii())
                self.assertTrue(header["bizResText"].isascii())

    def test_query_codes_must_match_endpoint(self):
        for name, (code, _, _) in INTERFACES.items():
            for biz_body in ({}, {"page": 1, "limit": 10}):
                for tran, serv in (("", ""), ("", "3033000313"),
                                   (code, ""), (code, "3033000316"),
                                   ("ICCARD12001002", "3033000314") if code.endswith("1")
                                   else ("ICCARD12001001", "3033000313"),
                                   (code, "3033000314" if code.endswith("1") else "3033000313")):
                    with self.subTest(code=code, tran=tran, serv=serv, biz=biz_body):
                        payload = make_request(name)
                        payload["Transaction"]["Header"]["sysHeader"].update(tranCode=tran, servCd=serv)
                        payload["Transaction"]["Body"]["request"]["bizBody"] = biz_body
                        status, raw = self.request("/" + code, body=json.dumps(payload).encode())
                        response = json.loads(raw)["Transaction"]
                        self.assertEqual(status, 200)
                        self.assertEqual(response["Body"]["response"]["bizBody"], {"count": 0, "records": []})
                        header = response["Header"]["sysHeader"]
                        self.assertEqual(header["bizResCd"], "100002")
                        self.assertEqual(header["resCd"], "100002")
                        self.assertIn("tranCode/servCd", header["resText"])
                        self.assertEqual(header["resText"], header["bizResText"])

    def test_order_submission_route_is_absent(self):
        paths = {path for path, methods in self.app.openapi()["paths"].items() if "post" in methods}
        self.assertEqual(paths, {"/ICCARD12001001", "/ICCARD12001002"})
