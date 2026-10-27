# Feature: Deep Ingestion & Recursive Frontier Expansion

## 1. Overview
The **Deep Ingestion & Recursive Frontier Expansion** engine breaks through single-query platform depth limits. It combines:
1. **Tier 1 (Base Platform Ingestion):** High-throughput single-call ingestion up to 7 generations from FamilySearch.
2. **Tier 2 (Recursive Frontier Expansion):** Automated traversal and expansion of frontier leaf ancestors up to 10 generations ($2^{10} = 1,024$ potential ancestral slots), stitching subtrees into the global root pedigree via mathematical coordinate mapping.

---

## 2. Mathematical Modeling & Global Ahnentafel Mapping

In standard Ahnentafel (ascendancy) numbering, each person $A$ has:
* Father: $2A$
* Mother: $2A + 1$
* Generation: $G = \lfloor \log_2(A) \rfloor$

When querying a sub-ancestry tree rooted at a frontier leaf ancestor $A_{frontier}$ (at generation $G_{frontier}$):
The relative root in the sub-tree has $a_{sub} = 1$. For any relative ancestor at relative generation $g$ with relative Ahnentafel number $a_{sub}$:
* **Global Generation:**
  $$G_{global} = G_{frontier} + g$$
* **Global Ahnentafel Number:**
  $$A_{global} = (A_{frontier} \cdot 2^g) + (a_{sub} - 2^g) = (A_{frontier} \ll g) + (a_{sub} - (1 \ll g))$$
* **Global Lineage Path:**
  $$\text{Path}_{global} = \text{Path}_{frontier} + "." + \text{Path}_{sub}$$

This mathematical derivation allows arbitrary depth stitching without loss of lineage context or relational continuity.

---

## 3. Architecture & Components

```
                   ┌─────────────────────────────────────────┐
                   │           ingest.py (CLI)               │
                   │ (--generations 7 --recursive-to 10)     │
                   └────────────────────┬────────────────────┘
                                        │
                                        ▼
                   ┌─────────────────────────────────────────┐
                   │    src/pedigree/ingest.py               │
                   │ (PedigreeIngester orchestrator)         │
                   └───────────┬───────────────────┬─────────┘
                               │                   │
                     Pass 1    ▼          Pass 2   ▼
                 Base Ingest (Gen 0-7)    Frontier Ingest (Gen 8-10)
                 Single call              58 leaf queries (Gen 7)
                               │                   │
                               └─────────┬─────────┘
                                         ▼
                   ┌─────────────────────────────────────────┐
                   │    src/pedigree/extractor.py            │
                   │  - calculate_global_ahnentafel          │
                   │  - derive_pedigree_parent_child_rels    │
                   └─────────────────────┬───────────────────┘
                                         ▼
                   ┌─────────────────────────────────────────┐
                   │         data/pedigree.sqlite            │
                   │ (545 persons, 1065 rels, 2845 facts)    │
                   └─────────────────────────────────────────┘
```

### Components
1. **[src/pedigree/extractor.py](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/src/pedigree/extractor.py)**:
   - `calculate_global_ahnentafel`: Translates relative subtree coordinates into unified global root coordinates.
   - Robust parsing of spouse designations (e.g. `'1-S'`).
2. **[src/pedigree/ingest.py](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/src/pedigree/ingest.py)**:
   - `PedigreeIngester.ingest_ancestry`: Orchestrates multi-tier ingestion with atomic batching, foreign key integrity, and rate pacing (0.05s).
3. **[ingest.py](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/ingest.py)**:
   - Command-line interface with dual-progress tracking and generation coverage tables through Gen 10+.
4. **[tree_summary.py](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/tree_summary.py)**:
   - Generational reporting and gap analysis for deep trees.

---

## 4. CLI Usage Examples

```bash
# Ingest 7 base generations and recursively expand frontier to 10 generations
python ingest.py --generations 7 --recursive-to 10 --db data/pedigree.sqlite

# Inspect 10-generation tree coverage and earliest documented ancestors
python tree_summary.py --db data/pedigree.sqlite

# Run deterministic constraint validation across all 10 generations
python validate_tree.py --db data/pedigree.sqlite
```
