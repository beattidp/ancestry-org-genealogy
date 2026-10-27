# Source & Citation Audit (10 Gen) & Frontier Expansion to 15 Generations

This plan addresses:
1. **Source & Citation Audit:** Executing evidence classification, GPS confidence scoring, and deficit identification across the expanded 10-generation tree (545 ancestors).
2. **Expansion to 15 Generations:** Iteratively pushing the frontier from Generation 10 to Generation 15 (or maximum available depth in FamilySearch).

---

## 1. Architectural Strategy

### Phase 1: High-Efficiency Source & Citation Auditor
* **Current State:** 545 ancestors in SQLite; 32 audited (Generations 0–4); 513 unaudited (Generations 5–10).
* **Incremental / Resumable Fetching:**
  * Update `SourceAuditor.audit_pedigree` to check whether an ancestor already has sources in `person_sources`. If already present, skips network fetch unless `--refresh` is explicitly requested.
  * Avoids redundant API calls and makes large-scale audits fully resumable.
* **Generational Scoping:**
  * Support `--max-gen` and `--generation` flags in `audit_sources.py` (e.g. audit Generations 0–7 first, or all 10 generations).
* **Evidentiary Breakdown:**
  * Produce the GPS Evidence Verification Matrix across all active generations (Birth %, Death %, Parentage %, Avg Confidence %).
  * Identify specific evidentiary deficits for Generations 5 through 10.

### Phase 2: Frontier Expansion to 15 Generations
* **Current Frontier:** 163 leaf ancestors at Generation 10.
* **Probing Insight:** Testing sample Gen 10 ancestors revealed deep lines (e.g. `John Buck LHKN-QL3` has 29 ancestors beyond Gen 10, extending into the 1500s and 1400s).
* **Iterative Deep Ingestion:**
  * Ingest sub-pedigrees from the 163 Gen 10 leaf nodes for up to 5 additional generations (`generations=5`), reaching Generation 15 ($2^{15} = 32,768$ potential slots).
  * Automatically stop along branches that terminate before Generation 15.
  * Map global Ahnentafel numbers up to $A_{max} = 32,767$ using `calculate_global_ahnentafel`.
  * Batch-upsert all newly discovered ancestors, facts, and parent-child relationships into SQLite.

---

## 2. Proposed Changes

### Audit Layer
#### [MODIFY] [src/audit/auditor.py](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/src/audit/auditor.py)
* Add `only_missing: bool = True` to `audit_pedigree`:
  * Checks `SELECT count(*) FROM person_sources WHERE person_pid = ?`. If $> 0$ and `not refresh`, skips API call and directly evaluates cached sources.
* Add `max_generation: int | None = None` to filter pedigree scope.

#### [MODIFY] [audit_sources.py](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/audit_sources.py)
* Add `--max-gen` flag (e.g. `--max-gen 7` or `--max-gen 10`).
* Add `--refresh` flag to force re-downloading sources for already-fetched ancestors.
* Expand generational matrix rendering up to Generation 15.

### Pedigree Ingestion Layer
#### [MODIFY] [src/pedigree/ingest.py](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/src/pedigree/ingest.py)
* Generalize frontier expansion:
  * Instead of expanding only from Gen 7, expand from the highest available leaf generation in SQLite (e.g. Gen 10 leaves to Gen 15).
  * Handle multi-step expansion if requested depth $> 8$ generations beyond frontier.

#### [MODIFY] [ingest.py](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/ingest.py)
* Support `--recursive-to 15` from CLI.

---

## 3. Verification Plan

### Phase 1 Verification (Source Audit)
1. Run incremental audit on existing 10-generation tree:
   ```bash
   python audit_sources.py --db data/pedigree.sqlite --fetch
   ```
2. Inspect GPS confidence score distribution and generational verification matrix.
3. Verify test suite passes (`pytest`).

### Phase 2 Verification (15-Generation Expansion)
1. Run recursive expansion from Generation 10 to 15:
   ```bash
   python ingest.py --recursive-to 15 --db data/pedigree.sqlite
   ```
2. Inspect expanded tree summary:
   ```bash
   python tree_summary.py --db data/pedigree.sqlite
   ```
3. Run constraint validator across the expanded tree:
   ```bash
   python validate_tree.py --db data/pedigree.sqlite
   ```
