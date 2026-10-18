# OfficeForge — capability matrix and investigation notes

## Scope and constraints

OfficeForge is an independent, local-first desktop-office alternative. It does not reuse Microsoft Office source code, private APIs, credentials, licensing logic, or protected user data. Microsoft Office is treated as a black-box reference; REA observations below are limited to local artifact metadata. This is not a claim of full Microsoft Office parity.

## Read-only target inventory (2026-10-17)

| Observation | Result | Evidence / boundary |
|---|---|---|
| Installed product | Microsoft 365 Apps for enterprise, en-us | Windows uninstall registry entry; version `16.0.20430.20146` |
| Word executable | `C:\\Program Files\\Microsoft Office\\root\\Office16\\WINWORD.EXE` | REA `inspect-artifact`; SHA-256 `a02ec8e28e1210a13f1c8d1874c9f10d6ed987a18365cbaae72d8403ba2d906d` |
| Excel executable | `C:\\Program Files\\Microsoft Office\\root\\Office16\\EXCEL.EXE` | REA `inspect-artifact`; SHA-256 `2876b54d3c41a978b16cab18fe6d94fbd602872d8d48e9ae6e82d9197ea19e5d` |
| PowerPoint executable | `C:\\Program Files\\Microsoft Office\\root\\Office16\\POWERPNT.EXE` | REA `inspect-artifact`; SHA-256 `d402e97afb5dd21fc38e9e3c1afc90bb22eacae31078f41081f0b68ea00af3bb` |
| Word PE resources | PE32+ x64; 1,557,224 bytes; resource inventory completed within REA default limits | REA `inspect-pe-resources`; static resource metadata only, not UI/behavior analysis |
| Native decompilation | Ghidra not configured; Hopper unsupported on Windows; IDA adapter not configured | REA `providers --format json`; deep native semantics not established |
| Python environment | Python 3.12.10; FastAPI and Uvicorn available; `python-docx`, `openpyxl`, `python-pptx`, PySide6 absent | Read-only importability probe; no packages installed |

## Capability matrix

Status legend: **MVP** = initial implementation target; **Planned** = not implemented yet; **Out of scope for parity claim** = requires extensive compatibility work.

| Area | Office user capability | OfficeForge MVP | Future work / known gaps |
|---|---|---|---|
| Writer | Create/edit text documents, headings, emphasis, lists, open/save | Editable local document; export basic `.docx` | Styles, headers/footers, images, tables, comments, track changes, pagination, full OOXML fidelity |
| Sheets | Grid editing, basic formulas, import/export | Editable grid; basic `SUM`, `AVERAGE`, `MIN`, `MAX`; `.xlsx` export | Formula engine, charts, pivots, conditional formatting, external links, macros, large-workbook performance |
| Slides | Create/edit slide titles and body text, export presentation | Basic slide editor; `.pptx` export | Themes, layout engine, animations, transitions, media, speaker notes, master slides, advanced typography |
| File compatibility | OOXML (`.docx`, `.xlsx`, `.pptx`) | Minimal generated OOXML packages; validate with ZIP/XML tests | Round-trip compatibility with real Office files requires broad fixtures and additional parsers |
| Local-first | Work without cloud account | Local HTTP server bound to loopback; no login, analytics, or network calls by design | Optional encryption, autosave recovery, accessibility and installer hardening |
| Collaboration / cloud | Shared editing and sync | Not in MVP | Separate opt-in service and conflict-resolution design required |
| Security | Safe file handling, no macro execution | File-size limits, extension checks, no macro execution | Fuzzing, sandboxed imports, security review, malicious OOXML corpus |

## Evidence vs inference

- **Observed:** Office executables are installed and their hashes/PE resource metadata were returned by REA.
- **Not observed:** complete source, full internal call graph, runtime behavior, or all Office features. Static artifact inventory is not semantic decompilation.
- **Design inference:** OfficeForge's feature priorities are based on common office workflows, not on claims about Microsoft's private implementation.

## Test strategy

1. Unit tests validate generated packages are ZIP archives and required OOXML parts parse as XML.
2. API smoke tests validate local health endpoint and each export route.
3. Round-trip tests validate basic text/cell/slide content in generated packages.
4. Optional manual interoperability check: open generated files in the user's licensed Office installation, without changing licensing or auth state.
5. Report unsupported features honestly; do not infer compatibility from a successful ZIP build alone.
