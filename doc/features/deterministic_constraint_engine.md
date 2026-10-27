# Feature: Deterministic Biological & Chronological Constraint Engine

## 1. Overview
High-confidence genealogy requires strict verification against biological laws and chronological physics. The **Deterministic Biological & Chronological Constraint Engine** validates all individuals, generational parent-child links, and marriages against established biological thresholds and event sequencing rules.

## 2. Architecture & Components

```
                   ┌─────────────────────────────────────────┐
                   │           data/pedigree.sqlite          │
                   │ (persons, facts, relationships, scores) │
                   └────────────────────┬────────────────────┘
                                        │
                                        ▼
                   ┌─────────────────────────────────────────┐
                   │    src/constraints/date_parser.py       │
                   │  (GEDCOM X formal, ranges, text dates)  │
                   └────────────────────┬────────────────────┘
                                        │
                                        ▼
                   ┌─────────────────────────────────────────┐
                   │       src/constraints/rules.py          │
                   │  - Individual Chronology (Lifespan/Seq) │
                   │  - Parent-Child Biology (Maternal/Pat)  │
                   │  - Spousal Chronology (Age/Posthumous)  │
                   └────────────────────┬────────────────────┘
                                        │
                                        ▼
                   ┌─────────────────────────────────────────┐
                   │      src/constraints/engine.py          │
                   │  - ConstraintEngine (Subtree/Arbitrary) │
                   │  - ValidationReport                     │
                   └────────────────────┬────────────────────┘
                                        │
                       ┌────────────────┴────────────────┐
                       ▼                                 ▼
         ┌───────────────────────────┐     ┌───────────────────────────┐
         │     validate_tree.py      │     │   constraint_violations   │
         │    (Rich Terminal UI)     │     │     (SQLite Table)        │
         └───────────────────────────┘     └───────────────────────────┘
```

### Components
1. **[src/constraints/date_parser.py](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/src/constraints/date_parser.py)**:
   - Supports GEDCOM X formal dates (`+YYYY-MM-DD`, `+YYYY-MM`, `+YYYY`, `+YYYY/+YYYY`).
   - Supports historical text formats (`22 November 1919`, `19660421`, `Jul 1937`, `about 1850`).
   - Produces `DateEstimate` containing exact dates, year bounds, and approximation flags.
   - Computes age in fractional years and exact calendar day differences with uncertainty awareness.
2. **[src/constraints/rules.py](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/src/constraints/rules.py)**:
   - Evaluates violations and assigns severity: `ERROR`, `WARNING`, or `INFO`.
   - **`CHRONO-EVENT-ORDER`**: Birth $\le$ Christening $\le$ Marriage $\le$ Death $\le$ Burial.
   - **`CHRONO-LIFESPAN`**: Lifespan $\ge 0$ and $\le 120$ years (Centenarians $> 105$ flagged for verification).
   - **`CHRONO-MARR-AGE`**: Age at marriage $\ge 12$ years.
   - **`REL-INVERSION`**: Child born before or in the same year as parent.
   - **`BIO-MOTH-AGE`**: Mother age at birth $13 \le age \le 50$ (Error if $< 13$ or $> 50$; Warning if $13 \le age < 15$ or $46 \le age \le 50$).
   - **`BIO-MOTH-POSTHUMOUS`**: Child born after mother's death.
   - **`BIO-FATH-AGE`**: Father age at child's conception/birth $14 \le age \le 85$ (Error if $< 14$ or $> 85$; Warning if $14 \le age < 16$ or $70 \le age \le 85$).
   - **`BIO-FATH-POSTHUMOUS`**: Child born $> 280$ days after father's death (Error if $> 280$ days; Info if $0 < days \le 280$).
3. **[src/constraints/engine.py](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/src/constraints/engine.py)**:
   - `ConstraintEngine`: Coordinates graph loading, rule execution, metric aggregation, and violation persistence.
   - Supports arbitrary generational depth.
   - Supports scoping by ancestor subtree (`root_pid`), single individual (`person_pid`), or confidence threshold (`min_confidence`).
4. **[validate_tree.py](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/validate_tree.py)**:
   - CLI tool rendering Rich summary panels and detailed violation tables.
   - Supports `--db`, `--root`, `--pid`, `--min-confidence`, and `--persist`.

## 3. SQLite Storage Schema
Stored in `constraint_violations`:
* `id INTEGER PRIMARY KEY AUTOINCREMENT`
* `rule_id TEXT NOT NULL`
* `severity TEXT NOT NULL` (`ERROR`, `WARNING`, `INFO`)
* `person_pid TEXT NOT NULL`
* `relative_pid TEXT`
* `description TEXT NOT NULL`
* `details_json TEXT`
* `created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP`

## 4. CLI Usage Examples

```bash
# 1. Validate full pedigree tree
python validate_tree.py --db data/pedigree.sqlite

# 2. Validate tree and persist violations to SQLite
python validate_tree.py --db data/pedigree.sqlite --persist

# 3. Validate only high-confidence ancestors (GPS score >= 70%)
python validate_tree.py --db data/pedigree.sqlite --min-confidence 70

# 4. Validate a specific validated ancestor
python validate_tree.py --db data/pedigree.sqlite --pid KJJ4-83J

# 5. Validate an ancestral branch starting from an ancestor PID
python validate_tree.py --db data/pedigree.sqlite --root KJJ4-83J
```
