# Walkthrough: Source Audit & 15-Generation Frontier Expansion

## Overview
In this iteration, we implemented:
1. Incremental and generational-scoped source auditing in `src/audit/auditor.py`, `src/storage/db.py`, and `audit_sources.py`.
2. Scalable multi-round iterative frontier expansion up to Generation 15 in `src/pedigree/ingest.py` and `ingest.py`.
3. Executed live audits on the expanded 10-generation tree (542 ancestors).
4. Executed live recursive expansion from Generation 10 to Generation 15, expanding the tree to **2,603 ancestors**, **4,237 relationships**, and **10,021 facts**.
5. Validated biological and chronological integrity across all 15 generations using the constraint engine.

---

## Changes Implemented

### 1. Incremental and Scoped Source Auditing
- **`src/storage/db.py`**:
  - Added `has_person_sources(self, person_pid: str) -> bool` using an indexed lookup on `person_sources`.
  - Added `max_generation` parameter to `get_audit_scores` and `get_audit_summary`.
- **`src/audit/auditor.py`**:
  - Updated `audit_pedigree` with `only_missing: bool = True`, `refresh: bool = False`, and `max_generation: int | None = None`.
  - Skips API requests for ancestors who already have sources in `person_sources` unless `refresh=True`.
- **`audit_sources.py`**:
  - Added CLI options `--max-gen` and `--refresh`.
  - Expanded generational summary table to support up to Generation 15.

### 2. Scalable 15-Generation Recursive Frontier Expansion
- **`src/pedigree/ingest.py`**:
  - Implemented iterative `while True:` loop in `PedigreeIngester.ingest_ancestry`.
  - Dynamically detects the maximum generation in SQLite for `root_pid`.
  - Expands leaf ancestors in batches of up to 8 generations per call (`step_depth = min(target_max_gen - current_max_gen, 8)`).
  - Translates sub-pedigree relative coordinates into global Ahnentafel numbers up to $A_{max} = 32,767$.
- **`ingest.py` & `tree_summary.py`**:
  - Updated `gen_labels` to format up to Generation 15 (13th Great-Grandparents).
  - Extended reporting tables for up to 15 generations.

---

## Verification & Live Results

### 1. Automated Tests
Executed full test suite:
```bash
pytest
```
**Result**: 37/37 tests passed.

### 2. Live Source & Citation Audit
Executed incremental audit across the 10-generation tree:
```bash
python audit_sources.py --db data/pedigree.sqlite --fetch
```
**Results**:
- **Total Audited**: 542 ancestors
- **Average Pedigree Confidence Score**: 53.0%
- **GPS Evidence Distribution**:
  - **HIGH (80-100%)**: 173 (31.9%)
  - **MEDIUM (50-79%)**: 116 (21.4%)
  - **LOW (1-49%)**: 173 (31.9%)
  - **UNSOURCED (0%)**: 80 (14.8%)
- **Generational Verification**:
  - Gen 2–3: 100% Birth, Death, and Parentage verified (100.0% confidence)
  - Gen 4: 100% Birth, 94% Death, 100% Parentage verified (98.9% confidence)
  - Gen 5: 88% Birth, 78% Death, 78% Parentage verified (84.8% confidence)

### 3. Live 15-Generation Expansion
Executed recursive expansion from Generation 10 to 15:
```bash
python ingest.py --recursive-to 15 --db data/pedigree.sqlite
```
**Results**:
- **Total Persisted Ancestors**: 2,603 (from 545)
- **Total Relationships**: 4,237 (from 1,065)
- **Total Facts**: 10,021 (from 2,845)
- **Deepest Discovered Ancestor**: **Ralph Goody** (`LBZY-3G4`), born 1 April 1420 in Hertfordshire, England (Generation 15).

### 4. Constraint Validation
Executed biological and chronological constraint checks across all 2,603 ancestors:
```bash
python validate_tree.py --db data/pedigree.sqlite --persist
```
**Results**:
- 180 total violations persisted (125 errors, 54 warnings, 1 info).
- 10 relationship inversions caught (e.g. child born before parent due to crowdsourced entry errors).
- 74 maternal age violations caught (e.g. mother $<13$ or $>50$).
- Over 95% of parent-child relationships across 15 generations adhere to biological plausibility.
