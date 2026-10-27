# Walkthrough — Source & Citation Auditor

We have built and verified the automated **Genealogical Source & Citation Auditor**, which fetches attached archival records from FamilySearch, classifies them into **Genealogical Proof Standard (GPS)** evidence tiers, verifies core life events (Birth, Death, Parentage), and scores confidence across the pedigree.

---

## 1. What Was Created & Implemented

### Database Layer (`src/storage/db.py`)
* Added tables and indexes:
  * `sources`: Stores normalized and classified records (`id`, `title`, `about_url`, `citation_text`, `tier`, `record_type`, `raw_json`).
  * `person_sources`: Stores citation reference linkages between persons and sources with fact tags (`Name`, `Birth`, `Death`, etc.).
  * `person_audit_scores`: Stores calculated confidence scores, tier source distributions, verification flags, and identified evidentiary deficits.
* Added query and aggregation methods: `upsert_sources_batch`, `upsert_person_sources_batch`, `upsert_audit_score`, `get_person_sources`, `get_audit_scores`, and `get_audit_summary`.

### Classifier & Auditor Engines (`src/audit/`)
* **[src/audit/classifier.py](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/src/audit/classifier.py)**:
  * Pattern-matches and categorizes records into GPS evidence quality tiers:
    * **Tier 1 (Primary Documentary Evidence)**: Censuses, vital birth/death/marriage registrations, parish christenings, military draft/service cards, Social Security NUMIDENT, wills/probate.
    * **Tier 2 (Secondary / Derivative Evidence)**: Newspaper obituaries, compiled county histories, biographical books, passenger manifests.
    * **Tier 3 (Unverified Hypotheses)**: Member trees, Pedigree Resource Files, Legacy NFS sources. (Assigned zero weight toward verification).
* **[src/audit/auditor.py](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/src/audit/auditor.py)**:
  * `SourceAuditor` fetches attached sources from FamilySearch (`GET /platform/tree/persons/{pid}/sources`).
  * Evaluates birth verification, death verification, and parentage corroboration.
  * Calculates weighted confidence scores (0–100%) and categorizes ancestors as `HIGH`, `MEDIUM`, `LOW`, or `UNSOURCED`.

### CLI Tool
* **[audit_sources.py](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/audit_sources.py)**:
  * Interactive CLI utility:
    ```bash
    python audit_sources.py --db data/pedigree.sqlite --fetch
    ```
  * Renders:
    1. **Evidence Confidence Distribution Table**
    2. **Generational Evidence Verification Matrix**
    3. **Priority Evidentiary Deficits Action Table**

---

## 2. Verification Results

### Automated Unit Tests
Ran `pytest`:
```text
============================= test session starts ==============================
platform linux -- Python 3.13.1, pytest-9.1.1, pluggy-1.7.0
rootdir: /home/beattidp/Documents/antigravity/ancestry-genealogy
configfile: pytest.ini
testpaths: tests
plugins: anyio-4.15.1
collected 23 items

tests/test_audit.py .......                                              [ 30%]
tests/test_auth.py ...                                                   [ 43%]
tests/test_client.py ....                                                [ 60%]
tests/test_ingestion.py .....                                            [ 82%]
tests/test_storage.py ....                                               [100%]

============================== 23 passed in 1.45s ==============================
```

### Live Pedigree Source Audit Results
Ran `python audit_sources.py --db data/pedigree.sqlite --fetch` against FamilySearch Production:

* **Sources Ingested:** **640 distinct historical source descriptions** and **642 citation links**.
* **Average Pedigree Confidence Score:** **71.9%**.
* **Confidence Distribution:**
  * **HIGH (80–100%)**: 13 ancestors (40.6%)
  * **MEDIUM (50–79%)**: 15 ancestors (46.9%)
  * **LOW (1–49%)**: 1 ancestor (3.1%)
  * **UNSOURCED (0%)**: 3 living/recent individuals (9.4%)
* **Generational Verification Matrix:**
  * **Grandparents (Gen 2):** **100% Birth Verified, 100% Death Verified, 100% Parentage Verified (100.0% Avg Confidence)**.
  * **1st Great-Grandparents (Gen 3):** **100% Birth Verified, 100% Death Verified, 100% Parentage Verified (100.0% Avg Confidence)**.
  * **2nd Great-Grandparents (Gen 4):** 100% Birth Verified, 94% Death Verified, 0% Parentage Verified (63.1% Avg Confidence) — because Generation 5 parents are the unlinked brick walls!
* **Priority Evidentiary Deficits Action List:** Successfully generated the exact list of 16 Generation 4 ancestors whose parentage needs primary documentary corroboration (e.g. tracking down 1870/1880 censuses, probate records, or county vital entries).
