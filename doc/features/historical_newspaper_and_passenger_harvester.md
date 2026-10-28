# Feature: Historical Newspaper & Maritime and Digitized Passenger List Harvesters

**Module:** `src/sources/`  
**CLI Tool:** `harvest_records.py`  
**Database Table:** `candidate_discoveries` in `data/pedigree.sqlite`  
**Test Suite:** `tests/test_harvesters.py` (8 new tests, 47 total in test suite)

---

## 1. Overview & Purpose

Previously, the pedigree pipeline was restricted solely to the FamilySearch API. This meant our local knowledge graph was purely reactive: it could only ingest records that had already been found and manually attached by researchers on FamilySearch.org. If an ancestor immigrated on a ship, appeared under an alternate surname spelling, or was covered in local historical newspapers or out-of-print published family genealogies, our system had zero visibility.

This feature introduces a multi-source external harvesting and candidate discovery engine:
1. **Library of Congress Chronicling America Harvester (`src/sources/chronicling_america.py`)**: Queries historical American newspapers (1777–1963) via the `loc.gov` JSON search endpoint to discover maritime port arrivals, ship passenger lists, obituaries, and legal/probate notices.
2. **Internet Archive Harvester (`src/sources/internet_archive.py`)**: Queries digitized books, compiled passenger lists (Rupp, Tepper, Filby), county histories, and family genealogies via the `archive.org` Advanced Search JSON API.
3. **Candidate Discovery Engine (`src/storage/db.py`)**: Stores discovered external records in a dedicated `candidate_discoveries` table with spatial-temporal scoring, relevance rationales, and review status (`pending`, `confirmed`, `rejected`), keeping the verified tree clean while generating targeted research leads.

---

## 2. Architecture & Data Flow

```
                                  +---------------------------------------+
                                  |       `harvest_records.py` CLI        |
                                  +---------------------------------------+
                                                      |
                  +-----------------------------------+-----------------------------------+
                  |                                                                       |
                  v                                                                       v
+-----------------------------------+                                   +-----------------------------------+
|    ChroniclingAmericaHarvester    |                                   |     InternetArchiveHarvester      |
|    (Library of Congress API)      |                                   |      (Internet Archive API)       |
+-----------------------------------+                                   +-----------------------------------+
  - Full Name in quotes                                                   - Monograph: "{Surname} family"
  - In-lifespan date bounding                                             - Passenger lists & immigrant texts
  - Maritime intelligence query:                                          - County histories matching places
    `"{Surname}" AND (ship OR arrival                                     - Details URL & OCR metadata
     OR passengers OR steamer)`
                  |                                                                       |
                  +-----------------------------------+-----------------------------------+
                                                      |
                                                      v
                                  +---------------------------------------+
                                  |      `score_candidate()` Engine       |
                                  |          (`src/sources/base.py`)      |
                                  +---------------------------------------+
                                    1. Name match (+0.10 to +0.40)
                                    2. Lifespan & date correlation (+0.30)
                                    3. Geographic match (+0.25)
                                    4. Maritime / passenger boost (+0.15)
                                    5. Obituary / probate boost (+0.10)
                                                      |
                                                      v
                                  +---------------------------------------+
                                  |      `candidate_discoveries` Table    |
                                  |         (`data/pedigree.sqlite`)      |
                                  +---------------------------------------+
                                  | PID, harvester, discovery_type, title |
                                  | date_str, url, snippet, score, status |
                                  +---------------------------------------+
```

---

## 3. Database Schema: `candidate_discoveries`

```sql
CREATE TABLE IF NOT EXISTS candidate_discoveries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_pid TEXT NOT NULL,
    harvester TEXT NOT NULL,         -- 'chronicling_america' or 'internet_archive'
    discovery_type TEXT NOT NULL,    -- 'newspaper_mention', 'maritime_arrival', 'monograph', 'obituary_or_probate'
    title TEXT NOT NULL,
    date_str TEXT,
    url TEXT,
    source_identifier TEXT,
    snippet_text TEXT,
    confidence_score REAL DEFAULT 0.0,
    relevance_reason TEXT,
    raw_json TEXT,
    status TEXT DEFAULT 'pending',   -- 'pending', 'confirmed', 'rejected'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (person_pid) REFERENCES persons(pid) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_candidates_pid ON candidate_discoveries(person_pid);
CREATE INDEX IF NOT EXISTS idx_candidates_harvester ON candidate_discoveries(harvester);
CREATE INDEX IF NOT EXISTS idx_candidates_conf ON candidate_discoveries(confidence_score);
```

---

## 4. CLI Usage & Verification

### Targeted Harvest for an Individual Ancestor
```bash
python3 harvest_records.py --harvester all --target pid --pid 9ZMG-JSD --limit 5 --export-markdown doc/reports/candidate_discoveries.md
```

### Batch Harvest for Terminal Brick Walls
```bash
python3 harvest_records.py --harvester all --target brick_walls --max-gen 5 --limit 3 --export-markdown doc/reports/brick_walls_gen5_discoveries.md
```

### Summary of Discovered Leads
```bash
python3 harvest_records.py --summary
```

**Live Output:**
```
==================================================
 Candidate Discovery Summary
==================================================
Total Discoveries:   24
Distinct Persons:    5
Average Confidence:  38.3%

By Harvester:
  - chronicling_america   : 17
  - internet_archive      : 7

By Discovery Type:
  - maritime_arrival      : 4
  - monograph             : 5
  - newspaper_mention     : 13
  - obituary_or_probate   : 2

By Status:
  - pending               : 24
==================================================
```

---

## 5. Automated Verification

Ran full pytest test suite:
* `tests/test_harvesters.py`: 8 passed
* Full test suite: **47 passed** across all modules (`test_audit.py`, `test_auth.py`, `test_client.py`, `test_constraints.py`, `test_harvesters.py`, `test_ingestion.py`, `test_storage.py`).
