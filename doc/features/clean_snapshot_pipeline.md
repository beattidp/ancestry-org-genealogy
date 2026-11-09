# Clean Snapshot Release Pipeline & Sanitization Engine

## Overview & Architecture

The **Clean Snapshot Release Pipeline** provides a secure, repeatable bridge between the private development repository (`ancestry-genealogy`) and the public-facing GitHub repository (`~/github/beattidp/ancestry-org-genealogy`). 

### Problem Addressed
A private development repository often contains:
1. Privileged internal identifiers (e.g. FamilySearch logged-in account IDs, internal user names).
2. Root person PIDs tied to living or sensitive tree profiles.
3. Internal AI interaction logs, draft plans, and raw diagnostic output.

Standard Git branching (e.g., branching `trunk` from `main` and committing file deletions) leaves historical commits accessible to anyone who clones the repository. The clean snapshot pipeline eliminates this by maintaining an isolated, sanitized git tree on branch `trunk` with zero historical leakage.

---

## Architecture & Security Pipeline

```
[ Private Source Repo ] (ancestry-genealogy)
          │
          ├──> 1. Whitelist Selection (src/, tests/, doc/features/, root tools)
          │    (Excludes doc/worklogs/, doc/plans/, doc/walkthroughs/, .env, *.sqlite)
          │
          ├──> 2. Automated Redaction Engine
          │    - Real Root PIDs -> ABCD-123 (FamilySearch 404 non-existent profile)
          │    - CIS User IDs  -> cis.user.SAMPLE-USER
          │    - User Names    -> Sample User / Sample Person
          │
          ├──> 3. Security Guard (Fail-Safe Pre-commit Regex Scanner)
          │    - Halts export immediately if ANY sensitive pattern is detected
          │
          └──> 4. Clean Snapshot Commit on Branch 'trunk'
               (Destination: ~/github/beattidp/ancestry-org-genealogy)
```

---

## Components

### 1. Script Entrypoint (`scripts/export_clean.py`)
* **Whitelist-based synchronization:** Only approved directories and files are copied (including all root CLI tools: `ingest.py`, `probe.py`, `validate_tree.py`, `tree_summary.py`, `audit_sources.py`, `export_gedcom.py`, `harvest_records.py`, `resolve_scottish_places.py`).
* **Pre-Checkout Branch Management:** Ensures target branch (`trunk`) is checked out before altering any working tree files.
* **In-memory content transformation:** Performs regex substitution on all source code and markdown documents prior to writing.
* **Security Guard (Step 4):** Scans destination files for forbidden user identifiers, surname patterns, and live PIDs.
* **Destination Test Suite Validation (Step 4b):** Automatically executes `pytest` inside the target directory before staging any changes.
* **Rollback Guard:** If the security scan or test suite fails, automatically restores the target repository via `git reset --hard HEAD` and `git clean -fd`, ensuring the destination git repository is never left dirty or indeterminate.
* **Git Automation (Step 5):** Configures branch `trunk`, carries over safe GitHub noreply committer identity, and creates clean release commits.

### 2. Dummy Identifier Standards
* **`ABCD-123`**: Chosen specifically as the dummy root PID because requests to FamilySearch for `ABCD-123` return `HTTP 404 Not Found`, ensuring no accidental correlation with live genealogical persons.
* **`cis.user.SAMPLE-USER`**: Standard placeholder for account-level user tokens.
* **`Sample User` / `Sample Ancestor`**: Standard placeholders for developer/user display names and ancestor leads.

### 3. Schema Revision & Database Template (`data/pedigree.sqlite`)
* **Empty Schema Template:** The destination repository tracks an empty `data/pedigree.sqlite` database containing the complete schema (10 tables, relational indexes, and constraint triggers) with 0 data rows.
* **Destination `.gitignore` Rule:** In the public repository, `.gitignore` is dynamically modified during export to ignore runtime databases while tracking the schema template:
  ```gitignore
  *.sqlite
  *.sqlite3
  *.db
  data/*
  !data/pedigree.sqlite
  cache/
  ```
* **Preservation & Idempotency:** The pipeline verifies the database via `Database.is_empty_schema()`. If `data/` or `data/pedigree.sqlite` does not exist, it is created automatically via `Database.create_empty_template()`. If an empty valid database already exists, it is preserved without altering git modification timestamps.

---

## Usage

### Run Default Export
```bash
python3 scripts/export_clean.py
```

### Run with Custom Target Directory or Branch
```bash
python3 scripts/export_clean.py \
  --target-dir ~/github/beattidp/ancestry-org-genealogy \
  --branch trunk
```

### Dry Run (Stage files without committing)
```bash
python3 scripts/export_clean.py --no-commit
```

### Push to GitHub
Once the clean snapshot is verified:
```bash
cd ~/github/beattidp/ancestry-org-genealogy
git push -u origin trunk
```

---

## Verification & Metrics

* **Source Test Suite:** 69 passing unit tests in private repository (`pytest`).
* **Exported Test Suite:** 69 passing unit tests in destination repository (`pytest`).
* **Forbidden Pattern Scan:** 0 matches in target repository across all files.
* **Database Verification:** `data/pedigree.sqlite` present with 0 data rows and 10 schema tables.
* **Branch Isolation:** Destination branch `trunk` has an independent, clean commit history.
* **Indeterminate State Prevention:** Automatic rollback restores clean HEAD state on any abort.
