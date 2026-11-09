# User Guide: High-Confidence FamilySearch Research & Pedigree Engine

Welcome to the **High-Confidence Research Architecture for FamilySearch**. This system is an offline-first genealogical research engine designed to build, validate, audit, and enhance multi-generational family trees with deterministic constraints and evidentiary rigor based on the **Genealogical Proof Standard (GPS)**.

---

## Table of Contents

1. [Architectural Overview & Philosophy](#1-architectural-overview--philosophy)
2. [Prerequisites & Installation](#2-prerequisites--installation)
3. [Configuration & Authentication](#3-configuration--authentication)
4. [Command-Line Tool Reference](#4-command-line-tool-reference)
   - [API Connection Probe (`scripts/probe.py`)](#41-api-connection-probe-scriptsprobepy)
   - [Pedigree Ingestion Engine (`scripts/ingest.py`)](#42-pedigree-ingestion-engine-scriptsingestpy)
   - [Offline Tree Inspector (`scripts/tree_summary.py`)](#43-offline-tree-inspector-scriptstree_summarypy)
   - [Deterministic Constraint Validator (`scripts/validate_tree.py`)](#44-deterministic-constraint-validator-scriptsvalidate_treepy)
   - [Source Citation Auditor (`scripts/audit_sources.py`)](#45-source-citation-auditor-scriptsaudit_sourcespy)
   - [External Record Harvester (`scripts/harvest_records.py`)](#46-external-record-harvester-scriptsharvest_recordspy)
   - [Scottish Gazetteer & Place Resolver (`scripts/resolve_scottish_places.py`)](#47-scottish-gazetteer--place-resolver-scriptsresolve_scottish_placespy)
   - [Targeted FamilySearch Synchronizer (`scripts/sync_discoveries.py`)](#48-targeted-familysearch-synchronizer-scriptssync_discoveriespy)
   - [Standard GEDCOM 5.5.1 Exporter (`scripts/export_gedcom.py`)](#49-standard-gedcom-551-exporter-scriptsexport_gedcompy)
5. [Local Database Schema](#5-local-database-schema)
6. [Common Research Workflows](#6-common-research-workflows)
7. [Best Practices & Security](#7-best-practices--security)

---

## 1. Architectural Overview & Philosophy

Collaborative online trees (such as FamilySearch Family Tree) frequently suffer from conflated personas, erroneous merges, chronologically impossible parent-child relationships, and unverified source citations.

This toolkit provides an evidentiary firewall and high-confidence research framework:

* **Offline-First Knowledge Graph:** Downloads and normalizes pedigree data into a local SQLite database (`data/pedigree.sqlite`) configured with Write-Ahead Logging (WAL) for rapid local querying.
* **Deterministic Biological & Chronological Constraints:** Evaluates every lineage against strict biological rules (e.g., maximum maternal age at childbirth, birth after parental death, marriage before birth) before accepting relationships as verified.
* **Evidence Weighting & GPS Scoring:** Audits every source citation, classifying evidence into primary vs. secondary tiers and calculating a composite confidence score (0–100%) for each person.
* **Recursive Frontier Expansion:** Automatically traverses beyond standard API depth limits (typically 4–8 generations) by identifying leaf ancestors and recursively fetching ancestral frontiers up to 15+ generations.
* **External Record Linkage:** Harvesters query open historical databases (such as Library of Congress Chronicling America and Internet Archive) to discover missing records for brick-wall ancestors.
* **Archaic Place Resolution:** Standardizes historical, misspelled, or archaic parish and county names against authoritative geospatial gazetteers (e.g., National Records of Scotland).
* **Controlled, Targeted Synchronization:** Provides safe, dry-run-first mutation capabilities to post verified citations and standardized coordinates back to FamilySearch.

---

## 2. Prerequisites & Installation

### Requirements
* **Python:** 3.11 or higher
* **Operating System:** Linux, macOS, or Windows (WSL recommended for Windows)
* **Git**

### Installation Steps

1. **Clone the repository:**
   ```bash
   git clone https://github.com/beattidp/ancestry-org-genealogy.git
   cd ancestry-org-genealogy
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
   *(On Windows PowerShell: `.\.venv\Scripts\Activate.ps1`)*

3. **Install dependencies:**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. **Verify test suite:**
   ```bash
   pytest
   ```
   All unit and integration tests should pass cleanly.

---

## 3. Configuration & Authentication

The tool interacts with the FamilySearch GEDCOM X REST API. It uses session token authentication (`fssessionid`), allowing you to leverage your active FamilySearch browser login without registering a complex OAuth client ID.

### Step 1: Create Your `.env` File

Copy the template configuration file:
```bash
cp .env.example .env
```

### Step 2: Extract Your `fssessionid` Cookie

1. Open your web browser and log in to [FamilySearch](https://www.familysearch.org).
2. Open Developer Tools:
   * **Chrome / Edge / Brave:** Press `F12` or `Ctrl+Shift+I` (macOS: `Cmd+Option+I`), navigate to the **Application** tab, and expand **Cookies** > `https://www.familysearch.org`.
   * **Firefox:** Press `F12`, navigate to the **Storage** tab, and expand **Cookies** > `https://www.familysearch.org`.
3. Locate the cookie named **`fssessionid`**.
4. Copy its value (a long alphanumeric string).

### Step 3: Populate `.env`

Edit `.env` and set the session token:
```ini
# FamilySearch Session ID (keep quotes around the string)
FAMILYSEARCH_SESSION_ID="YOUR_FSSESSIONID_TOKEN_HERE"

# API Environment: "production" (default) or "beta"
FAMILYSEARCH_ENV="production"

# Optional: Developer App Key (only needed if using official OAuth2 developer keys)
FAMILYSEARCH_APP_KEY=""
```

### Step 4: Verify Connection

Run the probe utility to ensure your credentials are valid:
```bash
python scripts/probe.py
```

---

## 4. Command-Line Tool Reference

All primary tools are located in the `scripts/` directory and can be executed from the project root.

```
scripts/
├── probe.py                  # API credential and connectivity validation
├── ingest.py                 # Pedigree download & recursive frontier expansion
├── tree_summary.py           # Offline generational breakdown & brick-wall report
├── validate_tree.py          # Biological & chronological constraint checker
├── audit_sources.py          # Evidence auditor & GPS confidence scorer
├── harvest_records.py        # External newspaper & archive record harvester
├── resolve_scottish_places.py # Scottish parish & NRS gazetteer resolver
├── sync_discoveries.py       # Targeted FamilySearch write-back engine
└── export_gedcom.py          # Standard GEDCOM 5.5.1 knowledge graph exporter
```

---

### 4.1 API Connection Probe (`scripts/probe.py`)

Checks your `.env` configuration, verifies FamilySearch API reachability, and reports your authenticated identity.

```bash
python scripts/probe.py
```

#### Output Details:
* Authenticated Display Name and User ID (`cis.user.XXXX`)
* Current Tree Root Person PID (if available)
* Active API endpoint URL

---

### 4.2 Pedigree Ingestion Engine (`scripts/ingest.py`)

Downloads ancestor trees directly from FamilySearch and stores them in your local SQLite database (`data/pedigree.sqlite`).

```bash
# Ingest 7 base generations (auto-detects root PID from authenticated user)
python scripts/ingest.py --generations 7

# Ingest starting from a specific person PID and recursively expand to generation 12
python scripts/ingest.py --root ABCD-123 --generations 7 --recursive-to 12

# Specify a custom database path
python scripts/ingest.py --root ABCD-123 --generations 5 --db data/my_tree.sqlite
```

#### Command Options:
| Flag | Type | Default | Description |
|---|---|---|---|
| `--root` | `string` | *(auto-detect)* | Root Person PID (e.g. `ABCD-123`). If omitted, detects root PID from session. |
| `--generations` | `int` | `7` | Base ancestor generations to ingest in a single pass (max 8 per API call). |
| `--recursive-to` | `int` | `10` | Recursive target depth for frontier leaf ancestors (`0` to disable). |
| `--db` | `string` | `data/pedigree.sqlite` | Path to SQLite database file. |

---

### 4.3 Offline Tree Inspector (`scripts/tree_summary.py`)

Analyzes your local SQLite database without requiring internet access or API tokens.

```bash
# Summarize the default database
python scripts/tree_summary.py

# Inspect a specific root PID or custom database
python scripts/tree_summary.py --root ABCD-123 --db data/pedigree.sqlite
```

#### Output Sections:
1. **Generational Breakdown:** Ancestor counts per generation and theoretical completeness percentage.
2. **Pedigree Gaps & Brick Walls:** Frontier ancestors whose parents are not yet recorded, highlighting opportunities for further research.
3. **Earliest Known Ancestors:** Chronologically oldest ancestors recorded in the tree.

---

### 4.4 Deterministic Constraint Validator (`scripts/validate_tree.py`)

Executes rigorous rule-based checks on parent-child relationships, marital dates, and vital timelines to catch impossible or improbable genealogy data.

```bash
# Validate the entire database tree
python scripts/validate_tree.py

# Validate a specific ancestral subtree
python scripts/validate_tree.py --root ABCD-123

# Validate an individual person
python scripts/validate_tree.py --pid ABCD-123

# Persist all detected violations to the database
python scripts/validate_tree.py --persist
```

#### Validation Rules Enforced:
* **Maternal Age at Birth:** Mother must be between 12 and 55 years old at child's birth.
* **Paternal Age at Birth:** Father must be at least 12 years old at child's birth.
* **Post-Mortem Childbirth:** Child cannot be born after mother's death, or more than 9 months after father's death.
* **Lifespan Outliers:** Flags lifespans exceeding 115 years or death preceding birth.
* **Chronological Sequence:** Marriage must not occur prior to birth or after death.

---

### 4.5 Source Citation Auditor (`scripts/audit_sources.py`)

Evaluates the evidentiary backing of every person in your tree against the **Genealogical Proof Standard (GPS)**.

```bash
# Audit sources currently cached in the local database
python scripts/audit_sources.py

# Fetch latest attached sources from FamilySearch API before auditing
python scripts/audit_sources.py --fetch

# Force re-fetching sources even if already cached locally
python scripts/audit_sources.py --fetch --refresh

# Audit only deep ancestral generations (e.g. generations 8 through 15)
python scripts/audit_sources.py --min-gen 8 --max-gen 15
```

#### Scoring Model:
* **Tier 1 (Direct Vital Evidence):** Civil birth, marriage, death records, parish baptisms, and censuses (+25 to +40 pts).
* **Tier 2 (Secondary / Derivative Evidence):** Wills, probate, military records, passenger manifests (+10 to +20 pts).
* **Tier 3 (User-Submitted / Unverified):** User genealogies, pedigree resource files, personal notes without citations (0 to +5 pts).
* **Composite Confidence Rating:**
  * **90–100%:** Highly Confirmed (multiple corroborating primary sources).
  * **70–89%:** Confirmed (primary source for vitals or parentage).
  * **50–69%:** Plausible / Needs Review (secondary evidence only).
  * **< 50%:** Unsubstantiated / High Risk (lacks primary documentation).

---

### 4.6 External Record Harvester (`scripts/harvest_records.py`)

Searches open historical archives to uncover corroborating evidence and primary source citations for brick-wall ancestors.

```bash
# Harvest discoveries for all frontier ancestors in generation 5
python scripts/harvest_records.py --generation 5

# Target a specific ancestor by PID
python scripts/harvest_records.py --pid ABCD-123

# Filter to records with high matching confidence (e.g. >= 0.75)
python scripts/harvest_records.py --generation 6 --min-score 0.75
```

#### Supported Harvesters:
1. **Library of Congress Chronicling America:** Scans historical US newspapers (1777–1963) for obituaries, marriage notices, and legal citations.
2. **Internet Archive:** Queries historical passenger manifests, immigration records, and regional county history volumes.

---

### 4.7 Scottish Gazetteer & Place Resolver (`scripts/resolve_scottish_places.py`)

Standardizes archaic, handwritten, or phonetically spelled Scottish place names against the **National Records of Scotland (NRS)** gazetteer of civil parishes and registration districts.

```bash
# Resolve all Scottish birth and death places in the database
python scripts/resolve_scottish_places.py

# Export a detailed Markdown resolution report
python scripts/resolve_scottish_places.py --export-markdown doc/reports/scottish_resolved.md
```

#### Capabilities:
* Resolves historical parish variations (e.g., *"St. Andrews and St. Leonards"*, *"Dundonald, Ayr"*, *"Govan, Lanark"*).
* Maps each parish to its official **NRS 3-digit civil parish code**.
* Attaches precise latitude and longitude centroid coordinates.

---

### 4.8 Targeted FamilySearch Synchronizer (`scripts/sync_discoveries.py`)

Provides a safe, selective write-back mechanism to sync validated discoveries, sources, and standardized geospatial coordinates back to FamilySearch Tree records.

> [!IMPORTANT]
> By default, `sync_discoveries.py` runs in **DRY-RUN mode**. No changes will be written to FamilySearch unless the `--live` flag is explicitly supplied.

```bash
# Dry-run inspection: preview all staged discoveries and parish updates
python scripts/sync_discoveries.py

# Filter preview to a single person PID
python scripts/sync_discoveries.py --pid ABCD-123

# Execute live synchronization to FamilySearch (requires active session)
python scripts/sync_discoveries.py --pid ABCD-123 --live

# Target the FamilySearch Beta sandbox environment
python scripts/sync_discoveries.py --env beta --live
```

---

### 4.9 Standard GEDCOM 5.5.1 Exporter (`scripts/export_gedcom.py`)

Exports your local SQLite pedigree graph into an industry-standard GEDCOM 5.5.1 file, ready for import into desktop genealogy software or interactive visualization tools such as [Topola Viewer](https://pewu.github.io/topola-viewer).

```bash
# Export the entire pedigree tree to data/pedigree.ged
python scripts/export_gedcom.py

# Export up to generation 8, direct ancestors only, excluding sources
python scripts/export_gedcom.py --max-gen 8 --direct-only --no-sources --out data/export_gen8.ged
```

#### Command Options:
| Flag | Type | Default | Description |
|---|---|---|---|
| `--out` | `string` | `data/pedigree.ged` | Destination GEDCOM file path. |
| `--max-gen` | `int` | `None` *(all)* | Maximum generation to export (e.g., 5 or 10). |
| `--direct-only` | `flag` | `False` | Exclude collateral spouses and non-direct relatives. |
| `--no-sources` | `flag` | `False` | Exclude source citations from the exported file. |
| `--db-path` | `string` | `data/pedigree.sqlite` | Source SQLite database file. |

---

## 5. Local Database Schema

The SQLite database (`data/pedigree.sqlite`) is structured into relational tables:

```
+-------------------------------------------------------------------------------+
|                             data/pedigree.sqlite                              |
+-------------------------------------------------------------------------------+
|  persons               - Normalized identity, vitals, lifespans, raw JSON     |
|  relationships         - Couple & ParentChild edges with validation status     |
|  pedigree_tree         - Ahnentafel numbers, generation index, root relations  |
|  facts                 - Granular birth, death, marriage, and residence facts  |
|  sources               - Source descriptions, URLs, titles, and citations      |
|  source_audits         - Algorithmic GPS confidence scores and source tiers    |
|  candidate_discoveries - Harvester matches from external historical archives    |
|  constraint_violations - Persisted biological and chronological violations    |
|  ingestion_runs        - Tracking for multi-generational ingestion jobs        |
+-------------------------------------------------------------------------------+
```

---

## 6. Common Research Workflows

### Workflow A: New Tree Setup & Baseline Audit
1. Configure credentials:
   ```bash
   cp .env.example .env
   # Add your fssessionid to .env
   python scripts/probe.py
   ```
2. Ingest 7 base generations:
   ```bash
   python scripts/ingest.py --generations 7
   ```
3. Inspect tree summary:
   ```bash
   python scripts/tree_summary.py
   ```
4. Run biological validation:
   ```bash
   python scripts/validate_tree.py --persist
   ```
5. Audit attached sources:
   ```bash
   python scripts/audit_sources.py --fetch
   ```

---

### Workflow B: Breaking a Brick Wall at Generation 8+
1. Recursively expand frontier leaf ancestors:
   ```bash
   python scripts/ingest.py --generations 7 --recursive-to 10
   ```
2. Locate brick walls using the summary tool:
   ```bash
   python scripts/tree_summary.py
   ```
3. Harvest external records for frontier ancestors:
   ```bash
   python scripts/harvest_records.py --generation 8 --min-score 0.70
   ```
4. Resolve Scottish places:
   ```bash
   python scripts/resolve_scottish_places.py
   ```
5. Review staged updates and perform live synchronization:
   ```bash
   python scripts/sync_discoveries.py --pid <TARGET_PID>
   python scripts/sync_discoveries.py --pid <TARGET_PID> --live
   ```

---

### Workflow C: Visualizing in Topola Viewer
1. Export clean GEDCOM:
   ```bash
   python scripts/export_gedcom.py --out data/tree_visual.ged
   ```
2. Open [Topola Genealogy Viewer](https://pewu.github.io/topola-viewer) in your browser.
3. Load `data/tree_visual.ged` to explore an interactive, publication-quality pedigree chart.

---

## 7. Best Practices & Security

* **Never commit `.env`:** The `.gitignore` file is configured to exclude `.env` to prevent accidental disclosure of session cookies.
* **Session Expiration:** FamilySearch browser session cookies typically expire after 24 hours of inactivity. If `probe.py` or `ingest.py` reports an authentication error, refresh your browser session and update `FAMILYSEARCH_SESSION_ID` in `.env`.
* **Dry-Run by Default:** Always preview write operations using `scripts/sync_discoveries.py` before adding the `--live` flag.
* **Rate Limiting & Politeness:** The client architecture implements exponential backoff for HTTP 429 and 503 status codes. Avoid executing multiple ingestion runs concurrently against the FamilySearch API.
