import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from service import Handler, dispatch


class ServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def test_http_tax_and_validation(self):
        body = {
            "profile": {"salary": 1275000, "financial_year": "2025-26", "age": 35, "resident": True}
        }
        req = Request(
            self.base + "/tax",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urlopen(req) as response:
            result = json.load(response)
        self.assertEqual(result["new"]["tax_payable"], 0)
        with self.assertRaises(HTTPError) as error:
            urlopen(
                Request(
                    self.base + "/tax",
                    data=b'{"profile":{}}',
                    headers={"Content-Type": "application/json"},
                )
            )
        self.assertEqual(error.exception.code, 422)

    def test_incomplete_text_never_calculates(self):
        result = dispatch("/tax/text", {"text": "Meri salary 12 lakh hai"})
        self.assertEqual(result["status"], "needs_clarification")
        self.assertNotIn("result", result)

    def test_external_calls_are_explicit(self):
        with self.assertRaises(ValueError):
            dispatch(
                "/tax",
                {
                    "profile": {
                        "salary": 1000000,
                        "financial_year": "2024-25",
                        "age": 35,
                        "resident": True,
                    },
                    "method": "llm",
                },
            )
