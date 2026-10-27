# Feature: Incremental Source & Citation Audit & 15-Generation Frontier Expansion

## 1. Overview
This feature delivers two major capabilities for deep, evidence-grounded genealogical research:
1. **Incremental Source & Citation Audit**: Resumable and generational-scoped source fetching and evidence classification conforming to the Genealogical Proof Standard (GPS), with evidence tiering (Tiers 1, 2, and 3), proof verification checks (Birth, Death, Parentage), and confidence scoring.
2. **15-Generation Recursive Frontier Expansion**: Scalable iterative expansion of leaf frontier ancestors across arbitrary generation limits, expanding beyond the single-call FamilySearch limit (8 generations) up to 15 generations ($2^{15} = 32,768$ slots) while calculating global Ahnentafel ascendancy numbers and lineage paths.

---

## 2. Architecture & Design

### Incremental & Scoped Source Auditing
* **Resumability**: `SourceAuditor.audit_pedigree` accepts `only_missing=True` and `refresh=False`. It checks `Database.has_person_sources(pid)` to determine whether attached sources are already cached in `person_sources`. If present, network calls are bypassed, allowing rapid re-scoring and resumption after interruptions.
* **Generational Scoping**: Both `SourceAuditor.audit_pedigree` and CLI `audit_sources.py` accept `--max-gen`, allowing focused auditing of specific ancestral tiers (e.g. Generations 0–5 or Generations 0–10).
* **Summary and Scoring Filtering**: `Database.get_audit_scores` and `Database.get_audit_summary` filter by `max_generation` to render metrics corresponding to the requested scope.

### Iterative Frontier Expansion
* **Multi-Step While Loop**: In `PedigreeIngester.ingest_ancestry`, expansion operates iteratively:
  1. Base platform ingestion fetches up to 7 generations from `root_pid` in a single query.
  2. The loop inspects the maximum generation in SQLite for `root_pid`.
  3. While `current_max_gen < target_max_gen`, it queries all leaf ancestors at `current_max_gen`.
  4. Computes step depth: `step_depth = min(target_max_gen - current_max_gen, 8)`.
  5. Fetches sub-pedigrees, computes global Ahnentafel numbers via `calculate_global_ahnentafel`, and batch-upserts persons, facts, pedigree nodes, and relationships.
  6. Automatically terminates if no new ancestors are returned (end of available tree in FamilySearch) or if `target_max_gen` is achieved.

---

## 3. Database Updates

* **`Database.has_person_sources(person_pid: str) -> bool`**: Efficient indexed check (`SELECT 1 FROM person_sources WHERE person_pid = ? LIMIT 1`) to determine whether sources exist for a person.
* **`Database.get_audit_scores(root_pid: str, max_generation: int | None = None) -> list[dict[str, Any]]`**: Filtered score retrieval by generational depth.
* **`Database.get_audit_summary(root_pid: str, max_generation: int | None = None) -> dict[str, Any]`**: Aggregate statistics restricted to requested generational depth.

---

## 4. CLI Utilities

### `audit_sources.py`
* `--max-gen <N>`: Restricts audit and summary rendering to generation $N$.
* `--refresh`: Forces re-downloading source descriptions for already-cached ancestors.
* Generational matrix displays labels up to Generation 15 (13th Great-Grandparents).

### `ingest.py`
* `--recursive-to <N>`: Supports deep recursive frontier expansion up to Generation 15+.
* Generational report table formatted up to Generation 15.

---

## 5. Live Execution Results

### Source & Citation Audit (10-Generation Baseline)
* **Total Audited**: 542 ancestors across Generations 0–10.
* **Confidence Distribution**:
  * **HIGH (80–100%)**: 173 ancestors (31.9%)
  * **MEDIUM (50–79%)**: 116 ancestors (21.4%)
  * **LOW (1–49%)**: 173 ancestors (31.9%)
  * **UNSOURCED (0%)**: 80 ancestors (14.8%)
  * **Average Confidence**: 53.0%
* **Generational Verification**:
  * Gen 2–3: 100% Birth, Death, and Parentage verified (100.0% confidence).
  * Gen 4: 100% Birth, 94% Death, 100% Parentage verified (98.9% confidence).
  * Gen 5: 88% Birth, 78% Death, 78% Parentage verified (84.8% confidence).
  * Gen 10: 55% Birth, 34% Death, 0% Parentage verified (frontier leaves).

### 15-Generation Frontier Expansion
* **Total Persisted Ancestors**: 2,603 ancestors (expanded from 545).
* **Total Relationships**: 4,237 relationships (expanded from 1,065).
* **Total Facts**: 10,021 facts (expanded from 2,845).
* **Generational Distribution**:
  * Gen 0: 1 (Self)
  * Gen 1: 3 (Parents)
  * Gen 2: 4 (Grandparents)
  * Gen 3: 8 (1st Great-Grandparents)
  * Gen 4: 16 (2nd Great-Grandparents)
  * Gen 5: 32 (3rd Great-Grandparents - 100% complete)
  * Gen 6: 51 (4th Great-Grandparents - 79.7%)
  * Gen 7: 56 (5th Great-Grandparents - 43.8%)
  * Gen 8: 85 (6th Great-Grandparents - 33.2%)
  * Gen 9: 123 (7th Great-Grandparents - 24.0%)
  * Gen 10: 163 (8th Great-Grandparents - 15.9%)
  * Gen 11: 214 (9th Great-Grandparents - 10.4%)
  * Gen 12: 306 (10th Great-Grandparents - 7.5%)
  * Gen 13: 399 (11th Great-Grandparents - 4.9%)
  * Gen 14: 491 (12th Great-Grandparents - 3.0%)
  * Gen 15: 651 (13th Great-Grandparents - 2.0%)
* **Earliest Ancestors Found**:
  * **Ralph Goody** (`LBZY-3G4`): Born 1 April 1420 in Hertfordshire, England (Generation 15).
  * **Pierre Duteil** (`G9CG-C85`): Born 1 April 1593 in Aubigny-sur-Nère, Cher, France (Generation 15).

### Deterministic Constraint Validation
* Evaluated all 2,603 ancestors across 15 generations.
* **Total Violations Detected**: 180 (125 errors, 54 warnings, 1 info).
* Cleanly caught crowdsourced anomalies across deep lines (maternal age $< 13$ or $> 50$, paternal age $< 14$, child born before parent, etc.).
