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
* **Whitelist-based synchronization:** Only approved directories and files are copied.
* **In-memory content transformation:** Performs regex substitution on all source code and markdown documents prior to writing.
* **Security Guard:** Scans destination files for forbidden user identifiers, surname patterns, and live PIDs.
* **Git Automation:** Configures branch `trunk`, carries over safe GitHub noreply committer identity, and creates clean release commits.

### 2. Dummy Identifier Standards
* **`ABCD-123`**: Chosen specifically as the dummy root PID because requests to FamilySearch for `ABCD-123` return `HTTP 404 Not Found`, ensuring no accidental correlation with live genealogical persons.
* **`cis.user.SAMPLE-USER`**: Standard placeholder for account-level user tokens.
* **`Sample User`**: Standard placeholder for developer/user display names.

---

## Usage

### Run Default Export
```bash
python scripts/export_clean.py
```

### Run with Custom Target Directory or Branch
```bash
python scripts/export_clean.py \
  --target-dir ~/github/beattidp/ancestry-org-genealogy \
  --branch trunk
```

### Dry Run (Stage files without committing)
```bash
python scripts/export_clean.py --no-commit
```

### Push to GitHub
Once the clean snapshot is verified:
```bash
cd ~/github/beattidp/ancestry-org-genealogy
git push -u origin trunk
```

---

## Verification & Metrics

* **Source Test Suite:** 37 passing unit tests in private repository (`pytest`).
* **Exported Test Suite:** 37 passing unit tests in destination repository (`pytest`).
* **Forbidden Pattern Scan:** 0 matches in target repository across all files.
* **Branch Isolation:** Destination branch `trunk` has an independent, clean commit history.
