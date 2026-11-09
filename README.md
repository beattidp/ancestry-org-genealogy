# ancestry-genealogy

_High-Confidence Research Architecture for FamilySearch with Deterministic Constraint Engine, Source Classification, Evidence Weighting, External Record Harvesters, and Recursive Frontier Ingestion._

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests: Pytest](https://img.shields.io/badge/tests-pytest-green.svg)](tests/)

---

## Documentation

📖 **Looking for step-by-step instructions?**  
See the **[User Guide](doc/user_guide.md)** for a full tutorial covering installation, credential setup, database schema, and detailed command-line usage for all tools.

---

## Overview & Intended Use

**ancestry-genealogy** is an offline-first research framework designed for genealogists, researchers, and engineers seeking high evidentiary confidence when working with the FamilySearch Family Tree.

Collaborative public family trees often accumulate errors: conflated individuals, anachronistic dates, physically impossible parent-child ages, and unverified assertions. This project provides an automated evidentiary firewall and research accelerator that applies the **Genealogical Proof Standard (GPS)** to your family history.

### Primary Use Cases

* **Offline Archival & Deep Analysis:** Download multi-generational ancestral trees into a local SQLite database for instant, offline querying and analysis without repeated API calls.
* **Deterministic Rule Validation:** Detect biological and chronological anomalies (e.g. parents born after children, mothers giving birth outside biological ages, marriages before birth).
* **Evidentiary Auditing & GPS Scoring:** Evaluate attached sources, classify citations into primary vs. secondary evidence tiers, and calculate composite confidence ratings (0–100%).
* **Recursive Frontier Expansion:** Traverse beyond standard generation limits to ingest ancestral lines up to 15+ generations.
* **External Record Harvesting:** Automatically search open historical archives (Library of Congress Chronicling America, Internet Archive) for corroborating evidence.
* **Geospatial & Archaic Place Resolution:** Standardize archaic, handwritten, or regional place names (e.g. historical Scottish civil parishes) against official gazetteers and geocode them.
* **Targeted, Safe Synchronization:** Stage confirmed discoveries and standardized place data locally, reviewing changes before selectively syncing back to FamilySearch.
* **Standard Interoperability:** Export validated pedigree knowledge graphs to clean GEDCOM 5.5.1 files for visualization in tools like [Topola Viewer](https://pewu.github.io/topola-viewer) or desktop genealogy suites.

---

## Core Capabilities

| Component | Script / Module | Capability Description |
|---|---|---|
| **API Probe** | `scripts/probe.py` | Validates session authentication, token health, and API connectivity. |
| **Pedigree Ingester** | `scripts/ingest.py` | Ingests base pedigree (1–7 gen) and recursively expands frontier leaf ancestors (8–15+ gen). |
| **Tree Inspector** | `scripts/tree_summary.py` | Reports offline generational completeness, earliest ancestors, and brick walls. |
| **Constraint Engine** | `scripts/validate_tree.py` | Validates parent age gaps, lifespans, post-mortem births, and marital sequence. |
| **Source Auditor** | `scripts/audit_sources.py` | Evaluates evidence quality, assigns GPS confidence tiers, and scores pedigree strength. |
| **Record Harvester** | `scripts/harvest_records.py` | Searches Chronicling America (newspapers) and Internet Archive (passenger lists/books). |
| **Scottish Gazetteer** | `scripts/resolve_scottish_places.py` | Maps archaic Scottish locations to official NRS civil parishes and coordinates. |
| **Targeted Sync** | `scripts/sync_discoveries.py` | Safe dry-run staging and selective write-back to FamilySearch Tree. |
| **GEDCOM Exporter** | `scripts/export_gedcom.py` | Exports local database to standard GEDCOM 5.5.1 format. |

---

## Quickstart

### 1. Installation

```bash
git clone https://github.com/beattidp/ancestry-org-genealogy.git
cd ancestry-org-genealogy
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configuration

Copy `.env.example` to `.env` and provide your active FamilySearch session ID (`fssessionid` from your browser cookies):

```bash
cp .env.example .env
# Edit .env and paste your session token:
# FAMILYSEARCH_SESSION_ID="your_token_here"
```

Verify your credentials:

```bash
python scripts/probe.py
```

### 3. Ingest & Inspect Pedigree

Download 7 generations into your local SQLite database:

```bash
python scripts/ingest.py --generations 7
```

View generational counts and brick walls:

```bash
python scripts/tree_summary.py
```

### 4. Validate & Audit

Run the biological constraint engine:

```bash
python scripts/validate_tree.py
```

Audit source evidence and calculate GPS confidence ratings:

```bash
python scripts/audit_sources.py --fetch
```

### 5. Export for Interactive Visualization

Export standard GEDCOM 5.5.1 and open in [Topola Viewer](https://pewu.github.io/topola-viewer):

```bash
python scripts/export_gedcom.py --out data/pedigree.ged
```

For complete usage instructions and advanced options, consult the **[User Guide](doc/user_guide.md)**.

---

## Repository Structure

```
├── doc/
│   ├── features/              # Feature implementation and architectural specs
│   └── user_guide.md          # Comprehensive end-to-end user manual
├── scripts/                   # User-facing CLI utilities
│   ├── audit_sources.py       # Evidence scoring & citation auditing
│   ├── export_gedcom.py       # GEDCOM 5.5.1 export utility
│   ├── harvest_records.py     # External historical record harvester
│   ├── ingest.py              # Pedigree ingestion & recursive expansion
│   ├── probe.py               # API probe & credential validator
│   ├── resolve_scottish_places.py # Scottish parish & gazetteer resolver
│   ├── sync_discoveries.py    # Targeted FamilySearch synchronization
│   ├── tree_summary.py        # Offline database summary & gap analysis
│   └── validate_tree.py       # Deterministic constraint validation
├── src/                       # Core engine modules
│   ├── audit/                 # Evidence scoring and classification
│   ├── constraints/           # Chronological & biological constraint rules
│   ├── familysearch/          # API client, session manager & sync engine
│   ├── gedcom/                # GEDCOM 5.5.1 generation
│   ├── geo/                   # Scottish civil parish gazetteer
│   ├── pedigree/              # GEDCOM X parsers and graph extractors
│   ├── sources/               # Chronicling America & Internet Archive harvesters
│   └── storage/               # SQLite WAL database manager & schema
├── tests/                     # Automated unit and integration test suite
├── .env.example               # Configuration template
├── pytest.ini                 # Pytest configuration
└── requirements.txt           # Python package dependencies
```

---

## Verification & Testing

The test suite includes comprehensive tests for database storage, GEDCOM X parsing, constraint engines, harvesters, gazetteers, and synchronization:

```bash
pytest -v
```

---

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

---

### Credit where Credit is Due:
The code for this application was developed with [Google Antigravity](http://antigravity.google/).  _Thank you!_

