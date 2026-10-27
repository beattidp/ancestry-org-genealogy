# Implementation Plan — Source & Citation Auditor

Build an automated **Source & Citation Auditor** to ingest all attached archival citations from FamilySearch, classify them into evidence quality tiers (Primary vs Secondary vs User Trees), assess verification coverage for core life events (Birth, Death, Parentage), and compute an objective Confidence Score for each ancestor in the local database.

## User Review Required

> [!IMPORTANT]
> **Evidence Quality Tiering Rules**:
> The auditor classifies attached sources into three strict evidentiary tiers:
> - **Tier 1 (Primary Contemporary Documentary Evidence)**: Vital birth/death/marriage certificates, parish baptism/burial registers, federal/state censuses (1850–1950), military records, Social Security NUMIDENT, and probate/wills.
> - **Tier 2 (Secondary / Derivative Evidence)**: Newspaper obituaries, compiled county histories, memorial entries without primary document scans.
> - **Tier 3 (Unverified Hypotheses / User Assertions)**: User-submitted member trees (Ancestry trees, Legacy NFS, Pedigree Resource Files) or unsourced notes. These receive **zero weight** toward verifying an event.

> [!TIP]
> **Actionable Research Backlog**:
> In addition to scoring confidence, the auditor generates a prioritized research backlog highlighting which ancestors lack primary birth, death, or parentage proof so you know exactly which historical archives to search next.

---

## Proposed Changes

### Database Layer (`src/storage/`)

#### [MODIFY] [src/storage/db.py](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/src/storage/db.py)
- Add new tables:
  - `sources`: `id` (PK), `title`, `about_url` (ARK URL), `citation_text`, `collection_url`, `tier` (1, 2, 3), `record_type` (`census`, `vital_birth`, `vital_death`, `military`, `social_security`, `user_tree`, `other`), `raw_json`, `updated_at`.
  - `person_sources`: `id` (PK), `person_pid` (FK), `source_id` (FK), `tags` (comma-separated list: `Name`, `Birth`, `Death`, etc.), `contributor`, `raw_json`.
  - `person_audit_scores`: `person_pid` (PK), `total_sources`, `tier1_sources`, `tier2_sources`, `tier3_sources`, `birth_verified`, `death_verified`, `parentage_verified`, `confidence_score` (0.0–100.0), `confidence_level` (`HIGH`, `MEDIUM`, `LOW`, `UNSOURCED`), `issues` (JSON list), `audited_at`.
- Add helper methods:
  - `upsert_sources_batch(sources_list)`
  - `upsert_person_sources_batch(person_sources_list)`
  - `upsert_audit_score(score_dict)`
  - `get_audit_summary(root_pid)`
  - `get_unaudited_or_deficit_ancestors(root_pid)`

---

### Audit & Evidence Classification Layer (`src/audit/`)

#### [NEW] [src/audit/__init__.py](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/src/audit/__init__.py)
- Package init exporting `SourceClassifier`, `SourceAuditor`, and `AuditAssessment`.

#### [NEW] [src/audit/classifier.py](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/src/audit/classifier.py)
- `SourceClassifier`:
  - Evaluates source title, collection URL, and ARK identifiers using regular expressions and rule patterns.
  - Categorizes records into:
    - `census`: US Federal/State Censuses, UK/Canadian Censuses (Tier 1)
    - `vital_birth`: Birth indexes, birth certificates, baptism/christening registers (Tier 1)
    - `vital_marriage`: Marriage licenses, certificates, parish marriage registers (Tier 1)
    - `vital_death`: Death certificates, burial registers, cemetery interments (Tier 1)
    - `military`: WW1/WW2 draft cards, enlistments, service records (Tier 1)
    - `social_security`: Social Security Applications & NUMIDENT files (Tier 1)
    - `probate`: Wills, probate packets, letters of administration (Tier 1)
    - `secondary`: Newspaper obituaries, county histories, compiled books (Tier 2)
    - `user_tree`: Pedigree Resource File, Ancestry Member Tree, Legacy NFS (Tier 3)
  - Returns `(tier: int, record_type: str)`.

#### [NEW] [src/audit/auditor.py](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/src/audit/auditor.py)
- `SourceAuditor`:
  - `fetch_and_store_sources(pids: list[str])`: Queries FamilySearch `/platform/tree/persons/{pid}/sources`, normalizes records via `SourceClassifier`, and stores them in SQLite.
  - `audit_person(pid: str)`:
    - Evaluates attached sources for Birth, Death, and Parentage.
    - Determines if Birth has at least one Tier 1 primary citation.
    - Determines if Death has at least one Tier 1 primary citation.
    - Determines if Parentage link is corroborated by a Tier 1 source mentioning child and parents (e.g. Census household or birth register).
    - Calculates a weighted Confidence Score (0–100%):
      - 40% Parentage proof (the most critical link in genealogy)
      - 30% Birth primary proof
      - 20% Death primary proof
      - 10% Corroborating contemporary records (multiple censuses/military)
      - Penalty deductions for conflicting records or reliance on Tier 3 user trees.
  - `audit_pedigree(root_pid: str, fetch: bool = False)`: Audits all ancestors in the pedigree tree and records scores in `person_audit_scores`.

---

### CLI Utility

#### [NEW] [audit_sources.py](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/audit_sources.py)
- Interactive CLI command:
  ```bash
  python audit_sources.py --db data/pedigree.sqlite --fetch
  ```
  - Displays progress while fetching sources from FamilySearch.
  - Renders formatted Rich tables:
    1. **Confidence Level Distribution** (High / Medium / Low / Unsourced counts & percentages).
    2. **Evidence Coverage Matrix** (Generations vs % Birth Verified, % Death Verified, % Parentage Verified).
    3. **Target Evidence Deficits** (Table of specific ancestors missing primary evidence, with recommended research actions).

---

### Tests

#### [NEW] [tests/test_audit.py](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/tests/test_audit.py)
- Unit tests for `SourceClassifier`:
  - Verifies correct classification of US Censuses, California Birth Index, WWII Draft Cards, and Member Trees.
- Unit tests for `SourceAuditor`:
  - Verifies score calculation on well-sourced vs poorly-sourced personas.
  - Verifies database persistence of audit scores and sources.

---

## Verification Plan

### Automated Tests
1. **Unit Test Suite**:
   - `python -m pytest tests/test_audit.py -v`
   - Verify 100% pass across classifier and scoring calculations.

### Live Verification
1. **Source Fetch & Audit Execution**:
   - Run `python audit_sources.py --db data/pedigree.sqlite --fetch`.
   - Verify attached sources are downloaded for all 32 ancestors.
2. **Audit Output Inspection**:
   - Verify summary tables display accurate confidence tiers.
   - Confirm ancestors with primary vital records (e.g. `KJJ4-83J` with WWII Draft + Social Security NUMIDENT) are accurately scored.
