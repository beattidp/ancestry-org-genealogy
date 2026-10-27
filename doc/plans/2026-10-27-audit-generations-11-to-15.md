# Implementation Plan: Source Auditing of Generations 11–15

Audit attached sources and calculate Genealogical Proof Standard (GPS) confidence scores across the 2,061 newly expanded deep ancestors in Generations 11 through 15 (1400s–1600s), enhancing classification for early modern and medieval record types (parish registers, heraldic visitations, chancery/probate records, and published peerages).

## User Review Required

> [!NOTE]
> **Scale of Ingestion**: There are 2,061 ancestors across Generations 11–15:
> - Generation 11 (9th Great-Grandparents): 214 ancestors
> - Generation 12 (10th Great-Grandparents): 306 ancestors
> - Generation 13 (11th Great-Grandparents): 399 ancestors
> - Generation 14 (12th Great-Grandparents): 491 ancestors
> - Generation 15 (13th Great-Grandparents): 651 ancestors
> 
> With polite API throttling (~0.06s delay per query), fetching attached sources across all 2,061 ancestors will take approximately 2–3 minutes.
> 
> We will add a `--min-gen` CLI argument to [audit_sources.py](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/audit_sources.py) so you can audit the entire Gen 11–15 range in one run, or audit generation-by-generation (e.g. `--min-gen 11 --max-gen 11`).

## Open Questions

None currently. The architecture easily extends the existing incremental auditing engine.

---

## Proposed Changes

### Source Classification Layer

#### [MODIFY] [classifier.py](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/src/audit/classifier.py)
* Add recognition for early modern and medieval British, Scottish, and French historical records:
  * **Tier 1 (Primary Documentary Evidence)**:
    * Parish registers & church records: `parish register`, `parish record`, `church record`, `banns`, `kirk session`
    * Inquisitions & Manorial: `inquisition post mortem`, `ipm`, `court roll`, `manorial`, `feet of fines`
    * Chancery & Wills: `prerogative court of canterbury`, `chancery proceedings`, `testament dative`
  * **Tier 2 (Secondary / Published Derivative)**:
    * Heralds' Visitations: `visitation of`, `visitations of`, `heraldic visitation`, `pedigrees of`
    * Peerages & Gentry: `peerage`, `baronetage`, `cokayne`, `burke's`
    * Academic Registers: `alumni cantabrigienses`, `alumni oxonienses`
    * Town & County Histories: `county history`, `history and antiquities`

---

### Storage Layer

#### [MODIFY] [db.py](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/src/storage/db.py)
* Update `get_audit_scores` and `get_audit_summary` to accept `min_generation: int | None = None` alongside `max_generation`.
* Add `get_audited_person_pids() -> set[str]` to track which ancestors have already been audited. This ensures ancestors who have 0 attached sources in FamilySearch are not repeatedly re-queried during incremental fetching.

---

### Audit Engine Layer

#### [MODIFY] [auditor.py](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/src/audit/auditor.py)
* Add `min_generation: int | None = None` to `audit_pedigree`.
* Integrate `get_audited_person_pids()` into `audit_pedigree` to cleanly bypass API queries for all previously audited ancestors (both sourced and unsourced).

---

### CLI Interface

#### [MODIFY] [audit_sources.py](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/audit_sources.py)
* Add `--min-gen` CLI argument (integer, default `None`).
* Forward `min_generation` to `auditor.audit_pedigree`, `db.get_audit_summary`, and `db.get_audit_scores`.
* Update table headers and panels to display the active generational range (e.g. `Generations 11 to 15`).

---

### Tests

#### [MODIFY] [test_audit.py](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/tests/test_audit.py)
* Add unit test for medieval / early modern record classification (Heralds' Visitations, Parish Registers, IPMs).
* Add unit test for `min_generation` scoping in `audit_pedigree` and `get_audit_summary`.

---

## Verification Plan

### Automated Tests
1. Run audit unit tests:
   ```bash
   pytest tests/test_audit.py
   ```
2. Run full test suite:
   ```bash
   pytest
   ```

### Live Verification
1. Run live audit on Generations 11 through 15:
   ```bash
   python audit_sources.py --db data/pedigree.sqlite --fetch --min-gen 11 --max-gen 15
   ```
2. Inspect the Generational Evidence Verification Matrix for Generations 11 to 15:
   - Verify Birth %, Death %, Parentage %, and Average Confidence scores.
3. Inspect Priority Evidentiary Deficits table for deep lineage target lines.
