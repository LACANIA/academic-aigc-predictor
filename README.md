# Academic AIGC Writing Risk Precheck for Codex

An unofficial research tool for English academic writing. Codex reads the manuscript and offers an uncalibrated estimate of possible Turnitin AI Writing behavior, a subjective range, and exact supporting passages. This tool does not reproduce a proprietary detector, identify actual AI authorship, or guarantee a formal score.

## Version and capabilities

`RC1-DOCX-PORTABLE-0.1.0`; Skill name: `academic-aigc-precheck-portable`.
Supports PDF, paired PDF+TeX, and DOCX. Mode B analyzes a new paper using permitted other-family references; mode A uses an explicitly supplied old report to analyze revisions. TeX is read statically; Word math is retained with interpretation warnings. Papers and reports are never edited automatically.

## Requirements and installation on Windows

Python >=3.11 and PyMuPDF >=1.24,<2. There is no detector API, extra model client, Word installation, or TeX compiler requirement. Codex supplies the language-model analysis. Create a dedicated Python virtual environment and install the declared requirements.

The release ZIP contains exactly 23 frozen files. Its SHA-256 is `5e0cb505f676fe93e19bfb406919c7cdf98ebac6392f91fda0966fd31a2ba5d5`. Verify this value before extraction. Read the packaged INSTALL_WINDOWS.md for detailed instructions and errors.

```powershell
py -3 -m venv <venv-dir>
<venv-dir>/Scripts/python.exe -m pip install -r <unpacked-skill>/requirements.txt
<python> <unpacked-skill>/manage.py check-bundle --bundle <release.zip>
<python> <unpacked-skill>/manage.py install --bundle <release.zip> --dest <user-home>/.agents/skills/academic-aigc-precheck-portable
<python> <installed-skill>/manage.py verify --dest <installed-skill>
<python> <installed-skill>/scripts/precheck.py doctor
```

Use a user-level installation for availability in other projects. If a same-named directory exists, verify and reuse identical contents, or back it up completely before selecting a fresh installation; do not overwrite user changes. This checkout also exposes the exact same Skill at project scope. Do not maintain conflicting versions at both scopes.

## Private knowledge is required separately

This repository and ZIP contain no private cases, private rules, manuscripts, or real reports. Copy config.example.json to a private location outside this repository and outside the installed Skill. Configure `schema_version=portable-knowledge-1`, an explicit local root, relative cases/rules paths, and their actual SHA-256 values. Optional known_titles/known_sources register family identity. Use only data you are authorized to access. A full prepare stops if this knowledge is absent or invalid; it does not silently substitute another scoring method. The original 35 cases and seven rules are not licensed or distributed here.

## Daily use

In Codex invoke `$academic-aigc-precheck-portable` with an explicit manuscript path, your Python environment and private knowledge config. Ask for a new PRECHECK_REPORT.md in a fresh private directory. Supply the corresponding TeX only when it matches the PDF; supply an old report explicitly for mode A. Never provide the latest result before prediction. The host confirms family identity before selecting references.

```powershell
<python> <installed-skill>/scripts/precheck.py prepare --docx <paper.docx> --family <confirmed-family> --knowledge <private-config.json> --output <new-input-dir>
<python> <installed-skill>/scripts/precheck.py prepare --pdf <paper.pdf> --family <confirmed-family> --knowledge <private-config.json> --output <new-input-dir>
<python> <installed-skill>/scripts/precheck.py prepare --pdf <paper.pdf> --tex <main.tex> --family <confirmed-family> --knowledge <private-config.json> --output <new-input-dir>
<python> <installed-skill>/scripts/precheck.py prepare --docx <paper.docx> --history <old-report.pdf> --family <confirmed-family> --knowledge <private-config.json> --output <new-input-dir>
<python> <installed-skill>/scripts/precheck.py finish --packet <new-input-dir>/model_input.json --prediction <host-output.json> --output <new-report-dir>
```

Prepare performs local parsing and reference selection. Codex then reads the full packet and protocol, saves its actual analysis, and invokes finish. Finish validates packet binding and quotations and renders the report; it does not infer a percentage by itself. No history is selected by scanning unrelated files.

## Verification boundaries

The frozen version has passed independent-directory import checks, PDF/DOCX/TeX input preparation, both modes, report rendering, invalid-input rejection, private-knowledge mounting, and local Codex discovery checks. These are engineering checks. Fully autonomous model-led operation across arbitrary installations and dependable cross-paper prediction accuracy remain unverified. Historical same-family outcomes do not establish general accuracy. Simulated results marked ENGINEERING_TEST_ONLY are format fixtures, never real predictions.

## Privacy, limitations and removal

Python operates on explicit local inputs without uploading them. A host LLM processes whatever paper text the user allows into its context; its service data policies still apply. Keep all knowledge configurations, papers, reports, generated packets and logs outside this repository. Do not remove genuine AI-use disclosures or use the estimate as an authorship finding. DOCX lacks reliable PDF page numbers, formulas may lose meaning in linear text, and PDF reading order or source-version mismatches can limit analysis.

```powershell
<python> <installed-skill>/manage.py verify --dest <installed-skill>
<python> <installed-skill>/manage.py uninstall --dest <installed-skill>
```

Uninstall removes only an unchanged managed Skill and leaves private knowledge and reports intact. Keep a backup if you modify installed files. This private repository has no assigned open-source license. This release is for Codex; DSH configuration is outside this deployment.
