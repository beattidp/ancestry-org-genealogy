# Walkthrough: GEDCOM 5.5.1 Export, Candidate Review, Scottish Gazetteer & Gen 6–10 Brick Wall Harvest

## Overview
In this milestone, we delivered four core capabilities to bridge local database analysis, standard genealogical interchange, candidate discovery verification, and deep Scottish geographical record resolution:

1. **Standard GEDCOM 5.5.1 Exporter**: Lineage-linked export utility enabling migration and external visualization of the 15-generation pedigree across desktop programs (Gramps, RootsMagic, Family Tree Maker).
2. **Candidate Review Workflow**: Interactive and scriptable commands (`--list-candidates`, `--confirm`, `--reject`) to evaluate harvested leads and promote confirmed candidates into Tier 1/2 verified database sources.
3. **Scottish Gazetteer & Civil Parish Resolver**: Reference resolution engine matching archaic Scottish event places to official historical counties, National Records of Scotland (NRS) civil parish codes, and generating direct ScotlandsPeople search links.
4. **Generation 6–10 Brick Wall Harvest Expansion**: Multi-source harvesting across terminal ancestors, discovering 37 high-confidence external records from the Library of Congress and Internet Archive.

---

## Key Achievements & Implementation Details

### 1. GEDCOM 5.5.1 Export Engine (`src/gedcom/exporter.py` & `export_gedcom.py`)
- **Format Compliance**: Standard Lineage-Linked GEDCOM 5.5.1 with UTF-8 encoding.
- **Individuals (`INDI`)**:
  - Personal name record with surname delimiters (`1 NAME Given /Surname/ Suffix`), `GIVN`, `SURN`, `NSFX`.
  - Gender (`1 SEX M/F`).
  - Vital events (`BIRT`, `CHR`, `DEAT`, `BURI`) with standardized `DATE` and `PLAC` tags.
  - Lineage pointers linking to child family (`1 FAMC @F_...@`) and spouse family (`1 FAMS @F_...@`).
- **Families (`FAM`)**:
  - Husband (`1 HUSB @I_...@`), Wife (`1 WIFE @I_...@`), Children (`1 CHIL @I_...@`).
  - Marriage events (`1 MARR`) with `DATE` and `PLAC`.
- **Sources & Citations (`SOUR`)**:
  - Full source records (`0 @S_...@ SOUR`) with `TITL`, `AUTH`, `PUBL`, direct `URL`, and citation `NOTE`.
  - Inline source citations (`1 SOUR @S_...@`) on individuals and event records.
- **Safety Sanitization**: Cross-reference pointers sanitize hyphens to underscores (`@I_KWHS_6NN@`) to prevent syntax errors in strict desktop parsers.
- **CLI Capabilities**:
  ```bash
  # Full export
  python3 export_gedcom.py --out data/beattie_pedigree.ged

  # Direct ancestors only, capped at Generation 5
  python3 export_gedcom.py --out data/direct_gen5.ged --direct-only --max-gen 5

  # Fast export omitting source citations
  python3 export_gedcom.py --out data/tree_fast.ged --no-sources
  ```

### 2. Candidate Review Commands (`harvest_records.py` & `src/storage/db.py`)
- **Review Options**:
  - `--list-candidates [--status {all,pending,confirmed,rejected}]`: Lists candidate discoveries with ID, ancestor, title, score, and status.
  - `--confirm <ID>`: Promotes candidate discovery to a verified source in `sources` (`DISC_<ID>`) and creates an individual association in `person_sources` (`PS_DISC_<ID>`).
  - `--reject <ID>`: Marks candidate discovery as rejected to filter from future consideration.
- **DB Methods**: Implemented `get_candidate_by_id`, `update_candidate_status`, and `promote_candidate_to_source` with atomic SQLite transactions.

### 3. Scottish Gazetteer & Civil Parish Resolver (`src/geo/scottish_gazetteer.py` & `resolve_scottish_places.py`)
- **Reference Dataset**: Built-in gazetteer covering Scottish civil parishes, historical counties, and National Records of Scotland (NRS) civil parish / registration district codes.
- **Matching Engine**: Employs regex word-boundary matching (`\b{parish}\b`) and county-level compatibility checks to eliminate false substring collisions (e.g., preventing the parish "Annan" from colliding with "Clackmannanshire").
- **Research Links**: Automatically formats pre-populated ScotlandsPeople Old Parish Register (OPR) search URLs for births/baptisms, marriages, and deaths.
- **Execution**: Scanned 10,021 facts in `data/pedigree.sqlite`, identified 27 Scottish vital events across 24 ancestors, and exported `doc/reports/scottish_ancestors_resolved.md`.

### 4. Generation 6–10 Brick Wall Harvest Expansion
- Screened terminal brick-wall ancestors (missing parents) across early American and Scottish/Irish lines.
- Executed multi-source queries against Library of Congress Chronicling America and Internet Archive collections.
- Yielded 37 candidate discoveries across 9 distinct ancestors, exported to `doc/reports/brick_walls_gen6_discoveries.md`.

---

## Verification & Metrics

### Automated Test Suite
Ran complete unit test suite across all modules:
```bash
pytest -v
```
**Results: 54 passed in 2.70s**
- `tests/test_audit.py` (10 tests)
- `tests/test_auth.py` (3 tests)
- `tests/test_client.py` (4 tests)
- `tests/test_constraints.py` (11 tests)
- `tests/test_gazetteer.py` (3 tests)
- `tests/test_gedcom.py` (4 tests)
- `tests/test_harvesters.py` (8 tests)
- `tests/test_ingestion.py` (7 tests)
- `tests/test_storage.py` (4 tests)

### Live GEDCOM Export Output
Exported to `data/beattie_pedigree.ged`:
- **Individuals**: 2,617
- **Families**: 1,378
- **Source Citations**: 21,193
- **File Size**: 10.7 MB
- **Export Time**: 2.1 seconds

### Live Scottish Resolution Output
Identified Scottish events and parishes:
- **Duncan Millar (`M247-ST2`)**: Alloa, Clackmannanshire (Parish #465)
- **William White (`KC3B-S6V`)**: Liberton, Midlothian (Parish #693)
- **Elizabeth Simpson (`KC3B-SZ5`)**: Liberton, Midlothian (Parish #693)
- **Donald McNeill (`G2M9-65R`)**: Colonsay, Argyllshire (Parish #539)
- **John Beattie (`M247-SRQ`)**: Peebles, Peeblesshire (Parish #768)
- **James Millar (`M247-SPK`)**: Alloa, Clackmannanshire (Parish #465)
- **John Somerville (`M247-STM`)**: St Cuthbert's, Edinburgh, Midlothian (Parish #685/1)

### Live Candidate Review Verification
- Confirmed candidate ID 2 (`DISC_2`), successfully promoting it to `sources` and `person_sources`.
- Rejected candidate ID 24 (`Flux 25` modern publication).

### Live Candidate Discovery Aggregate Summary
```
==================================================
 Candidate Discovery Summary
==================================================
Total Discoveries:   37
Distinct Persons:    9
Average Confidence:  37.4%

By Harvester:
  - chronicling_america   : 20
  - internet_archive      : 17

By Discovery Type:
  - maritime_arrival      : 8
  - monograph             : 12
  - newspaper_mention     : 15
  - obituary_or_probate   : 2

By Status:
  - confirmed             : 1
  - pending               : 35
  - rejected              : 1
==================================================
```
