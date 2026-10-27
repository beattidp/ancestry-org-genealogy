# Walkthrough — Deterministic Biological & Chronological Constraint Engine

We have designed, implemented, and verified the **Deterministic Biological & Chronological Constraint Engine** (Milestone 4). The engine enforces physical and biological laws across pedigree graphs, detecting chronological contradictions, generational inversions, and biological impossibilities with date-uncertainty awareness.

---

## 1. What Was Created & Implemented

### Storage Layer (`src/storage/db.py`)
* Added table and indexes:
  * `constraint_violations`: Stores detected anomalies (`rule_id`, `severity`, `person_pid`, `relative_pid`, `description`, `details_json`, `created_at`).
  * Added indexes on `person_pid`, `rule_id`, and `severity`.
* Added database operations:
  * `record_violations_batch`: Bulk inserts violation records with optional cleanup.
  * `get_violations`: Queries violations with person names, lifespans, and pedigree metadata.
  * `clear_violations`: Clears violations globally or for a specific person.
  * `get_violations_summary`: Returns aggregated counts by severity, rule, and affected individuals.

### Constraint Engine Package (`src/constraints/`)
* **[src/constraints/date_parser.py](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/src/constraints/date_parser.py)**:
  * Parses GEDCOM X formal dates (`+YYYY-MM-DD`, `+YYYY-MM`, `+YYYY`, ranges `/`) and historical text formats (`22 November 1919`, `19660421`, `Jul 1937`, `about 1850`).
  * Computes exact days difference and fractional years while respecting date uncertainty intervals.
* **[src/constraints/rules.py](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/src/constraints/rules.py)**:
  * Individual Chronology: Event sequencing (`CHRONO-EVENT-ORDER`), Lifespan limits (`CHRONO-LIFESPAN`), Marriage ages (`CHRONO-MARR-AGE`).
  * Parent-Child Biology: Generational inversions (`REL-INVERSION`), Mother age 13–50 (`BIO-MOTH-AGE`), Mother posthumous births (`BIO-MOTH-POSTHUMOUS`), Father age 14–85 (`BIO-FATH-AGE`), Father posthumous births within 280 days (`BIO-FATH-POSTHUMOUS`).
  * Spousal Chronology: Marriage after death, marriage ages below legal/biological minimums.
* **[src/constraints/engine.py](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/src/constraints/engine.py)**:
  * `ConstraintEngine`: Coordinates graph loading, rule execution, and aggregate metric reporting across arbitrary depths and subtrees.
  * Supports scoping by subtree root (`root_pid`), single individual (`person_pid`), or GPS confidence threshold (`min_confidence`).

### CLI Tool
* **[validate_tree.py](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/validate_tree.py)**:
  * Interactive CLI utility:
    ```bash
    python validate_tree.py --db data/pedigree.sqlite --persist
    ```
  * Renders Rich overview panels, pass rate, and detailed anomaly tables.

---

## 2. Verification Results

### Automated Unit Tests
Executed `pytest` across all suites:
```text
============================= test session starts ==============================
platform linux -- Python 3.13.1, pytest-9.1.1, pluggy-1.7.0
rootdir: /home/beattidp/Documents/antigravity/ancestry-genealogy
configfile: pytest.ini
testpaths: tests
plugins: anyio-4.15.1
collected 34 items

tests/test_audit.py .......                                              [ 20%]
tests/test_auth.py ...                                                   [ 29%]
tests/test_client.py ....                                                [ 41%]
tests/test_constraints.py ...........                                    [ 73%]
tests/test_ingestion.py .....                                            [ 88%]
tests/test_storage.py ....                                               [100%]

============================== 34 passed in 1.64s ==============================
```

### Live Pedigree Validation Results
Ran `python validate_tree.py --db data/pedigree.sqlite --persist` against the live local database:

```text
Genealogical Constraint & Biological Anomaly Validator

╭────────────────────────────── Validation Scope ──────────────────────────────╮
│ Subtree Root: KWHS-6NN                                                       │
│ Database: data/pedigree.sqlite                                               │
│ Persist to DB: Yes                                                           │
╰──────────────────────────────────────────────────────────────────────────────╯
╭────────────────────── Validation Summary & Compliance ───────────────────────╮
│ Total Persons Evaluated: 32                                                  │
│ Total Relationships Evaluated: 54                                            │
│ Pedigree Biological Pass Rate: 100.0%                                        │
│                                                                              │
│ Critical Errors: 0  |  Warnings / Outliers: 0  |  Informational: 0            │
│                                                                              │
│ ✓ No biological or chronological violations detected!                        │
│                                                                              │
╰──────────────────────────────────────────────────────────────────────────────╯
╭──────────────────────────────────────────────────────────────────────────────╮
│ ✓ 100% Deterministic Compliance: All assessed individuals, parent-child      │
│ generations, and marriages satisfy chronological and biological laws.        │
╰──────────────────────────────────────────────────────────────────────────────╯
Persisted 0 violation records into table 'constraint_violations'.
```

### Targeted Validated-Ancestor & Filter Tests
1. **Targeting Single Validated Ancestor (`KJJ4-83J`, John Chandler Beattie):**
   ```bash
   python validate_tree.py --db data/pedigree.sqlite --pid KJJ4-83J
   ```
   * Result: Evaluated 1 person, 4 relationships — **100% Pass Rate (0 errors)**.
2. **Filtering by GPS High-Confidence Corroboration (`--min-confidence 70`):**
   ```bash
   python validate_tree.py --db data/pedigree.sqlite --min-confidence 70
   ```
   * Result: Evaluated 13 primary-source-verified ancestors and 42 relationships — **100% Pass Rate (0 errors)**.
