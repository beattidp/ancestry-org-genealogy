# Implementation Plan: GEDCOM 5.5.1 Export, Candidate Review, Scottish Gazetteer & Gen 6–10 Expansion

Implement the prioritized sequence requested by the user:
1. **GEDCOM 5.5.1 Export Engine (`export_gedcom.py` & `src/gedcom/exporter.py`)** to produce standard lineage-linked `.ged` files directly from `data/pedigree.sqlite`.
2. **Candidate Review Workflow (`confirm`/`reject`)** to inspect, accept, or reject external candidate discoveries in `candidate_discoveries`.
3. **Scottish Gazetteer & Civil Parish Resolver (`src/geo/scottish_gazetteer.py`)** to standardize archaic Scottish birth/death locations and map them to official National Records of Scotland (NRS) civil parish codes.
4. **Harvest Expansion across Generation 6–10 Brick Walls** (138 terminal ancestors) using the multi-source harvester engine.

---

## User Review Required

> [!IMPORTANT]
> **GEDCOM Standard Compatibility**: The export will implement standard **GEDCOM 5.5.1 Lineage-Linked (UTF-8)**, universally supported by RootsMagic, Gramps, Ancestry, Family Tree Maker, and MacFamilyTree. All 2,603 individuals, 4,237 relationships, 10,021 facts, and 1,489 citations will be exported.

> [!TIP]
> **Candidate Lead Promotion**: When a candidate discovery is confirmed via `--confirm <ID>`, it will:
> 1. Set `status = 'confirmed'` in `candidate_discoveries`.
> 2. Automatically create a verified source in `sources` and link it to the person in `person_sources`.

---

## Open Questions

None. The user has specified the execution sequence clearly.

---

## Proposed Changes

### Phase 1: GEDCOM 5.5.1 Export Engine

#### [NEW] [exporter.py](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/src/gedcom/exporter.py)
* `GedcomExporter` class:
  * Reads individuals, couples, parent-child links, facts, and source citations from `Database`.
  * Generates standard `INDI` records (`0 @I<pid>@ INDI`):
    * `NAME Given /Surname/`
    * `SEX M` / `F`
    * Fact tags: `BIRT`, `DEAT`, `BURI`, `CHR`, `MARR`, `RESI`, `OCCU` with `DATE` and `PLAC`.
    * Source citations: `SOUR @S<id>@`.
    * Family links: `FAMS @F<id>@` (spouse) and `FAMC @F<id>@` (child).
  * Synthesizes `FAM` family units (`0 @F<id>@ FAM`):
    * `HUSB @I<husband_pid>@`, `WIFE @I<wife_pid>@`, `CHIL @I<child_pid>@`, and spousal marriage facts.
  * Generates `SOUR` repository citations (`0 @S<id>@ SOUR`):
    * `TITL`, `AUTH`, `NOTE` with web links and citation text.
  * Supports options:
    * `max_generation`: cap depth (e.g. Gen 5, 10, or full 15).
    * `direct_only`: filter strictly to direct-line ancestors.

#### [NEW] [export_gedcom.py](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/export_gedcom.py)
* CLI tool:
  * `--out <path>`: Output `.ged` file (default: `data/beattie_pedigree.ged`).
  * `--max-gen <N>`: Optional maximum generation cap.
  * `--direct-only`: Flag to export direct ancestors only.
  * `--summary`: Show record counts (individuals, families, sources) written.

#### [NEW] [test_gedcom.py](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/tests/test_gedcom.py)
* Unit tests for GEDCOM formatting, header/trailer tags, name splitting (`Given /Surname/`), family synthesis, and date/place formatting.

---

### Phase 2: Candidate Review Commands (`confirm` / `reject`)

#### [MODIFY] [db.py](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/src/storage/db.py)
* Add `update_candidate_status(discovery_id, status)`: Updates status (`confirmed`, `rejected`, `pending`).
* Add `promote_candidate_to_source(discovery_id)`: Creates a formal entry in `sources` and `person_sources` for confirmed leads.

#### [MODIFY] [harvest_records.py](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/harvest_records.py)
* Add review CLI commands:
  * `--list-candidates`: Tabular display of candidate discoveries filtered by status or PID.
  * `--confirm <ID>`: Confirm a candidate discovery and promote it to a verified source.
  * `--reject <ID>`: Mark a candidate as rejected (ignoring in future runs).

---

### Phase 3: Scottish Gazetteer & Civil Parish Resolver

#### [NEW] [scottish_gazetteer.py](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/src/geo/scottish_gazetteer.py)
* Reference gazetteer of Scottish historical counties and civil parishes:
  * Maps archaic parish names (e.g. *Liberton*, *Colonsay*, *Aberdeen*, *Edinburgh St Giles/Canongate*, *Peebles*) to official National Records of Scotland (NRS) civil parish numbers.
  * Normalizes place strings in facts and person records.
  * Generates direct search URLs/parameters for ScotlandsPeople Old Parish Registers (OPR).

#### [NEW] [resolve_scottish_places.py](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/resolve_scottish_places.py)
* CLI utility to scan the 24 Scottish ancestors in our database, resolve their places, and report official parish jurisdictions.

#### [NEW] [test_gazetteer.py](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/tests/test_gazetteer.py)
* Unit tests for Scottish place resolution and NRS parish code lookups.

---

### Phase 4: Harvest Expansion across Generation 6–10 Brick Walls

* Target the **138 terminal brick-wall ancestors** in Generations 6 through 10.
* Run batch harvesting via `harvest_records.py --harvester all --target brick_walls --max-gen 10`.
* Store discoveries in `candidate_discoveries` and generate a master Markdown discovery report in `doc/reports/brick_walls_gen6_10_discoveries.md`.

---

## Verification Plan

### Automated Tests
1. Run pytest across the entire expanded test suite:
   ```bash
   pytest tests/test_gedcom.py -v
   pytest tests/test_gazetteer.py -v
   pytest -v
   ```

### Live Verification
1. **GEDCOM Export**:
   ```bash
   python3 export_gedcom.py --out data/beattie_pedigree.ged
   ```
   * Verify file header, trailer (`0 TRLR`), 2,603 `INDI` records, and valid `FAM` family structures.
2. **Candidate Review Commands**:
   ```bash
   python3 harvest_records.py --list-candidates --status pending
   python3 harvest_records.py --confirm 1
   python3 harvest_records.py --summary
   ```
3. **Scottish Gazetteer Resolver**:
   ```bash
   python3 resolve_scottish_places.py
   ```
4. **Generation 6–10 Harvest**:
   ```bash
   python3 harvest_records.py --harvester all --target brick_walls --max-gen 7 --limit 3 --export-markdown doc/reports/brick_walls_gen6_7_discoveries.md
   ```
