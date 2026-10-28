# Worklog: Source Auditing of Generations 11 to 15

* **Date:** 2026-10-27
* **Time:** 18:19 MDT
* **Agent:** Antigravity
* **User:** Douglas Paul Beattie Jr (`KWHS-6NN`)

---

## Summary of Actions

1. **Source Classifier Enhancements**:
   - Updated `SourceClassifier` in `src/audit/classifier.py` with regex patterns for early modern British, Scottish, and French record types:
     - Tier 1: `parish_register` (parish registers, church records, kirk sessions), `vital_marriage` (banns, allegations, bonds), `probate` (inquisitions post mortem, court of rolls, prerogative court wills).
     - Tier 2: `heraldic_visitation` (Heralds' Visitations), `peerage` (Cokayne, Burke's, Landed Gentry), university alumni registers (`alumni cantabrigienses`, `alumni oxonienses`).
   - Aligned `audit_person` in `src/audit/auditor.py` to recognize `parish_register` for birth, `probate` for death, and `heraldic_visitation`/`peerage` for parentage corroboration.

2. **Generational Range Scoping & Incremental Optimization**:
   - Added `get_audited_person_pids()` in `src/storage/db.py` to enable cache checking against previously audited persons.
   - Added `min_generation` parameter to `get_audit_scores` and `get_audit_summary` in `src/storage/db.py`.
   - Updated `audit_pedigree` in `src/audit/auditor.py` with `min_generation` filtering and `already_audited` skip logic.
   - Updated `audit_sources.py` with `--min-gen` CLI argument and updated summary tables.

3. **Testing & Verification**:
   - Added unit tests in `tests/test_audit.py` for deep historical record classification and `min_generation` scoping.
   - Ran `pytest`: 39/39 tests passed.
   - Executed live audit on Generations 11 to 15 (2,061 ancestors): 462 HIGH confidence (22.4%), 347 MEDIUM (16.8%), 626 LOW (30.4%), 626 UNSOURCED (30.4%). Average confidence: 40.5%.
   - Executed full-tree benchmark across all 2,603 ancestors (Generations 0 to 15): 699 HIGH confidence (26.9%), 427 MEDIUM (16.4%), 771 LOW (29.6%), 706 UNSOURCED (27.1%). Overall average confidence: 44.5%.
