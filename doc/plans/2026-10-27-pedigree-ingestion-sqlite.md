# Implementation Plan — Pedigree Ingestion & Local SQLite Storage

Build a local storage and automated ingestion engine to fetch $N$ generations of ancestors from FamilySearch and persist them into a structured SQLite database. This provides offline analysis, rapid querying, pedigree gap identification, and the foundation for source auditing.

## User Review Required

> [!NOTE]
> **Token Expiration**: The session token provided earlier has reached its expiration window (`Authentication failed (401)`). Before running live data ingestion, you will need to refresh the `fssessionid` cookie from [familysearch.org](https://www.familysearch.org) and update `.env`. Our CLI tools (`probe.py` and `ingest.py`) will automatically alert and guide you if the token is expired.

> [!IMPORTANT]
> **Data Integrity & Raw Preservation**:
> The SQLite database uses a dual-representation schema:
> 1. **Normalized relational columns** (`name`, `gender`, `birth_date`, `birth_place`, `death_date`, `death_place`) for rapid SQL querying, indexing, and constraint checking.
> 2. **Lossless raw JSON payloads** (`raw_json`) for every person, relationship, and fact, ensuring no FamilySearch/GEDCOM X metadata is discarded.

---

## Proposed Changes

### Database Layer (`src/storage/`)

#### [NEW] [src/storage/__init__.py](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/src/storage/__init__.py)
- Package init exporting `Database` and models.

#### [NEW] [src/storage/db.py](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/src/storage/db.py)
- SQLite connection manager with WAL (Write-Ahead Logging) mode, foreign key enforcement, and thread safety.
- Manages schema creation and migrations:
  - `persons`: `pid` (PK), `name`, `gender`, `lifespan`, `living`, `birth_date`, `birth_place`, `death_date`, `death_place`, `raw_json`, `updated_at`.
  - `relationships`: `id` (PK), `rel_type` (`parent-child`, `couple`), `parent_pid`, `child_pid`, `spouse1_pid`, `spouse2_pid`, `lineage_type`, `raw_json`.
  - `pedigree_tree`: `root_pid`, `person_pid`, `generation`, `ascendancy_number` (Ahnentafel number: 1=self, 2=father, 3=mother, 4=paternal grandfather, etc.), `lineage_path`.
  - `facts`: `id` (PK auto), `person_pid`, `fact_type`, `date_original`, `date_formal`, `place_original`, `place_normalized`, `value`.
  - `ingestion_runs`: Log of ingestion timestamp, root PID, generation depth, counts, and status.
- Helper methods for upserting persons, relationships, facts, and pedigree nodes.

---

### Ingestion Engine (`src/pedigree/`)

#### [NEW] [src/pedigree/__init__.py](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/src/pedigree/__init__.py)
- Package init.

#### [NEW] [src/pedigree/extractor.py](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/src/pedigree/extractor.py)
- Helper to parse GEDCOM X payloads into clean structured models:
  - Extracts normalized names, gender, birth/death/marriage facts, and formal date strings.

#### [NEW] [src/pedigree/ingest.py](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/src/pedigree/ingest.py)
- `PedigreeIngester` class:
  - Accepts `root_pid` and `max_generations` (default: 4, expandable up to 8+ via recursive leaf traversal).
  - Queries FamilySearch `/platform/tree/ancestry` with `personDetails=true` and `marriageDetails=true`.
  - Parses Ahnentafel / ascendancy numbers and parent-child links.
  - Recursively fetches deeper generations if requested depth > 8.
  - Upserts persons and relationships in an atomic transaction.
  - Updates progress hooks for real-time terminal feedback.

---

### CLI Utilities

#### [NEW] [ingest.py](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/ingest.py)
- Interactive CLI ingestion script:
  ```bash
  python ingest.py --root KWHS-6NN --generations 4 --db data/pedigree.sqlite
  ```
  - Validates session before beginning.
  - Displays progress bar and live metrics via `rich`.
  - Prints summary table showing count of ancestors ingested per generation.

#### [NEW] [tree_summary.py](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/tree_summary.py)
- Offline database inspection tool:
  ```bash
  python tree_summary.py --db data/pedigree.sqlite
  ```
  - Displays pedigree tree stats: total ancestors by generation, completion percentage ($2^n$ theoretical vs actual), identified pedigree gaps (ancestors with missing parents), and earliest ancestors born.

---

### Tests

#### [NEW] [tests/test_storage.py](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/tests/test_storage.py)
- Unit tests for SQLite database creation, person upsert, relationship linking, and fact indexing.

#### [NEW] [tests/test_ingestion.py](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/tests/test_ingestion.py)
- Unit tests for `extractor.py` and `PedigreeIngester` with mock GEDCOM X payloads.

---

## Verification Plan

### Automated Tests
1. **Database Schema & CRUD Tests**:
   - `python -m pytest tests/test_storage.py tests/test_ingestion.py -v`
2. **Mock Ingestion Pipeline**:
   - Verify that simulated multi-generation ancestry payloads correctly populate all SQLite tables (`persons`, `relationships`, `pedigree_tree`, `facts`).

### Live Verification (with active token)
1. **Live Pedigree Ingestion**:
   - Run `python ingest.py --root KWHS-6NN --generations 4 --db data/pedigree.sqlite`.
   - Verify all 4 generations of ancestors are stored.
2. **Offline Tree Inspection**:
   - Run `python tree_summary.py --db data/pedigree.sqlite`.
   - Confirm generation statistics, Ahnentafel numbers, and identified pedigree gaps match expected family lines.
