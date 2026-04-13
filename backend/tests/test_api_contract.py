from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


def _noop() -> None:
    return None


class ApiContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._patch_init = patch("app.main.init_db_pool", _noop)
        cls._patch_bootstrap = patch("app.main.bom_records_service.init_persistence_layer", _noop)
        cls._patch_close = patch("app.main.close_db_pool", _noop)
        cls._patch_init.start()
        cls._patch_bootstrap.start()
        cls._patch_close.start()
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.close()
        cls._patch_close.stop()
        cls._patch_bootstrap.stop()
        cls._patch_init.stop()

    def test_health_returns_request_id_header(self) -> None:
        resp = self.client.get("/api/health")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.headers.get("x-request-id"))

    def test_http_exception_body_contains_request_id(self) -> None:
        resp = self.client.get(
            "/api/sp_file",
            params={"drive_id": "", "item_id": "", "filename": "a.txt", "mode": "preview"},
        )
        self.assertEqual(resp.status_code, 400)
        body = resp.json()
        self.assertEqual(body.get("status"), "error")
        self.assertTrue(body.get("request_id"))
        self.assertEqual(body.get("request_id"), resp.headers.get("x-request-id"))

    def test_validation_error_body_contains_request_id(self) -> None:
        resp = self.client.get("/api/sp_file")
        self.assertEqual(resp.status_code, 422)
        body = resp.json()
        self.assertEqual(body.get("status"), "error")
        self.assertTrue(body.get("request_id"))
        self.assertEqual(body.get("request_id"), resp.headers.get("x-request-id"))


if __name__ == "__main__":
    unittest.main()
