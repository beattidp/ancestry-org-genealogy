# Walkthrough: Clean Snapshot Release Pipeline & Repository Sanitization

This walkthrough documents the successful implementation and execution of the **Clean Snapshot Release Pipeline**, providing an automated, leak-proof mechanism to export sanitized releases of `ancestry-genealogy` to the secondary repository on branch `trunk`.

---

## 1. Key Accomplishments

1. **Root PID Sanitization (`ABCD-123`):**
   - Updated [ingest.py:L34](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/ingest.py#L34) CLI argument parser help text to use `ABCD-123` (FamilySearch HTTP 404 test identifier).
   - Sanitized [pedigree_ingestion_sqlite.md](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/doc/features/pedigree_ingestion_sqlite.md) and [familysearch_api_client.md](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/doc/features/familysearch_api_client.md) to replace live PIDs and account tokens with generic placeholders (`ABCD-123`, `cis.user.SAMPLE-USER`, `Sample User`).
2. **Automated Export & Sanitization Engine:**
   - Implemented [scripts/export_clean.py](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/scripts/export_clean.py) with automated whitelist copying, regex redaction, fail-safe security scanner, and Git branch management on `trunk`.
3. **Target Repository Staging & Verification:**
   - Exported clean release snapshot to `/home/beattidp/github/beattidp/ancestry-org-genealogy`.
   - Verified that all 37 automated tests pass in the destination repository.
   - Verified that forbidden patterns (`MM9W`, `Beattie`, `KWHS`) return **zero matches**.
   - Created clean release commit `c8b6653` on branch `trunk`.

---

## 2. Export Pipeline Execution

Running the pipeline script performs a synchronized export and audit:

```bash
$ python scripts/export_clean.py
============================================================
Ancestry Genealogy - Clean Release Snapshot Pipeline
============================================================
Source Directory: /home/beattidp/Documents/antigravity/ancestry-genealogy
Target Directory: /home/beattidp/github/beattidp/ancestry-org-genealogy
Target Branch:    trunk

[Step 1/5] Synchronizing file tree...

[Step 2/5] Copying and sanitizing root files...
  + README.md
  + requirements.txt
  + pytest.ini
  + .python-version
  + .env.example
  + .gitignore
  + audit_sources.py
  + ingest.py
  + probe.py
  + tree_summary.py
  + validate_tree.py

[Step 3/5] Copying and sanitizing directory trees...
  Directory: src/
  Directory: tests/
  Directory: doc/features/

[Step 4/5] Running Security Guard verification scan...
  [PASS] Zero sensitive patterns found in exported tree.

[Step 5/5] Managing git branch 'trunk' in target repository...
  [SUCCESS] Created clean release commit on branch 'trunk':
    c8b6653 chore(release): export clean snapshot v0.6.0-15gen-audit

============================================================
Clean export completed successfully!
Target repository is ready at: /home/beattidp/github/beattidp/ancestry-org-genealogy
Branch: trunk
To push to GitHub:
  cd /home/beattidp/github/beattidp/ancestry-org-genealogy
  git push -u origin trunk
============================================================
```

---

## 3. Verification & Security Validation

### A. Destination Repository Test Suite
```bash
$ cd /home/beattidp/github/beattidp/ancestry-org-genealogy && python -m pytest -v
============================== 37 passed in 2.78s ==============================
```

### B. Destination PII Scan
```bash
$ grep -E -Is -rn "MM9W|Beattie|KWHS" /home/beattidp/github/beattidp/ancestry-org-genealogy
(0 matches found - CLEAN)
```

### C. Destination Git State
```bash
$ cd /home/beattidp/github/beattidp/ancestry-org-genealogy && git log -n 1
commit c8b6653ff47132c2c4ef1ca21b7fe3e3efdd6f86 (HEAD -> trunk)
Author: beattidp <5289980+beattidp@users.noreply.github.com>
Date:   Tue Oct 27 15:50:03 2026 -0600

    chore(release): export clean snapshot v0.6.0-15gen-audit
    
    Sanitized public release tree:
    - Core pedigree ingestion and SQLite database
    - Deterministic biological & chronological constraint validation engine
    - Source citation tier classification and completeness auditor
    - Automated redactions (ABCD-123 root dummy PID)
    - Full unit test suite
```

---

## 4. How to Push to GitHub

When ready to publish upstream to GitHub, run:

```bash
cd /home/beattidp/github/beattidp/ancestry-org-genealogy
git push -u origin trunk
```
