# Deep Ingestion (7 Generations) & Recursive Frontier Expansion (10 Generations)

This milestone expands the local genealogical database from the initial 4-generation foundation to **7 generations in a single platform pass** and **recursively expands frontier ancestors to 10 generations** ($2^{10} = 1,024$ potential ancestral slots).

---

## 1. Architectural Strategy & Mathematical Modeling

### Multi-Tier Ingestion Strategy
1. **Tier 1 (Base Platform Ingestion - Generations 0 to 7):**
   - FamilySearch `/platform/tree/ancestry` endpoint directly returns up to 7–8 generations in a single high-efficiency network call (~1.8 seconds).
   - Live probing shows **174 ancestors** are currently populated across Generations 0 through 7 for root `KWHS-6NN`:
     - Gen 0: 1 (100%)
     - Gen 1: 2 (100%)
     - Gen 2: 4 (100%)
     - Gen 3: 8 (100%)
     - Gen 4: 16 (100%)
     - Gen 5: 32 (100%)
     - Gen 6: 53 (82.8%)
     - Gen 7: 58 (45.3%)
2. **Tier 2 (Recursive Frontier Expansion - Generations 8 to 10):**
   - Identify all 58 frontier ancestors at Generation 7.
   - For each frontier ancestor, query their ancestry for 3 additional generations (`generations=3` yields Generations 8, 9, and 10).
   - Stitch subtrees into the global root pedigree using global Ahnentafel coordinate mapping and path extension.

### Global Ahnentafel & Lineage Mapping Formula
When stitching a sub-ancestry tree rooted at frontier ancestor $A_{frontier}$ (at generation $G_{frontier}$):
For any sub-ancestor at relative generation $g$ with relative Ahnentafel number $a$:
* **Global Generation:**
  $$G_{global} = G_{frontier} + g$$
* **Global Ahnentafel Number:**
  $$A_{global} = (A_{frontier} \cdot 2^g) + (a - 2^g)$$
* **Global Lineage Path:**
  $$\text{Path}_{global} = \text{Path}_{frontier} + "." + \text{Path}_{sub}$$

This ensures every person at Generations 8, 9, and 10 receives their exact mathematical position relative to Douglas Beattie Jr (`KWHS-6NN`).

---

## 2. Proposed Changes

### Extractor Layer
#### [MODIFY] [src/pedigree/extractor.py](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/src/pedigree/extractor.py)
* Add `calculate_global_ahnentafel(frontier_asc: int, sub_asc: int) -> tuple[int, int, str]`:
  * Returns `(global_gen, global_asc, global_path)`.
* Handle spouse strings (e.g. `'1-S'`) gracefully in `ascendancyNumber` parsing.

### Ingestion Engine
#### [MODIFY] [src/pedigree/ingest.py](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/src/pedigree/ingest.py)
* Refactor `PedigreeIngester.ingest_ancestry`:
  * Add parameters: `initial_generations: int = 7`, `target_generations: int = 10`.
  * Pass 1: Ingest primary tree up to `min(target_generations, 7)`.
  * Pass 2: If `target_generations > 7`, collect all leaf ancestors at Generation 7.
  * Loop through frontier ancestors with polite rate pacing:
    * Fetch sub-ancestry for `target_generations - 7` generations.
    * Map global Ahnentafel numbers and paths.
    * Derive parent-child linkages between frontier ancestors and their newly discovered parents.
    * Batch upsert persons, facts, pedigree nodes, and relationships.
  * Provide fine-grained progress callback updates to CLI.

### CLI Tools
#### [MODIFY] [ingest.py](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/ingest.py)
* Update arguments:
  * `--generations`: Target generation depth (default: 7, or 10 for full recursive expansion).
  * `--recursive-from`: Generation threshold to start frontier recursion (default: 7).
* Expand generation labels table up to Generation 10:
  * Gen 5: 3rd Great-Grandparents
  * Gen 6: 4th Great-Grandparents
  * Gen 7: 5th Great-Grandparents
  * Gen 8: 6th Great-Grandparents
  * Gen 9: 7th Great-Grandparents
  * Gen 10: 8th Great-Grandparents

#### [MODIFY] [tree_summary.py](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/tree_summary.py)
* Support table rendering and brick-wall summaries for generations 0 through 10.

### Automated Tests
#### [MODIFY] [tests/test_ingestion.py](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/tests/test_ingestion.py)
* Unit tests for `calculate_global_ahnentafel` across generations 7 to 10.
* Unit tests for recursive frontier expansion and parent-child derivation.

---

## 3. Verification Plan

### Automated Tests
* Run `pytest -v` to verify existing tests and new recursive calculation tests pass.

### Live Ingestion Execution
1. Run live ingestion to 7 generations:
   ```bash
   python ingest.py --generations 7 --db data/pedigree.sqlite
   ```
2. Run recursive frontier expansion to 10 generations:
   ```bash
   python ingest.py --generations 10 --db data/pedigree.sqlite
   ```
3. Inspect tree summary:
   ```bash
   python tree_summary.py --db data/pedigree.sqlite
   ```
4. Run constraint validation on expanded 10-generation tree:
   ```bash
   python validate_tree.py --db data/pedigree.sqlite
   ```
