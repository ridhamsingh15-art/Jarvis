# Security Policy

JARVIS AIOS is an actively developed prototype. Do not assume it is suitable for unattended or high-impact use.

## Reporting a vulnerability

Please do not publish exploit details, credentials, tokens, cookies, private logs, or a working exploit in a public issue. Use GitHub's **private vulnerability reporting / security advisory** feature for this repository if it is enabled. If private reporting is unavailable, contact the repository maintainer privately through a verified channel before sharing exploit details.

Include the affected component, impact, prerequisites, reproduction steps, and a proposed mitigation if known. Redact secrets and personal data.

## Scope priorities

Security reports are especially valuable for:
- arbitrary command or code execution;
- escaping configured filesystem boundaries;
- bypassing desktop action approval;
- authentication, authorization, or token-validation flaws in MCP/federation;
- secret exposure in logs, traces, prompts, or reports;
- unsafe model/tool output handling;
- dependency or supply-chain compromise.

## Current limitations

The project has not completed an independent security audit, signed release process, full dependency vulnerability review, or production threat-model validation. Local approval dialogs and unit tests reduce specific risks but do not guarantee safety. Keep remote endpoints disabled unless explicitly configured and protected, use least-privilege credentials, and never approve unexpected desktop actions.
