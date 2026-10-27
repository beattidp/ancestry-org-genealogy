# Feature Documentation: Pedigree Ingestion & Local SQLite Storage

**Feature Name:** Pedigree Ingestion & Local SQLite Storage  
**Status:** Implemented & Verified  
**Date:** 2026-10-27  
**Module(s):** `src/storage/db.py`, `src/pedigree/extractor.py`, `src/pedigree/ingest.py`, `ingest.py`, `tree_summary.py`

---

## 1. Architectural Overview

This feature enables automated downloading, normalization, and local storage of multi-generational ancestry trees from FamilySearch into a structured SQLite database. It forms the offline evidentiary data layer upon which source auditing, automated GPS verification, and record linkage operate.

```
+------------------------------------------------------------------------+
|                          FamilySearch Cloud                            |
|                 GET /platform/tree/ancestry?person={pid}               |
+-----------------------------------|------------------------------------+
                                    | Raw GEDCOM X Payload
                                    v
+------------------------------------------------------------------------+
|                      src/pedigree/extractor.py                         |
|                                                                        |
|  - extract_person(): Normalized names, gender, vitals                  |
|  - extract_facts(): Granular birth, death, marriage, residences        |
|  - extract_relationships(): Explicit Couple & ParentChild records      |
|  - derive_pedigree_parent_child_relationships(): Ahnentafel derivation |
|  - calculate_generation_and_path(): Mathematical generation & path     |
+-----------------------------------|------------------------------------+
                                    | Clean Domain Models
                                    v
+------------------------------------------------------------------------+
|                        src/pedigree/ingest.py                          |
|                     (PedigreeIngester Engine)                          |
|                                                                        |
|  1. Ingestion run lifecycle tracking                                   |
|  2. Persons batch insertion                                            |
|  3. Pedigree tree node position mapping                                |
|  4. Granular facts replacement                                         |
|  5. Explicit + derived relationships linking                           |
|  6. Real-time terminal progress reporting                              |
+-----------------------------------|------------------------------------+
                                    | Atomic Transactions
                                    v
+------------------------------------------------------------------------+
|                           src/storage/db.py                            |
|                      data/pedigree.sqlite (WAL Mode)                   |
|                                                                        |
|  - persons (pid PK, name, gender, lifespan, living, vitals, raw_json)  |
|  - relationships (id PK, rel_type, parent_pid, child_pid, couple)     |
|  - pedigree_tree (root_pid, person_pid, generation, ascendancy_number)  |
|  - facts (id PK, person_pid, fact_type, dates, places, raw_json)       |
|  - ingestion_runs (id PK, root_pid, max_generations, status)          |
+------------------------------------------------------------------------+
```

---

## 2. API Usage & CLI Operations

### Programmatic Usage
```python
from src.storage.db import Database
from src.familysearch.client import FamilySearchClient
from src.pedigree.ingest import PedigreeIngester

# Initialize components
db = Database("data/pedigree.sqlite")
client = FamilySearchClient()
ingester = PedigreeIngester(client, db)

# Ingest 4 generations of ancestors
result = ingester.ingest_ancestry(
    root_pid="ABCD-123",
    max_generations=4,
    progress_callback=lambda desc, curr, tot: print(f"{desc} ({curr}/{tot})")
)

print(f"Ingested {result.total_persons} ancestors and {result.total_relationships} relationships.")

# Query offline stats
stats = db.get_pedigree_stats("ABCD-123")
gaps = db.get_pedigree_gaps("ABCD-123", max_generation=5)
```

### CLI Ingestion Command
```bash
# Ingest 4 generations (auto-detects root PID from authenticated user)
python ingest.py --generations 4 --db data/pedigree.sqlite

# Ingest custom root PID and custom depth
python ingest.py --root ABCD-123 --generations 6 --db data/pedigree.sqlite
```

### Offline Inspection Command
```bash
# Display generational breakdown, pedigree brick walls, and earliest ancestors
python tree_summary.py --db data/pedigree.sqlite
```

---

## 3. Verification & Metrics

* **Unit Test Suite:** 16 automated unit tests in `tests/test_storage.py`, `tests/test_ingestion.py`, `tests/test_auth.py`, and `tests/test_client.py`.
* **Live Ingestion Verification:**
  * Root PID: `ABCD-123` (Sample User)
  * Generations Ingested: 4
  * Total Ancestors Persisted: 32
  * Total Relationships Persisted: 54
  * Total Granular Facts Indexed: 256
  * Target Brick Walls Identified: 16 (Generation 4 ancestors with unlinked parents)
