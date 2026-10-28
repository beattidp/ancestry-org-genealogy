# Implementation Plan: Historical Newspaper & Maritime Harvester & Digitized Passenger List Harvester

Build a multi-source external record discovery and harvesting engine that connects to:
1. **Library of Congress Historical Newspapers API** (`loc.gov` Chronicling America collection) to discover maritime arrivals, passenger manifests, obituaries, and legal notices.
2. **Internet Archive Search API** (`archive.org`) to discover digitized passenger list compendiums, county histories, and published family genealogies.
3. **Candidate Discovery Engine** in `src/storage/db.py` to store, rank, and correlate external candidate records against brick-wall and unsourced ancestors without polluting the verified pedigree tree.

---

## User Review Required

> [!IMPORTANT]
> **Candidate Leads vs. Verified Sources**: External API searches inherently contain ambiguity (e.g. common names, OCR noise). We propose storing discoveries in a dedicated `candidate_discoveries` table rather than directly attaching them to `sources`/`person_sources`. This keeps the verified tree clean while generating high-confidence candidate leads for user review.

> [!TIP]
> **Primary Target Cohorts**:
> 1. **Terminal Immigrant Brick Walls:** Ancestors with 0 parents who immigrated to the US/Canada (e.g. Gen 5 direct patrilineal ancestor **Adam Beattie** `9ZMG-JSD`, b. 1828 Ireland, d. 1908 Sonoma CA; and his wife **Catherine Kennedy** `9ZMG-JS6`).
> 2. **Unsourced / Low-Confidence Cohort:** Ancestors with $\le 1$ sources in Generations 0 to 6.

---

## Open Questions

None currently. The user explicitly prioritized:
1. Historical Newspaper and Maritime Harvester
2. Followed by Digitized Passenger List and Monograph Harvester.

---

## Proposed Changes

### Storage & Schema

#### [MODIFY] [db.py](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/src/storage/db.py)
* Add `candidate_discoveries` table and indexes:
  * `id`: Primary key
  * `person_pid`: FK to `persons(pid)`
  * `harvester`: `'chronicling_america'` or `'internet_archive'`
  * `discovery_type`: `'newspaper_mention'`, `'maritime_arrival'`, `'passenger_list'`, `'monograph'`
  * `title`: Headline or document title
  * `date_str`: Published date or date range
  * `url`: Direct link to view the digitized page or scan
  * `source_identifier`: LOC resource ID or Internet Archive item ID
  * `snippet_text`: Extracted OCR text or description snippet
  * `confidence_score`: Float between 0.0 and 1.0 based on spatial/temporal correlation
  * `relevance_reason`: Human-readable explanation of why this was matched
  * `raw_json`: Full API response payload
  * `status`: `'pending'`, `'confirmed'`, `'rejected'`
  * `created_at`: Timestamp
* Add CRUD helper methods:
  * `upsert_candidate_discovery(candidate)`
  * `get_candidate_discoveries(person_pid=None, harvester=None, min_confidence=0.0)`
  * `get_terminal_brick_walls(max_generation=10)`
  * `get_discovery_summary()`

---

### Source Harvester Engine (`src/sources/`)

#### [NEW] [base.py](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/src/sources/base.py)
* Abstract base class `BaseHarvester`:
  * `CandidateDiscovery` dataclass.
  * Standardized querying interface: `search_person(person, facts) -> list[CandidateDiscovery]`.
  * Spatial and temporal relevance scoring algorithms (scoring name proximity, date proximity to lifespan $\pm 5$ years, state/location matches, and maritime/obituary keywords).

#### [NEW] [chronicling_america.py](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/src/sources/chronicling_america.py)
* `ChroniclingAmericaHarvester`:
  * Connects to the Library of Congress JSON search endpoint (`https://www.loc.gov/search/?in=original-format:newspaper&fo=json`).
  * Supports date range filtering (`dates=YYYY/YYYY`) matching the ancestor's lifetime.
  * Supports location filtering (`location_state=<state>`) based on known facts (e.g. California, Pennsylvania, Ohio, New York).
  * Maritime intelligence keyword expansion: queries for ship arrival terms (`"ship"`, `"vessel"`, `"arrival"`, `"bark"`, `"steamer"`) coupled with surnames.
  * Obituary and legal notice keyword extraction.
  * Rate-limiting and error handling with polite User-Agent headers.

#### [NEW] [internet_archive.py](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/src/sources/internet_archive.py)
* `InternetArchiveHarvester`:
  * Connects to `https://archive.org/advancedsearch.php` with JSON output.
  * Queries digitized book collections, immigration passenger compendiums (Rupp, Tepper, Filby, passenger lists), and published family genealogies (`"Beattie family"`, county histories).
  * Parses metadata, item identifiers, thumbnail URLs, and OCR snippets.
  * Scores relevance against known ancestor lifespans and geographic migration paths.

---

### CLI Tools

#### [NEW] [harvest_records.py](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/harvest_records.py)
* Comprehensive command-line utility for multi-source record harvesting:
  * `--harvester {newspaper,archive,all}`: Select target harvester.
  * `--target {brick_walls,unsourced,pid}`: Target selection.
  * `--pid <PID>`: Target an individual ancestor (e.g. Adam Beattie `9ZMG-JSD`).
  * `--max-gen <N>`: Maximum generation to target (default: 6).
  * `--limit <N>`: Maximum queries per run to avoid API exhaustion.
  * `--export-markdown <path>`: Export ranked candidate report for user review.

---

### Automated Tests

#### [NEW] [test_harvesters.py](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/tests/test_harvesters.py)
* Unit tests with mocked HTTP responses:
  * Test query construction (name formatting, date bounding, state filtering).
  * Test LOC API JSON response parsing and OCR snippet extraction.
  * Test Internet Archive search parsing.
  * Test spatial/temporal relevance scoring (positive vs negative controls).
  * Test database storage and retrieval of candidate discoveries.

---

## Verification Plan

### Automated Tests
1. Run pytest across the whole test suite including new harvester tests:
   ```bash
   pytest tests/test_harvesters.py -v
   pytest -v
   ```

### Live Verification
1. Run live targeted harvest on terminal immigrant ancestor **Adam Beattie** (`9ZMG-JSD`, b. 1828 Ireland, d. 1908 Redwood/Guerneville, Sonoma, CA):
   ```bash
   python3 harvest_records.py --harvester newspaper --pid 9ZMG-JSD --limit 5
   python3 harvest_records.py --harvester archive --pid 9ZMG-JSD --limit 5
   ```
2. Verify candidate discoveries are stored in `data/pedigree.sqlite` and display title, publication date, URL, relevance score, and snippet text.
3. Run batch harvest for early brick walls (Generations 1–5):
   ```bash
   python3 harvest_records.py --harvester all --target brick_walls --max-gen 5 --limit 10
   ```
4. Verify results summary table and export markdown report.
