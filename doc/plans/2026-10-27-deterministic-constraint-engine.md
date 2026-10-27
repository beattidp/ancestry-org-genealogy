# Deterministic Biological & Chronological Constraint Engine

A genealogical tree can only be considered high-confidence if all claims adhere strictly to biological reality and chronological physics. This milestone implements an automated, deterministic **Constraint & Anomaly Engine** that analyzes all ancestors, relationships, and life events in the local SQLite database to detect impossibilities, biological anomalies, and chronological conflicts.

---

## 1. Objectives & Rule Specifications

The engine applies rigorous rules across individual life events and parent-child/spousal relationships. Every violation is categorized by severity:
* **CRITICAL / ERROR**: Physically or biologically impossible claims (e.g., child born after mother's death, child born before parent, negative lifespans).
* **WARNING**: Highly improbable or biologically extreme claims that require special corroboration (e.g., mother aged 13–14 or 46–50 at birth, father aged > 70, marriage age < 14).
* **INFO**: Incomplete data preventing definitive constraint validation (e.g., missing birth or death year).

### Rule Catalog

| Rule ID | Category | Description | Severity | Thresholds |
|---|---|---|---|---|
| `BIO-MOTH-AGE` | Biological | Mother's age at child's birth | `ERROR` / `WARNING` | Error: $< 13$ or $> 50$ yrs.<br>Warning: $13 \le age < 15$ or $46 \le age \le 50$. |
| `BIO-MOTH-POSTHUMOUS` | Biological | Child born after mother's death | `ERROR` | Child birth date $>$ mother death date. |
| `BIO-FATH-AGE` | Biological | Father's age at child's conception/birth | `ERROR` / `WARNING` | Error: $< 14$ or $> 85$ yrs.<br>Warning: $14 \le age < 16$ or $70 \le age \le 85$. |
| `BIO-FATH-POSTHUMOUS` | Biological | Child born after father's death | `ERROR` | Child birth date $>$ father death date + 280 days (9.5 months). |
| `CHRONO-EVENT-ORDER` | Chronological | Event sequence consistency | `ERROR` | Birth $\le$ Christening $\le$ Marriage $\le$ Death $\le$ Burial. |
| `CHRONO-LIFESPAN` | Chronological | Plausible human lifespan | `ERROR` / `WARNING` | Error: $< 0$ (death before birth) or $> 120$ yrs.<br>Warning: $> 100$ yrs. |
| `CHRONO-MARR-AGE` | Chronological | Plausible age at marriage | `ERROR` / `WARNING` | Error: $< 12$ or $> 100$ yrs.<br>Warning: $12 \le age < 15$. |
| `REL-INVERSION` | Relational | Generational time inversion | `ERROR` | Child born before or in the same year as parent. |

---

## 2. Proposed Changes

### Storage Layer
#### [MODIFY] [src/storage/db.py](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/src/storage/db.py)
* Add `constraint_violations` table to persist detected errors and warnings:
  * `id` (INTEGER PRIMARY KEY)
  * `rule_id` (TEXT)
  * `severity` (TEXT: ERROR, WARNING, INFO)
  * `person_pid` (TEXT, REFERENCES persons)
  * `relative_pid` (TEXT, nullable, for parent/spouse involved)
  * `description` (TEXT)
  * `details_json` (TEXT)
  * `created_at` (TIMESTAMP)
* Add methods:
  * `record_violations_batch(violations: list[dict])`: Bulk store violations for a run.
  * `get_violations(root_pid: str | None = None, severity: str | None = None)`: Fetch violations with person names and lineage details.
  * `clear_violations(person_pid: str | None = None)`: Reset violations before re-audit.

### Constraint Engine Package (`src/constraints/`)
#### [NEW] [src/constraints/__init__.py](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/src/constraints/__init__.py)
* Expose public classes and types.

#### [NEW] [src/constraints/date_parser.py](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/src/constraints/date_parser.py)
* Robust parsing of GEDCOM X `date_formal` (`+YYYY-MM-DD`, `+YYYY-MM`, `+YYYY`, ranges `/`) and fallback `date_original`.
* Returns structured `DateEstimate(year: int, month: int | None, day: int | None, is_approximate: bool)`.
* Computes safe age differences in fractional years and days, accounting for date uncertainty intervals.

#### [NEW] [src/constraints/rules.py](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/src/constraints/rules.py)
* Encapsulates constraint checks into testable rule functions.
* Implements `check_individual_chronology(person, facts) -> list[Violation]`.
* Implements `check_parent_child_biology(parent, child, relationship_type, parent_facts, child_facts) -> list[Violation]`.
* Implements `check_spousal_chronology(husband, wife, marriage_fact, husband_facts, wife_facts) -> list[Violation]`.

#### [NEW] [src/constraints/engine.py](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/src/constraints/engine.py)
* `ConstraintEngine`: Coordinates graph traversal through SQLite:
  * Supports arbitrary pedigree depth (no generation limits; validates all generations in DB).
  * **Arbitrary Ancestor Targeting**: Can validate the entire tree, a specific ancestor and their direct relations, or an ancestral subtree rooted at any given PID (`root_pid` / `target_pid`).
  * **Confidence & Validation Filter**: Optional filter (`min_confidence` or `validated_only`) to execute constraint checks specifically against ancestors that have already been corroborated by the Source Auditor.
  * Optionally saves results to `constraint_violations` table.
  * Produces an aggregate compliance summary.

### CLI Inspection Tool
#### [NEW] [validate_tree.py](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/validate_tree.py)
* Rich CLI utility to run the engine on any SQLite database:
  ```bash
  # Validate entire pedigree across all available generations
  python validate_tree.py --db data/pedigree.sqlite

  # Validate starting from a specific validated ancestor (arbitrary depth/subtree)
  python validate_tree.py --db data/pedigree.sqlite --root <ANCESTOR_PID>

  # Validate only ancestors with confidence score >= 70% (GPS corroborated)
  python validate_tree.py --db data/pedigree.sqlite --min-confidence 70

  # Validate a single specific individual
  python validate_tree.py --db data/pedigree.sqlite --pid <ANCESTOR_PID>
  ```
* Displays:
  1. **Compliance Overview Panel**: Total nodes evaluated, total rules checked, pass rate, violations by severity.
  2. **Violations Breakdown Table**: Ancestor PID, Name, Ahnentafel #, Generation, Rule ID, Severity, Deficit Description.
  3. Optional `--persist` flag to record violations into SQLite.

### Automated Tests
#### [NEW] [tests/test_constraints.py](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/tests/test_constraints.py)
* Unit tests for `date_parser`: ISO 8601 variations, approximate dates, missing days/months.
* Unit tests for each rule:
  * Valid birth/death sequences vs. reversed dates.
  * Normal mother age (e.g. 26) vs. impossible mother age (e.g. 11 or 54).
  * Posthumous father birth within 9 months vs. posthumous birth 2 years later.
  * Sibling and spousal age edge cases.

---

## 3. Verification Plan

### Automated Unit Tests
* Run `pytest` to verify all new rule tests and date parser tests pass alongside existing test suites:
  ```bash
  pytest -v
  ```

### Live Pedigree Validation
* Execute `validate_tree.py` against the real user pedigree in `data/pedigree.sqlite` (32 ancestors through Gen 4):
  ```bash
  python validate_tree.py --db data/pedigree.sqlite --persist
  ```
* Confirm whether any biological or chronological anomalies exist in Douglas Beattie Jr's 4-generation pedigree tree.
