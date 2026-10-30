# W09 Literature Evidence Desk

A runnable, local Python prototype for extracting study information, healthcare resource utilization (HRU), and cost outcomes from public RWE/HEOR papers. This is a **technical feasibility prototype**, not a validated systematic review service or evidence of time savings.

## Start locally

Requires Python 3.10 or newer. From this directory:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python app.py
```

On Windows, activate with `.venv\Scripts\activate` in Command Prompt, or `.venv\Scripts\Activate.ps1` in PowerShell. If your Python command is `python3`, substitute it for `python`.

Open **http://127.0.0.1:8501**. Click **Try synthetic demo · no key** to exercise the complete interface using a clearly labeled fictional two-page paper. The demo does not call AI or simulate measured model performance.

## Extract real public papers

Set your own API credentials in the same terminal before starting the server:

```bash
export OPENAI_API_KEY="YOUR_API_KEY"
export OPENAI_MODEL="gpt-4.1-mini"
python app.py
```

PowerShell:

```powershell
$env:OPENAI_API_KEY="YOUR_API_KEY"
$env:OPENAI_MODEL="gpt-4.1-mini"
python app.py
```

The model field is editable. Use an available model supporting the Responses API and strict structured outputs; model access and API billing depend on your account. `.env.example` documents the variables but is **not automatically loaded**. Keep credentials out of source control.

1. Upload 1–5 public, text-based PDFs.
2. Confirm sending their extracted page text to the model API and click **Extract selected PDFs**.
3. Inspect **Study information** and **HRU & cost outcomes**. Every generated row starts unapproved.
4. Click **Page N / Inspect** to see the original page image, source quote and extracted page text.
5. Edit the value directly. Edit group, unit, currency, price year, observation period, page or quotation in the right panel and click **Apply context edits**. Then choose the review status.
6. Download the **Excel evidence table** and **JSON audit** before closing the tab or restarting. Edits do not persist across reloads; server runs are memory-only and only the five latest runs are kept.

Each paper is processed independently; one failed file does not discard the other papers. Retries are explicit and can incur additional API costs. A batch of five papers can take several minutes. Export once all selected papers have finished.

## Evidence structure

- Study information: study design, data source, population, sample size, treatment, comparator and follow-up.
- Outcomes: separate rows for each HRU/cost metric, group, statistic and observation period. Values are retained as source strings rather than calculated or currency-converted.
- Every row retains paper ID, PDF page, verbatim source quote, review status and reviewer note.
- Quote checks normalize Unicode, whitespace and case, then match against the **stated PDF page**. They are location checks, not semantic correctness checks. A quoted background study or wrong treatment group still needs human judgment.
- Missing study fields are explicit rows with empty values. “Not reported” means the extractor did not find a value; a reviewer must check whether the paper actually omits it.
- Missing outcome units, periods and groups are flagged; costs without currency are also flagged. A missing price year remains empty for review.
- Editing a value or its context returns the row to **Needs review**. Validation is recalculated on export. Approved rows with remaining warnings are exported with those warnings, not silently discarded.

Excel sheets: **Study information**, **Outcomes**, **Audit edits**, **Run metadata**. String cells are explicitly stored as text, including strings beginning with `=`, to avoid spreadsheet formula execution. JSON includes original model/fixture output, reviewed rows, changes, model usage, API wall time and prompt version. API time is **not** human labor time. Edit audit is the final difference from original output, not a chronological keystroke history.

## Scope and known limitations

- 15 MB / PDF, 60 pages / PDF, 180,000 extracted characters / PDF. Oversized input is rejected, never silently truncated.
- Scanned/encrypted PDFs are rejected. No OCR, figure interpretation or dedicated table reconstruction. Mixed image/text pages may omit critical content; inspect original pages. Plain-text extraction may scramble multi-column tables.
- One structured extraction request per paper. A long or outcome-heavy paper can exceed the model's output capacity; incomplete/refused/malformed responses are rejected.
- This version does not screen literature, search databases, deduplicate studies across PDFs, assess risk of bias, pool results, or build a vector database.
- The app binds to loopback only and does not write PDFs or keys to disk. Uploaded text goes to OpenAI **only** when extraction is requested; synthetic demo and export work locally. `store: false` is sent, but provider data-handling policies still apply. Use only public papers in this prototype.
- No multi-user authentication or production hosting. Do not expose this development server publicly. Review PyMuPDF's licensing before distributing or commercializing derivative software.

## Development and validation

```bash
python -m unittest -v
```

Tests cover synthetic source traceability, multiple treatment groups, page/quote mismatch, missing metadata, scanned/malformed PDFs, missing fields, edits/audit, Excel text cells, and mocked structured API success/incomplete/refusal responses. Frontend JavaScript passed a syntax check. A real-browser interaction/layout test could not run in the build environment because the browser binary download failed. Real model accuracy and end-to-end API connectivity require a user-configured API key and an independent 3–5-paper development exercise.

Suggested next exercise: choose a simple paper, a table-heavy paper, and a paper with several treatment groups/time windows. Record parsing failures, field errors, reviewer corrections and API usage. These are development examples, not a held-out evaluation set.

## Files

- `app.py`: loopback server, uploads, source preview and exports.
- `core.py`: parsing, API extraction, validation, synthetic fixture and Excel generation.
- `ui.html`: editable evidence desk; no frontend build step or CDN dependency.
- `test_core.py`, `test_app.py`: 13 core and HTTP integration tests; standard-library unittest.
- `requirements.txt`, `.env.example`: dependencies and configuration.

## Official implementation references

- [OpenAI structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
- [PyMuPDF text extraction](https://pymupdf.readthedocs.io/en/latest/recipes-text.html)
- [openpyxl workbook tutorial](https://openpyxl.readthedocs.io/en/stable/tutorial.html)
