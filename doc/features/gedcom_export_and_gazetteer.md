# GEDCOM 5.5.1 Lineage-Linked Exporter, Candidate Review, and Scottish Gazetteer

## Overview
This feature completes the cycle of multi-source genealogical research by enabling standard cross-platform export, candidate discovery review with verified source promotion, Scottish civil parish resolution against National Records of Scotland (NRS) civil parish codes, and deep brick-wall lead generation across Generations 6–10.

---

## Architecture & Components

```
                +----------------------------+
                |    data/pedigree.sqlite    |
                +--------------+-------------+
                               |
        +----------------------+----------------------+
        |                      |                      |
        v                      v                      v
+------------------+  +-------------------+  +--------------------+
|  GedcomExporter  |  | Candidate Review  |  | Scottish Gazetteer |
| (export_gedcom)  |  | (harvest_records) |  | (resolve_scottish) |
+--------+---------+  +--------+----------+  +---------+----------+
         |                     |                       |
         v                     v                       v
data/pedigree.ged          sources & person_sources  doc/reports/scottish_
                           (promoted Tier 1/2)       ancestors_resolved.md
```

### 1. GEDCOM 5.5.1 Exporter (`src/gedcom/exporter.py` & `export_gedcom.py`)
- **Format Compliance:** Generates standard Lineage-Linked GEDCOM 5.5.1 in UTF-8 encoding.
- **Entity Coverage:**
  - Individuals (`0 @I_<PID>@ INDI`): Given/Surname (`GIVN`, `SURN`, `NSFX`), gender (`SEX`), vital events (`BIRT`, `CHR`, `DEAT`, `BURI` with `DATE` and `PLAC`), parent family pointer (`FAMC`), spouse family pointers (`FAMS`).
  - Families (`0 @F_<HUSB>_<WIFE>@ FAM`): Husband (`HUSB`), Wife (`WIFE`), Children (`CHIL`), Marriage events (`MARR` with `DATE` and `PLAC`).
  - Source Citations (`0 @S_<ID>@ SOUR`): Title (`TITL`), Repository/Author (`AUTH`), Publication (`PUBL`), Direct Link (`URL`), and Citation text (`NOTE`).
  - Inline Citations (`1 SOUR @S_<ID>@`): Linked directly from `INDI` and individual fact events.
- **Identifier Sanitization:** Hyphens in PIDs (e.g. `ABCD-123`) are normalized to underscores (`@I_ABCD_123@`) to prevent syntax errors in strict desktop parsers (Gramps, RootsMagic, Family Tree Maker).

#### CLI Usage:
```bash
# Full pedigree export
python3 export_gedcom.py --out data/pedigree.ged

# Direct ancestors only, capped at Generation 5
python3 export_gedcom.py --out data/direct_gen5.ged --direct-only --max-gen 5

# Fast export without source citations
python3 export_gedcom.py --out data/tree_fast.ged --no-sources
```

---

### 2. Candidate Review Commands (`harvest_records.py` & `src/storage/db.py`)
Provides interactive or scriptable review of harvested leads (`pending`, `confirmed`, `rejected`):
- **Listing Candidates:**
  ```bash
  python3 harvest_records.py --list-candidates --status pending
  ```
- **Confirming Candidates:**
  ```bash
  python3 harvest_records.py --confirm <ID>
  ```
  Sets candidate status to `'confirmed'`, automatically crafts a new verified source record in `sources` (`DISC_<ID>`), and links it in `person_sources` (`PS_DISC_<ID>`).
- **Rejecting Candidates:**
  ```bash
  python3 harvest_records.py --reject <ID>
  ```
  Sets candidate status to `'rejected'` without modifying core sources.

---

### 3. Scottish Gazetteer and Civil Parish Resolver (`src/geo/scottish_gazetteer.py` & `resolve_scottish_places.py`)
Maps archaic or colloquial Scottish place names to historical Scottish counties, official civil parishes, and National Records of Scotland (NRS) registration district numbers.
- **Data Coverage:** Reference registry of Scottish civil parishes with registration district codes (e.g., Liberton #693, St Cuthbert's Edinburgh #685/1, Alloa #465, Colonsay #539, Peebles #768).
- **Matching Engine:** Regex word-boundary scanning with county-compatibility checks to prevent false substring collisions (e.g., distinguishing "Annan" from "Clackmannanshire").
- **Research Links:** Automatically generates pre-populated ScotlandsPeople Old Parish Register (OPR) search URLs for births/baptisms, marriages, and deaths.

#### CLI Usage:
```bash
python3 resolve_scottish_places.py --export-markdown doc/reports/scottish_ancestors_resolved.md
```

---

### 4. Generation 6–10 Brick Wall Harvest Expansion
- Targets terminal ancestors in Generations 6–10 lacking parents in the local SQLite tree.
- Queries Library of Congress Chronicling America and Internet Archive collections.
- Discovered 37 high-confidence candidate records across early American and Scottish/Irish immigrant brick walls, including:
  - Sample Ancestor (`9ZMG-JSD`) – 70% match in Michigan newspapers (1888) and 1877 probate terms.
  - John Shields (`KN4P-VCG`) – 60% match in 1916 news and 1903 Pennsylvania records.
  - Eliza Jane Briggs (`GQ74-53T`) – 45% match on 1838 maritime arrivals and 1880 family monographs.
  - Charles ROBINSON (`LW5B-X1T`) – 60% match on 1911 Gate City press and 1859 maritime arrivals.

---

## Verification
- **Test Suite:** 54 automated unit tests passing in `tests/test_gedcom.py`, `tests/test_gazetteer.py`, `tests/test_harvesters.py`, `tests/test_audit.py`, `tests/test_constraints.py`, etc.
- **Live GEDCOM Export:** `data/pedigree.ged` generated with 2,617 `INDI`, 1,378 `FAM`, and 21,193 `SOUR` records (10.7 MB).
- **Live Scottish Resolution:** 27 events resolved across 24 ancestors.
- **Live Harvest:** 37 discoveries recorded in `data/pedigree.sqlite` and exported to `doc/reports/brick_walls_gen6_discoveries.md`.
