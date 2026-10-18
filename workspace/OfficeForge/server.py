from __future__ import annotations

import html
import io
import json
import re
import zipfile
from html.parser import HTMLParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
import xml.etree.ElementTree as ET

HOST = "127.0.0.1"
PORT = 8765
MAX_UPLOAD = 15 * 1024 * 1024
ROOT = Path(__file__).resolve().parent
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
P = "http://schemas.openxmlformats.org/presentationml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
CT = "http://schemas.openxmlformats.org/package/2006/content-types"


def xml_bytes(text: str) -> bytes:
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' + text).encode("utf-8")


class RichTextParser(HTMLParser):
    """Converts a small, explicit HTML subset into Word paragraphs/runs."""
    BLOCKS = {"p", "div", "h1", "h2", "h3", "li", "blockquote"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.paragraphs = []
        self.runs = []
        self.bold = False
        self.italic = False
        self.style = None

    def flush(self):
        if self.runs:
            self.paragraphs.append((self.style, self.runs))
            self.runs = []
        self.style = None

    def handle_starttag(self, tag, attrs):
        if tag in self.BLOCKS:
            self.flush()
            if tag in {"h1", "h2", "h3"}:
                self.style = {"h1": "Heading1", "h2": "Heading2", "h3": "Heading3"}[tag]
            elif tag == "li":
                self.runs.append(("• ", False, False))
        elif tag in {"strong", "b"}:
            self.bold = True
        elif tag in {"em", "i"}:
            self.italic = True
        elif tag == "br":
            self.runs.append(("\n", self.bold, self.italic))

    def handle_endtag(self, tag):
        if tag in self.BLOCKS:
            self.flush()
        elif tag in {"strong", "b"}:
            self.bold = False
        elif tag in {"em", "i"}:
            self.italic = False

    def handle_data(self, data):
        if data:
            self.runs.append((data, self.bold, self.italic))


def make_docx(content_html: str, title: str) -> bytes:
    parser = RichTextParser()
    parser.feed(content_html[:2_000_000])
    parser.close()
    parser.flush()
    if not parser.paragraphs:
        parser.paragraphs = [(None, [(title or "Untitled document", False, False)])]
    body = []
    for style, runs in parser.paragraphs:
        ppr = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
        run_xml = []
        for text, bold, italic in runs:
            props = ("<w:rPr>" + ("<w:b/>" if bold else "") + ("<w:i/>" if italic else "") + "</w:rPr>") if bold or italic else ""
            pieces = text.split("\n")
            for i, piece in enumerate(pieces):
                if piece:
                    run_xml.append(f'<w:r>{props}<w:t xml:space="preserve">{html.escape(piece)}</w:t></w:r>')
                if i < len(pieces) - 1:
                    run_xml.append(f'<w:r>{props}<w:br/></w:r>')
        body.append("<w:p>" + ppr + "".join(run_xml) + "</w:p>")
    document = (
        f'<w:document xmlns:w="{W}" xmlns:r="{R}"><w:body>{"".join(body)}'
        '<w:sectPr><w:pgSz w:w="12240" w:h="15840"/><w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" w:header="720" w:footer="720" w:gutter="0"/></w:sectPr>'
        '</w:body></w:document>'
    )
    types = f'<Types xmlns="{CT}"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>'
    rels = f'<Relationships xmlns="{PKG_REL}"><Relationship Id="rId1" Type="{R}/officeDocument" Target="word/document.xml"/></Relationships>'
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", xml_bytes(types))
        z.writestr("_rels/.rels", xml_bytes(rels))
        z.writestr("word/document.xml", xml_bytes(document))
    return out.getvalue()


def col_name(n: int) -> str:
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def valid_formula(value: str) -> str | None:
    if not value.startswith("="):
        return None
    f = value[1:].strip()
    # Deliberately limited formula grammar: no external links, DDE, or arbitrary code.
    if len(f) > 256:
        raise ValueError("Formula is too long (limit 256 characters).")
    if re.fullmatch(r"(?i)(SUM|AVERAGE|MIN|MAX)\([A-Z]{1,3}[1-9][0-9]*(?::[A-Z]{1,3}[1-9][0-9]*)?(?:,[A-Z]{1,3}[1-9][0-9]*)*\)", f):
        return f.upper()
    if re.fullmatch(r"(?i)[A-Z]{1,3}[1-9][0-9]*(?:\s*[+\-*/]\s*[A-Z]{1,3}[1-9][0-9]*){1,8}", f):
        return f.upper().replace(" ", "")
    raise ValueError("Unsupported formula. MVP supports SUM, AVERAGE, MIN, MAX, and simple cell-reference arithmetic.")


def make_xlsx(rows) -> bytes:
    if not isinstance(rows, list) or len(rows) > 500:
        raise ValueError("Workbook must contain at most 500 rows.")
    normalized = []
    max_cols = 0
    for row in rows:
        if not isinstance(row, list):
            raise ValueError("Every worksheet row must be an array.")
        if len(row) > 100:
            raise ValueError("Worksheet is limited to 100 columns.")
        max_cols = max(max_cols, len(row))
        normalized.append(row)
    cells = []
    for ri, row in enumerate(normalized, 1):
        row_cells = []
        for ci, raw in enumerate(row, 1):
            value = "" if raw is None else str(raw)
            if len(value) > 32767:
                raise ValueError(f"Cell {col_name(ci)}{ri} exceeds 32,767 characters.")
            if value == "":
                continue
            ref = f"{col_name(ci)}{ri}"
            formula = valid_formula(value)
            if formula:
                row_cells.append(f'<c r="{ref}"><f>{html.escape(formula)}</f><v></v></c>')
            elif re.fullmatch(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?", value):
                row_cells.append(f'<c r="{ref}"><v>{value}</v></c>')
            else:
                row_cells.append(f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{html.escape(value)}</t></is></c>')
        if row_cells:
            cells.append(f'<row r="{ri}">{"".join(row_cells)}</row>')
    sheet = f'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="{R}"><sheetData>{"".join(cells)}</sheetData></worksheet>'
    workbook = f'<workbook xmlns="{ "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}" xmlns:r="{R}"><sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets></workbook>'
    types = f'<Types xmlns="{CT}"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>'
    rootrels = f'<Relationships xmlns="{PKG_REL}"><Relationship Id="rId1" Type="{R}/officeDocument" Target="xl/workbook.xml"/></Relationships>'
    bookrels = f'<Relationships xmlns="{PKG_REL}"><Relationship Id="rId1" Type="{R}/worksheet" Target="worksheets/sheet1.xml"/></Relationships>'
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", xml_bytes(types))
        z.writestr("_rels/.rels", xml_bytes(rootrels))
        z.writestr("xl/workbook.xml", xml_bytes(workbook))
        z.writestr("xl/_rels/workbook.xml.rels", xml_bytes(bookrels))
        z.writestr("xl/worksheets/sheet1.xml", xml_bytes(sheet))
    return out.getvalue()


def ppt_text_shape(shape_id: int, name: str, text: str, x: int, y: int, cx: int, cy: int, size: int, bold: bool=False) -> str:
    paragraphs = []
    for line in (text or "").splitlines() or [""]:
        paragraphs.append(f'<a:p><a:r><a:rPr lang="en-US" sz="{size}"'+(' b="1"' if bold else '')+'/><a:t xml:space="preserve">'+html.escape(line)+'</a:t></a:r><a:endParaRPr lang="en-US" sz="'+str(size)+'"/></a:p>')
    return f'<p:sp><p:nvSpPr><p:cNvPr id="{shape_id}" name="{html.escape(name)}"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr><p:spPr><a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/><a:ln><a:noFill/></a:ln></p:spPr><p:txBody><a:bodyPr wrap="square" lIns="91440" tIns="45720" rIns="91440" bIns="45720"/><a:lstStyle/>{"".join(paragraphs)}</p:txBody></p:sp>'


def make_pptx(slides) -> bytes:
    if not isinstance(slides, list) or not 1 <= len(slides) <= 100:
        raise ValueError("Presentation must contain between 1 and 100 slides.")
    slide_parts = []
    for i, slide in enumerate(slides, 1):
        title = str(slide.get("title", f"Slide {i}"))[:500]
        body = str(slide.get("body", ""))[:10000]
        sp_tree = '<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
        sp_tree += ppt_text_shape(2, "Title", title, 685800, 457200, 10820400, 1200000, 3000, True)
        sp_tree += ppt_text_shape(3, "Body", body, 685800, 1900000, 10820400, 4300000, 1800, False)
        slide_xml = f'<p:sld xmlns:p="{P}" xmlns:a="{A}" xmlns:r="{R}"><p:cSld name="Slide {i}"><p:spTree>{sp_tree}</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>'
        slide_parts.append((i, slide_xml))
    types = f'<Types xmlns="{CT}"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/><Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/><Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/><Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>'+''.join(f'<Override PartName="/ppt/slides/slide{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>' for i, _ in slide_parts)+'</Types>'
    rootrels = f'<Relationships xmlns="{PKG_REL}"><Relationship Id="rId1" Type="{R}/officeDocument" Target="ppt/presentation.xml"/></Relationships>'
    ids = ''.join(f'<p:sldId id="{255+i}" r:id="rId{i+1}"/>' for i, _ in slide_parts)
    presentation = f'<p:presentation xmlns:p="{P}" xmlns:a="{A}" xmlns:r="{R}"><p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/></p:sldMasterIdLst><p:sldIdLst>{ids}</p:sldIdLst><p:sldSz cx="12192000" cy="6858000" type="wide"/><p:notesSz cx="6858000" cy="9144000"/></p:presentation>'
    presentation_rels = f'<Relationships xmlns="{PKG_REL}"><Relationship Id="rId1" Type="{R}/slideMaster" Target="slideMasters/slideMaster1.xml"/>'+''.join(f'<Relationship Id="rId{i+1}" Type="{R}/slide" Target="slides/slide{i}.xml"/>' for i, _ in slide_parts)+'</Relationships>'
    master = f'<p:sldMaster xmlns:p="{P}" xmlns:a="{A}" xmlns:r="{R}"><p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr></p:spTree></p:cSld><p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/><p:sldLayoutIdLst><p:sldLayoutId id="1" r:id="rId1"/></p:sldLayoutIdLst><p:txStyles><p:titleStyle/><p:bodyStyle/><p:otherStyle/></p:txStyles></p:sldMaster>'
    master_rels = f'<Relationships xmlns="{PKG_REL}"><Relationship Id="rId1" Type="{R}/slideLayout" Target="../slideLayouts/slideLayout1.xml"/><Relationship Id="rId2" Type="{R}/theme" Target="../theme/theme1.xml"/></Relationships>'
    layout = f'<p:sldLayout xmlns:p="{P}" xmlns:a="{A}" xmlns:r="{R}" type="blank" preserve="1"><p:cSld name="Blank"><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr></p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sldLayout>'
    layout_rels = f'<Relationships xmlns="{PKG_REL}"><Relationship Id="rId1" Type="{R}/slideMaster" Target="../slideMasters/slideMaster1.xml"/></Relationships>'
    theme = f'<a:theme xmlns:a="{A}" name="OfficeForge"><a:themeElements><a:clrScheme name="OfficeForge"><a:dk1><a:srgbClr val="202938"/></a:dk1><a:lt1><a:srgbClr val="FFFFFF"/></a:lt1><a:dk2><a:srgbClr val="344054"/></a:dk2><a:lt2><a:srgbClr val="F2F4F7"/></a:lt2><a:accent1><a:srgbClr val="2563EB"/></a:accent1><a:accent2><a:srgbClr val="16A34A"/></a:accent2><a:accent3><a:srgbClr val="EA580C"/></a:accent3><a:accent4><a:srgbClr val="7C3AED"/></a:accent4><a:accent5><a:srgbClr val="0891B2"/></a:accent5><a:accent6><a:srgbClr val="DB2777"/></a:accent6><a:hlink><a:srgbClr val="0563C1"/></a:hlink><a:folHlink><a:srgbClr val="954F72"/></a:folHlink></a:clrScheme><a:fontScheme name="OfficeForge"><a:majorFont><a:latin typeface="Aptos Display"/></a:majorFont><a:minorFont><a:latin typeface="Aptos"/></a:minorFont></a:fontScheme><a:fmtScheme name="OfficeForge"><a:fillStyleLst/><a:lnStyleLst/><a:effectStyleLst/><a:bgFillStyleLst/></a:fmtScheme></a:themeElements></a:theme>'
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", xml_bytes(types))
        z.writestr("_rels/.rels", xml_bytes(rootrels))
        z.writestr("ppt/presentation.xml", xml_bytes(presentation))
        z.writestr("ppt/_rels/presentation.xml.rels", xml_bytes(presentation_rels))
        z.writestr("ppt/slideMasters/slideMaster1.xml", xml_bytes(master))
        z.writestr("ppt/slideMasters/_rels/slideMaster1.xml.rels", xml_bytes(master_rels))
        z.writestr("ppt/slideLayouts/slideLayout1.xml", xml_bytes(layout))
        z.writestr("ppt/slideLayouts/_rels/slideLayout1.xml.rels", xml_bytes(layout_rels))
        z.writestr("ppt/theme/theme1.xml", xml_bytes(theme))
        for i, slide_xml in slide_parts:
            z.writestr(f"ppt/slides/slide{i}.xml", xml_bytes(slide_xml))
            z.writestr(f"ppt/slides/_rels/slide{i}.xml.rels", xml_bytes(f'<Relationships xmlns="{PKG_REL}"><Relationship Id="rId1" Type="{R}/slideLayout" Target="../slideLayouts/slideLayout1.xml"/></Relationships>'))
    return out.getvalue()


def import_office(filename: str, raw: bytes):
    ext = Path(filename).suffix.lower()
    with zipfile.ZipFile(io.BytesIO(raw), "r") as z:
        infos = z.infolist()
        if len(infos) > 2000:
            raise ValueError("Office package contains too many entries (limit 2,000).")
        if sum(info.file_size for info in infos) > 50 * 1024 * 1024:
            raise ValueError("Expanded Office package exceeds the 50 MiB import limit.")
        names = {info.filename for info in infos}
        if ext == ".docx" and "word/document.xml" in names:
            root = ET.fromstring(z.read("word/document.xml"))
            paras = []
            for p in root.findall(".//{%s}p" % W):
                paras.append("".join(t.text or "" for t in p.findall(".//{%s}t" % W)))
            return {"kind": "docx", "text": "\n".join(paras)}
        if ext == ".xlsx" and "xl/worksheets/sheet1.xml" in names:
            shared = []
            if "xl/sharedStrings.xml" in names:
                sr = ET.fromstring(z.read("xl/sharedStrings.xml"))
                shared = ["".join(t.text or "" for t in si.findall(".//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t")) for si in sr]
            ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
            sheet = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))
            rows = []
            for row in sheet.findall(".//" + ns + "row"):
                vals = []
                for c in row.findall(ns + "c"):
                    ref = c.attrib.get("r", "A1")
                    m = re.match(r"([A-Z]+)([0-9]+)", ref)
                    ci = 0
                    for ch in m.group(1):
                        ci = ci * 26 + ord(ch) - 64
                    while len(vals) < ci - 1:
                        vals.append("")
                    formula = c.find(ns + "f")
                    value = c.find(ns + "v")
                    inline = c.find(".//" + ns + "t")
                    if formula is not None:
                        v = "=" + (formula.text or "")
                    elif c.attrib.get("t") == "s" and value is not None:
                        v = shared[int(value.text or "0")]
                    elif inline is not None:
                        v = inline.text or ""
                    else:
                        v = value.text if value is not None and value.text else ""
                    vals.append(v)
                rows.append(vals)
            return {"kind": "xlsx", "rows": rows}
        if ext == ".pptx" and "ppt/presentation.xml" in names:
            slides = []
            slide_names = sorted((n for n in names if re.fullmatch(r"ppt/slides/slide[0-9]+\.xml", n)), key=lambda n: int(re.search(r"slide([0-9]+)", n).group(1)))
            for sn in slide_names:
                root = ET.fromstring(z.read(sn))
                texts = [t.text or "" for t in root.findall(".//{%s}t" % A)]
                slides.append({"title": texts[0] if texts else "Slide", "body": "\n".join(texts[1:])})
            return {"kind": "pptx", "slides": slides}
    raise ValueError("Unsupported or malformed file. Import .docx, .xlsx, or .pptx (macro-enabled files are not supported).")


class Handler(BaseHTTPRequestHandler):
    server_version = "OfficeForge/0.1"

    def log_message(self, fmt, *args):
        # No document contents are written to logs.
        print("%s - %s" % (self.address_string(), fmt % args))

    def send_bytes(self, status, body, content_type="application/json; charset=utf-8", headers=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def json_body(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length < 0 or length > MAX_UPLOAD:
            raise ValueError("Request body exceeds the 15 MiB limit.")
        data = json.loads(self.rfile.read(length).decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("JSON request must be an object.")
        return data

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/health":
            self.send_bytes(200, json.dumps({"ok": True, "app": "OfficeForge", "version": "0.1", "local_only": True}).encode())
            return
        if path in {"/", "/index.html"}:
            body = (ROOT / "index.html").read_bytes()
            self.send_bytes(200, body, "text/html; charset=utf-8")
            return
        self.send_bytes(404, b'{"error":"Not found"}')

    def do_POST(self):
        parsed = urlparse(self.path)
        try:
            if parsed.path.startswith("/api/export/"):
                data = self.json_body()
                kind = parsed.path.rsplit("/", 1)[-1]
                title = str(data.get("title", "Untitled"))[:120]
                if kind == "docx":
                    body = make_docx(str(data.get("html", "")), title)
                    name = "officeforge-document.docx"
                    mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                elif kind == "xlsx":
                    body = make_xlsx(data.get("rows", []))
                    name = "officeforge-workbook.xlsx"
                    mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                elif kind == "pptx":
                    body = make_pptx(data.get("slides", []))
                    name = "officeforge-presentation.pptx"
                    mime = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
                else:
                    self.send_bytes(404, b'{"error":"Unknown export type"}')
                    return
                self.send_bytes(200, body, mime, {"Content-Disposition": f'attachment; filename="{name}"'})
                return
            if parsed.path == "/api/import":
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > MAX_UPLOAD:
                    raise ValueError("Upload must be between 1 byte and 15 MiB.")
                params = parse_qs(parsed.query)
                filename = params.get("filename", [""])[0]
                ext = Path(filename).suffix.lower()
                if ext not in {".docx", ".xlsx", ".pptx"}:
                    raise ValueError("Only .docx, .xlsx, and .pptx files can be imported.")
                result = import_office(filename, self.rfile.read(length))
                self.send_bytes(200, json.dumps(result, ensure_ascii=False).encode())
                return
            self.send_bytes(404, b'{"error":"Not found"}')
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError, zipfile.BadZipFile, ET.ParseError) as exc:
            self.send_bytes(400, json.dumps({"error": str(exc)}).encode())
        except Exception:
            self.send_bytes(500, b'{"error":"Internal server error; document contents were not logged."}')


def main():
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"OfficeForge running at http://{HOST}:{PORT}")
    print("Local-only prototype. Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping OfficeForge.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
