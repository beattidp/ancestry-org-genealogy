# Worklog: Clean Snapshot Pipeline & Repository Sanitization

* **Date:** 2026-10-27
* **Time:** 15:50:00-06:00
* **Agent:** Antigravity (Gemini 3.8 Flash High)
* **User:** Douglas Paul Beattie Jr (`KWHS-6NN`)

---

## 1. Objectives & Scope
* Eliminate potential exposure of PII (developer names, internal FamilySearch user IDs `MM9W-QYW8`, and root tree PID `KWHS-6NN`).
* Implement a clean snapshot release workflow exporting code, tests, and feature documentation to the secondary local repository (`~/github/beattidp/ancestry-org-genealogy`) on branch `trunk`.
* Replace root PID references with `ABCD-123` (guaranteed FamilySearch 404 response).
* Implement automated security guard to block any export containing sensitive tokens.

---

## 2. Actions & Changes

### A. Source Code Sanitization
1. **`ingest.py`**:
   * Updated argument parser CLI help to use `ABCD-123` instead of `KWHS-6NN`.
2. **`doc/features/pedigree_ingestion_sqlite.md` & `doc/features/familysearch_api_client.md`**:
   * Replaced references to live personal IDs and names with `ABCD-123`, `cis.user.SAMPLE-USER`, and `Sample User`.

### B. Clean Snapshot Pipeline Implementation
1. **`scripts/export_clean.py`**:
   * Created automated export script supporting:
     * Synchronized file copying for `src/`, `tests/`, `doc/features/`, and root tools/configs.
     * Automated redaction engine using compiled regex replacements.
     * Pre-commit security guard scanning for `MM9W`, `Beattie`, and `KWHS`.
     * Git branch management for branch `trunk` with automatic safe GitHub noreply committer config.

### C. Execution & Target Verification
1. Ran `python scripts/export_clean.py`:
   * Exported clean tree to `/home/beattidp/github/beattidp/ancestry-org-genealogy`.
   * Security guard validated 0 sensitive matches.
   * Committed clean snapshot on branch `trunk` (`c8b6653`).
2. Ran unit tests in destination repository:
   * 37 passed in 2.78s.
3. Ran regex scan on destination repository:
   * 0 matches found for any sensitive patterns.

---

## 3. Verification Commands & Results
* **Source Tests:** `python -m pytest -v` $\rightarrow$ 37 passed.
* **Target Tests:** `cd ~/github/beattidp/ancestry-org-genealogy && python -m pytest -v` $\rightarrow$ 37 passed.
* **Target Security Scan:** `grep -E -Is -rn "MM9W|Beattie|KWHS" ~/github/beattidp/ancestry-org-genealogy` $\rightarrow$ Clean (0 matches).
* **Target Git Status:** Clean on branch `trunk`.
