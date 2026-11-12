---
name: mathdoc
summary: Local, auditable Markdown/LaTeX to DOCX with native OMML equations
---

# MathDoc — Agent Skill

Use this when asked to convert Markdown / LaTeX to a Word document preserving native editable equations. Never paste raw OMML XML directly into Word and claim it will become an editable equation.

## Workflow

1. Obtain Markdown from the user or task and save it as UTF-8 `.md`; keep mathematical meaning unmodified.
2. Validate that Pandoc is installed (`pandoc --version`).
3. Convert: `python mathdoc_cli.py convert input.md -o output.docx` (run from project folder).
4. Audit: `python mathdoc_cli.py audit output.docx`.
5. For important research deliverables, render the document in Word or LibreOffice, review formula layout, headings and tables, then deliver.
6. If any equation is unsupported or input is ambiguous, report precisely rather than silently rewriting it.

## Interface

For interactive editing or provider-key configuration, run `python launch.py` and open localhost port 8765.

## Limits

- MathType mode copies LaTeX for MathType input; it does not create proprietary MathType OLE objects.
- Browser HTML clipboard paste fidelity depends on Word version. A `.docx` file is the reliable OMML artifact.
- Images embedded in untrusted Markdown are deliberately omitted to prevent unauthorized file access.
- Do not copy API keys into Markdown, logs, generated DOCX, or git commits.
