# Clean Snapshot Release Pipeline & Repository Sanitization

This plan establishes a repeatable, automated pipeline to export sanitized releases of the `ancestry-genealogy` project into the secondary local repository (`~/github/beattidp/ancestry-org-genealogy`), dedicated to public GitHub publication on the `trunk` branch, while completely eliminating PII and real FamilySearch user/person identifiers using `ABCD-123` (HTTP 404 test identifier).

## User Review Required

> [!IMPORTANT]
> **Scope of Exported Documentation:**
> The clean snapshot will export all application code (`src/`), unit tests (`tests/`), CLI tools, project configurations (`README.md`, `requirements.txt`, etc.), and feature architecture specifications (`doc/features/`).
> Internal activity records (`doc/worklogs/`), draft implementation plans (`doc/plans/`), and agent execution transcripts (`doc/walkthroughs/`) will be omitted from the public export by default.

> [!NOTE]
> **Dummy Identifier Selection:**
> As requested, all occurrences of the live root person PID (`KWHS-6NN`) will be replaced with `ABCD-123` (which reliably produces a 404 on FamilySearch), and account identifiers (`cis.user.MM9W-QYW8`) and personal names will be replaced with generic placeholders (`cis.user.SAMPLE-USER` and `Sample User`).

## Proposed Changes

### 1. Codebase Sanitization (Source Repository)

Sanitize the source repository so that core CLI help text and feature documentation no longer contain live personal identifiers.

#### [MODIFY] [ingest.py](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/ingest.py)
* Replace `KWHS-6NN` with `ABCD-123` in argument parser help text.

#### [MODIFY] [doc/features/pedigree_ingestion_sqlite.md](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/doc/features/pedigree_ingestion_sqlite.md)
* Replace `KWHS-6NN` with `ABCD-123` and `Douglas Paul Beattie Jr` with `Sample User`.

#### [MODIFY] [doc/features/familysearch_api_client.md](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/doc/features/familysearch_api_client.md)
* Replace `cis.user.MM9W-QYW8` with `cis.user.SAMPLE-USER`, `KWHS-6NN` with `ABCD-123`, and personal names with generic sample user text.

---

### 2. Clean Snapshot Export Pipeline

#### [NEW] [scripts/export_clean.py](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/scripts/export_clean.py)
Create a standalone Python script to execute the sanitization, export, verification, and staging in the secondary repository:
1. **Target Directory:** Defaults to `/home/beattidp/github/beattidp/ancestry-org-genealogy`.
2. **Branch Management:** Checks out or creates branch `trunk`.
3. **White-listed Files & Folders:**
   - Code: `src/`, `tests/`
   - Entrypoints & Tools: `ingest.py`, `probe.py`, `tree_summary.py`, `validate_tree.py`, `audit_sources.py`
   - Project Root: `README.md`, `requirements.txt`, `pytest.ini`, `.python-version`, `.env.example`, `.gitignore`
   - Documentation: `doc/features/` (sanitized)
4. **Automated Redaction Engine:**
   - Applies regex substitutions defined in a configurable redaction dictionary (PIDs $\rightarrow$ `ABCD-123`, User IDs $\rightarrow$ `cis.user.SAMPLE-USER`, names $\rightarrow$ `Sample User`).
5. **Pre-commit Security Guard (Fail-Safe):**
   - Scans the entire target staging tree for sensitive patterns (`MM9W`, `Beattie`, `KWHS`, or live user tokens).
   - Aborts immediately if any sensitive pattern is detected.
6. **Git Commit & Tag:**
   - Stages changes (`git add -A`) in the target repo on branch `trunk`.
   - Creates a clean snapshot commit with the current release version (e.g. `v0.6.0`).

---

### 3. Documentation & Worklog Updates (Project Rules)

#### [NEW] [doc/features/clean_snapshot_pipeline.md](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/doc/features/clean_snapshot_pipeline.md)
* Comprehensive documentation of the public release architecture, redaction rules, security guards, and verification steps.

#### [NEW] [doc/worklogs/2026-10-27-clean-snapshot-pipeline.md](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/doc/worklogs/2026-10-27-clean-snapshot-pipeline.md)
* Detailed worklog capturing the rationale, design, changes, and verification.

---

## Verification Plan

### Automated Tests
1. **Source Code Test Suite:**
   - Run `pytest` to ensure all existing tests pass with the sanitized CLI options:
     ```bash
     python -m pytest -v
     ```
2. **Export Pipeline Execution:**
   - Run `python scripts/export_clean.py` targeting `/home/beattidp/github/beattidp/ancestry-org-genealogy`.
3. **Destination PII Scanner:**
   - Execute regex search on the destination directory to verify zero leaked patterns:
     ```bash
     grep -E -Is -rn "MM9W|Beattie|KWHS" /home/beattidp/github/beattidp/ancestry-org-genealogy
     ```
4. **Destination Test Suite:**
   - Run pytest inside `/home/beattidp/github/beattidp/ancestry-org-genealogy` to verify the exported repo is fully self-contained and passes tests:
     ```bash
     cd /home/beattidp/github/beattidp/ancestry-org-genealogy && python -m pytest -v
     ```
