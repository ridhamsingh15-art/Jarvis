# OfficeForge

OfficeForge is an independent, local-first office-suite prototype built as a clean-room implementation. It is not affiliated with Microsoft and does not copy Microsoft Office code.

## Current MVP

- **Writer:** in-browser text editor with basic bold/italic/list/heading controls; exports \`.docx\`; imports basic paragraph text from \`.docx\`.
- **Sheets:** editable 12×8 grid; exports \`.xlsx\`; imports the first worksheet from \`.xlsx\`; supports a deliberately small formula subset (\`SUM\`, \`AVERAGE\`, \`MIN\`, \`MAX\`, and simple cell-reference arithmetic).
- **Slides:** add/edit title-and-body slides; exports \`.pptx\`; imports basic slide text from \`.pptx\`.
- No macros are executed. Macro-enabled file extensions are rejected. All HTTP listening is bound to \`127.0.0.1\`; no account, cloud API, analytics, or third-party package is required.

## Run on Windows

PowerShell:

\`\`\`powershell
Set-Location "$HOME\Projects\Jarvis\workspace\OfficeForge"
python .\server.py
\`\`\`

Then open \`http://127.0.0.1:8765\` in your browser. Keep the terminal open while using the app; press \`Ctrl+C\` to stop it.

## Run tests

\`\`\`powershell
Set-Location "$HOME\Projects\Jarvis\workspace\OfficeForge"
python -m py_compile .\server.py .\test_officeforge.py
python -m unittest -v .\test_officeforge.py
\`\`\`

## Important limits

This is an early functional prototype, not a full replacement for Microsoft Office. It does not currently implement full OOXML round-tripping, page layout, advanced styles, charts, pivots, animations, comments, track changes, macros, external data connections, collaboration, or complete formula compatibility. Importing a real Office document may discard unsupported formatting. Generated packages pass the prototype's ZIP/XML and content round-trip tests; broad interoperability with Microsoft Office has not yet been certified.

## Security notes

- Keep the server on loopback; do not expose port 8765 to your LAN or the internet.
- Only open documents you trust. Imports are bounded by a 15 MiB upload limit and must be ZIP-based \`.docx\`, \`.xlsx\`, or \`.pptx\` packages.
- Never use this prototype as a safe viewer for untrusted Office files until it has undergone a security review and malicious-document fuzzing.
