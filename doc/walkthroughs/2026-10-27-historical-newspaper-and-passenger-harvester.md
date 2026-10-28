# Walkthrough: Historical Newspaper & Maritime Harvester and Digitized Passenger List Harvester

## Overview
In this iteration, we expanded our genealogical pipeline beyond FamilySearch by building an autonomous multi-source external record discovery and harvesting engine. We integrated:
1. **Library of Congress Chronicling America** (`loc.gov` Historical Newspapers API) to discover ship manifests, maritime arrivals, obituaries, and legal notices.
2. **Internet Archive** (`archive.org` Advanced Search API) to discover digitized passenger list compendiums, county histories, and published family genealogies.
3. **Candidate Discovery Engine** in `src/storage/db.py` to store, rank, and correlate external candidate records against brick-wall and unsourced ancestors without polluting the verified pedigree tree.

---

## Key Achievements

### 1. Database Schema & Candidate Discovery Storage
- **`candidate_discoveries` Table**: Created in `data/pedigree.sqlite` with full tracking for `person_pid`, `harvester`, `discovery_type`, `title`, `date_str`, `url`, `source_identifier`, `snippet_text`, `confidence_score`, `relevance_reason`, `raw_json`, and `status`.
- **Deduplication & Queries**: Implemented `upsert_candidate_discovery()`, `get_candidate_discoveries()`, `get_terminal_brick_walls()`, and `get_discovery_summary()`.

### 2. Multi-Factor Spatial-Temporal Candidate Scorer (`src/sources/base.py`)
- Evaluates candidate matches against known ancestor facts:
  - **Exact Name Match**: $+0.40$
  - **Given + Surname**: $+0.30$
  - **Initial + Surname**: $+0.25$
  - **Surname Match**: $+0.10$
  - **Lifespan Date Window**: $+0.30$ if within lifespan; $-0.30$ if out of range
  - **Geographic Match**: $+0.25$ if matched against known birth/death places or facts
  - **Maritime / Passenger Terms**: $+0.15$ (classifies as `maritime_arrival`)
  - **Obituary / Probate Terms**: $+0.10$ (classifies as `obituary_or_probate`)

### 3. Harvester Implementations
- **`ChroniclingAmericaHarvester` (`src/sources/chronicling_america.py`)**:
  - Connects to Library of Congress `loc.gov/search/` endpoint.
  - Queries name in quotes, in-lifespan date bounding, and maritime arrival queries.
  - Extracts OCR snippets, publication metadata, location tags, and direct view URLs.
  - Features 35-second request timeout tuned for Library of Congress query processing.
- **`InternetArchiveHarvester` (`src/sources/internet_archive.py`)**:
  - Connects to Internet Archive Advanced Search API (`archive.org/advancedsearch.php`).
  - Queries family monographs (`"{surname} family"`, `"{surname} genealogy"`), compiled passenger lists, and county histories.
  - Extracts document identifiers, metadata, descriptions, creators, and direct scan URLs.

### 4. CLI Tool: `harvest_records.py`
- Supports targeted single-ancestor harvesting (`--pid`), batch brick-wall harvesting (`--target brick_walls`), and unsourced ancestor harvesting (`--target unsourced`).
- Formats rich tabular console output and exports markdown reports (`--export-markdown`).

---

## Live Verification & Discovery Results

### Automated Unit Tests
```bash
pytest tests/test_harvesters.py -v
pytest -v
```
* **47/47 tests passed** across all test suites in 2.41s.

### Targeted Live Harvest: Adam Beattie (`9ZMG-JSD`)
Terminal patrilineal immigrant ancestor (b. 1828 Ireland, d. 1908 Redwood/Guerneville, Sonoma, CA; 0 parents):
```bash
python3 harvest_records.py --harvester all --target pid --pid 9ZMG-JSD --limit 5 --export-markdown doc/reports/adam_beattie_discoveries.md
```
* **Results**: Discovered 6 candidate records.
* **Top Lead (70% Confidence)**:
  * Title: *Image 4 of The times (Owosso, Mich.), March 9, 1888*
  * URL: [https://www.loc.gov/resource/sn96077385/1888-03-09/ed-1/?sp=4&q=%22adam+beattie%22](https://www.loc.gov/resource/sn96077385/1888-03-09/ed-1/?sp=4&q=%22adam+beattie%22)
  * Match Rationale: Exact name match ("Adam Beattie"); In-lifespan date (1888 within 1828–1908).
* **Obituary Lead (40% Confidence)**:
  * Title: *Image 2 of Pioneer of Assumption, November 24, 1877*
  * Match Rationale: In-lifespan date; Vital/probate terms (died).

### Batch Live Harvest: Generation 1–5 Terminal Brick Walls
```bash
python3 harvest_records.py --harvester all --target brick_walls --max-gen 5 --limit 3 --export-markdown doc/reports/brick_walls_gen5_discoveries.md
```

#### Aggregate Discovery Summary
```bash
python3 harvest_records.py --summary
```
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
