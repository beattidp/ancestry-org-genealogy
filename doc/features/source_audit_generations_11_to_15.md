# Feature: Source Auditing of Generations 11 to 15 & Historical Record Classification

## 1. Overview
This feature extends the Genealogical Proof Standard (GPS) audit engine to evaluate 2,061 deep ancestors in Generations 11 through 15 (spanning the 1400s through 1600s). It enhances source evidence classification to accurately recognize early modern and medieval British, Scottish, and French record types, provides bidirectional generational scoping (`--min-gen` and `--max-gen`), and optimizes incremental audit caching.

---

## 2. Architecture & Design

### Historical Record Classification
Prior to this feature, earlier parish records and Heraldic Visitations were classified as Tier 3 (`other`). The classifier was enhanced with specific regular expressions to properly tier and type early modern sources:

* **Tier 1 (Primary Documentary Evidence)**:
  * **Parish Registers & Church Books**: `parish register`, `parish record`, `church record`, `kirk session` (classified as `parish_register`).
  * **Marriage Banns & Allegations**: `banns`, `marriage allegation`, `marriage bond` (classified as `vital_marriage`).
  * **Inquisitions Post Mortem & Manorial**: `inquisition post mortem`, `ipm`, `court rolls`, `manorial`, `feet of fines`, `chancery` (classified as `probate`).
  * **Probate Courts**: `prerogative court of canterbury`, `testament dative`, `testament testamentar` (classified as `probate`).

* **Tier 2 (Secondary / Published Derivative Evidence)**:
  * **Heralds' Visitations**: `visitation of`, `visitations of`, `heraldic visitation`, `pedigrees of` (classified as `heraldic_visitation`).
  * **Peerages & Gentry Compilations**: `peerage`, `baronetage`, `cokayne`, `burke's`, `landed gentry` (classified as `peerage`).
  * **Academic Registers**: `alumni cantabrigienses`, `alumni oxonienses` (classified as `secondary`).
  * **County Histories**: `county history`, `history and antiquities` (classified as `secondary`).

### Verification Checks Alignment
* **Birth Verification**: Now satisfied by Tier 1 primary birth, census, social security, or `parish_register` (recording infant baptisms/christenings).
* **Death Verification**: Now satisfied by Tier 1 death certificates, burials, cemetery records, social security, or contemporary `probate` (wills and Inquisitions Post Mortem proving date of death).
* **Parentage Verification**: Corroborated by contemporary documentary evidence linking parent and child: census, birth/baptism registers, probate/wills, `parish_register`, `heraldic_visitation`, or published `peerage`.

### Generational Range Scoping
* Added `--min-gen` alongside `--max-gen` in `audit_sources.py`.
* Propagated `min_generation` into `SourceAuditor.audit_pedigree`, `Database.get_audit_scores`, and `Database.get_audit_summary`.
* Enabled targeted generation-by-generation audits (e.g. `--min-gen 11 --max-gen 11`) or range audits (e.g. `--min-gen 11 --max-gen 15`).

### High-Efficiency Audit Caching
* `Database.get_audited_person_pids()` retrieves all previously scored ancestors.
* Bypasses network API requests for previously evaluated ancestors, preventing redundant calls on ancestors with 0 attached sources in FamilySearch.

---

## 3. Database Updates

* **`Database.get_audited_person_pids() -> set[str]`**: Queries distinct `person_pid` records from `person_audit_scores`.
* **`Database.get_audit_scores(root_pid, min_generation=None, max_generation=None)`**: Dynamic SQL clause builder filtering `pt.generation >= min_generation` and `pt.generation <= max_generation`.
* **`Database.get_audit_summary(root_pid, min_generation=None, max_generation=None)`**: Generates summary statistics strictly within the requested generational range.

---

## 4. Verification & Audit Results

### Generations 11 to 15 (2,061 Ancestors)
* **HIGH Confidence (80–100%)**: 462 ancestors (22.4%)
* **MEDIUM Confidence (50–79%)**: 347 ancestors (16.8%)
* **LOW Confidence (1–49%)**: 626 ancestors (30.4%)
* **UNSOURCED (0%)**: 626 ancestors (30.4%)
* **Average Confidence Score**: **40.5%**

### Generational Breakdown
* **Gen 11 (9th Great-Grandparents, 214 ancestors)**: 69% Birth verified, 48% Death verified, 53% Parentage verified, **64.2%** average confidence.
* **Gen 12 (10th Great-Grandparents, 306 ancestors)**: 64% Birth verified, 44% Death verified, 47% Parentage verified, **59.5%** average confidence.
* **Gen 13 (11th Great-Grandparents, 399 ancestors)**: 51% Birth verified, 35% Death verified, 36% Parentage verified, **48.6%** average confidence.
* **Gen 14 (12th Great-Grandparents, 491 ancestors)**: 40% Birth verified, 25% Death verified, 29% Parentage verified, **38.7%** average confidence.
* **Gen 15 (13th Great-Grandparents, 651 ancestors)**: 30% Birth verified, 22% Death verified, 1% Parentage verified, **20.2%** average confidence.
