from __future__ import annotations

import json
import logging
import unittest

from app import observability


class ObservabilityUnitTests(unittest.TestCase):
    def test_generate_request_id_has_expected_shape(self) -> None:
        request_id = observability.generate_request_id()
        self.assertEqual(len(request_id), 16)
        int(request_id, 16)

    def test_json_formatter_includes_request_id_and_extra(self) -> None:
        token = observability.set_request_id("abc123")
        try:
            logger = logging.getLogger("test_logger")
            record = logger.makeRecord(
                name="test_logger",
                level=logging.INFO,
                fn="unit.py",
                lno=10,
                msg="hello",
                args=(),
                exc_info=None,
                extra={"event": "unit.test", "elapsed_ms": 12.3},
            )
            observability.RequestIdFilter().filter(record)
            payload = json.loads(observability.JsonLogFormatter().format(record))

            self.assertEqual(payload["message"], "hello")
            self.assertEqual(payload["request_id"], "abc123")
            self.assertEqual(payload["event"], "unit.test")
            self.assertEqual(payload["elapsed_ms"], 12.3)
        finally:
            observability.reset_request_id(token)


if __name__ == "__main__":
    unittest.main()
