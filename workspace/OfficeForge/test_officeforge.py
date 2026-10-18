import io
import json
import unittest
import xml.etree.ElementTree as ET
import zipfile

import server


class OfficeForgePackageTests(unittest.TestCase):
    def package(self, data):
        self.assertTrue(zipfile.is_zipfile(io.BytesIO(data)))
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            for name in z.namelist():
                if name.endswith(".xml") or name.endswith(".rels") or name == "[Content_Types].xml":
                    ET.fromstring(z.read(name))
            return z

    def test_docx_package_and_text_roundtrip(self):
        data = server.make_docx("<h1>Test heading</h1><p>Hello <b>world</b>.</p><p>Second paragraph.</p>", "Test")
        z = self.package(data)
        self.assertIn("word/document.xml", z.namelist())
        imported = server.import_office("sample.docx", data)
        self.assertEqual(imported["kind"], "docx")
        self.assertIn("Test heading", imported["text"])
        self.assertIn("Hello world.", imported["text"])
        self.assertIn("Second paragraph.", imported["text"])

    def test_xlsx_package_and_formula_roundtrip(self):
        rows = [["Name", "Value"], ["A", "3"], ["B", "=SUM(B2:B2)"]]
        data = server.make_xlsx(rows)
        z = self.package(data)
        self.assertIn("xl/worksheets/sheet1.xml", z.namelist())
        imported = server.import_office("sample.xlsx", data)
        self.assertEqual(imported["kind"], "xlsx")
        self.assertEqual(imported["rows"][0][:2], ["Name", "Value"])
        self.assertEqual(imported["rows"][2][1], "=SUM(B2:B2)")

    def test_pptx_package_and_slide_roundtrip(self):
        data = server.make_pptx([{"title": "First slide", "body": "A line\nAnother line"}, {"title": "Second", "body": "Text"}])
        z = self.package(data)
        self.assertIn("ppt/presentation.xml", z.namelist())
        self.assertIn("ppt/slides/slide2.xml", z.namelist())
        imported = server.import_office("sample.pptx", data)
        self.assertEqual(imported["kind"], "pptx")
        self.assertEqual(len(imported["slides"]), 2)
        self.assertEqual(imported["slides"][0]["title"], "First slide")
        self.assertIn("Another line", imported["slides"][0]["body"])

    def test_rejects_external_or_arbitrary_formulas(self):
        with self.assertRaises(ValueError):
            server.valid_formula("=WEBSERVICE(\"https://example.com\")")
        with self.assertRaises(ValueError):
            server.valid_formula("=SUM(A1:A5)+CMD()")

    def test_limits(self):
        with self.assertRaises(ValueError):
            server.make_xlsx([["x"] for _ in range(501)])
        with self.assertRaises(ValueError):
            server.make_pptx([])

    def test_expanded_zip_limit(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("word/document.xml", "x" * (51 * 1024 * 1024))
        with self.assertRaisesRegex(ValueError, "Expanded Office package"):
            server.import_office("oversize.docx", buf.getvalue())

    def test_bad_file_rejected(self):
        with self.assertRaises((ValueError, zipfile.BadZipFile)):
            server.import_office("not-a-doc.docx", b"not a zip")


if __name__ == "__main__":
    unittest.main(verbosity=2)
