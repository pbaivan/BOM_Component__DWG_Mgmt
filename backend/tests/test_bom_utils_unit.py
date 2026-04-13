from __future__ import annotations

import unittest

from fastapi import HTTPException

from app.services import bom_utils


class BomUtilsUnitTests(unittest.TestCase):
    def test_normalize_text_rejects_empty(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            bom_utils.normalize_text("   ", "file_name")
        self.assertEqual(ctx.exception.status_code, 400)

    def test_normalize_record_id_rejects_invalid_uuid(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            bom_utils.normalize_record_id("not-a-uuid")
        self.assertEqual(ctx.exception.status_code, 400)

    def test_status_from_flags_matrix(self) -> None:
        self.assertEqual(bom_utils.status_from_flags(True, True), "paired")
        self.assertEqual(bom_utils.status_from_flags(True, False), "file_saved")
        self.assertEqual(bom_utils.status_from_flags(False, True), "metadata_saved")
        self.assertEqual(bom_utils.status_from_flags(False, False), "draft")

    def test_safe_filename_and_mime_guess(self) -> None:
        self.assertEqual(bom_utils.safe_filename("../folder\\file.xlsx"), "file.xlsx")
        self.assertEqual(bom_utils.safe_filename(""), "source.xlsx")
        self.assertEqual(bom_utils.guess_mime_type("drawing.pdf"), "application/pdf")


if __name__ == "__main__":
    unittest.main()
