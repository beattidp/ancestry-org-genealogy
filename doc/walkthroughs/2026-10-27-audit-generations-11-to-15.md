# Walkthrough: Source Auditing of Generations 11 to 15

## Overview
In this iteration, we expanded source and citation auditing across the 2,061 deep ancestors in Generations 11 to 15 (1400s–1600s). We upgraded the evidence classifier to support early modern and medieval British, Scottish, and French record types, added bidirectional generational range scoping (`--min-gen` / `--max-gen`), and completed a full audit of all 2,603 ancestors in the pedigree tree.

---

## Changes Implemented

### 1. Historical Source Classification
- **`src/audit/classifier.py`**:
  - **Tier 1 (Primary Records)**: Added recognition for Parish Registers (`parish_register`), Church Records, Kirk Session minutes, Marriage Banns/Allegations, Inquisitions Post Mortem (`probate`), Prerogative Court wills, and Court of Rolls/Feet of Fines.
  - **Tier 2 (Secondary/Scholarly)**: Added recognition for Heralds' Visitations (`heraldic_visitation`), Peerages & Baronetages (`peerage`), and university alumni registers (Oxford and Cambridge).
- **`src/audit/auditor.py`**:
  - Aligned verification criteria so that `parish_register` satisfies Birth/Baptism, `probate` (IPMs and wills) satisfies Death, and `heraldic_visitation`, `peerage`, `probate`, and `parish_register` corroborate Parentage links.

### 2. Generational Range Scoping & High-Efficiency Caching
- **`src/storage/db.py`**:
  - Added `get_audited_person_pids()` to retrieve previously audited person PIDs, preventing redundant network queries for ancestors with zero attached sources.
  - Extended `get_audit_scores` and `get_audit_summary` to accept `min_generation` and `max_generation`.
- **`src/audit/auditor.py`**:
  - Added `min_generation` scoping to `audit_pedigree`.
  - Integrated `already_audited` check to bypass API requests when `only_missing=True` and `refresh=False`.
- **`audit_sources.py`**:
  - Added `--min-gen` flag.
  - Forwarded generational ranges to the auditing and summary reporting components.

---

## Verification & Results

### 1. Automated Tests
```bash
pytest
```
- **39/39 tests passing** in 2.51s, including new unit tests for deep historical record classification and `min_generation` scoping.

### 2. Live Audit: Generations 11 to 15
```bash
python audit_sources.py --db data/pedigree.sqlite --fetch --min-gen 11 --max-gen 15
```
- **Audited**: 2,061 deep ancestors
- **Confidence Distribution**:
  - **HIGH (80–100%)**: 462 ancestors (22.4%)
  - **MEDIUM (50–79%)**: 347 ancestors (16.8%)
  - **LOW (1–49%)**: 626 ancestors (30.4%)
  - **UNSOURCED (0%)**: 626 ancestors (30.4%)
  - **Average Confidence**: **40.5%**

### 3. Full-Tree Benchmark (Generations 0 to 15)
```bash
python audit_sources.py --db data/pedigree.sqlite
```
- **Total Audited**: 2,603 ancestors across all 15 generations
- **Overall Confidence Distribution**:
  - **HIGH (80–100%)**: 699 ancestors (26.9%)
  - **MEDIUM (50–79%)**: 427 ancestors (16.4%)
  - **LOW (1–49%)**: 771 ancestors (29.6%)
  - **UNSOURCED (0%)**: 706 ancestors (27.1%)
  - **Overall Average Pedigree Confidence Score**: **44.5%**

#### Generational Evidence Verification Matrix

| Gen | Relationship | Ancestor Count | Birth Verified | Death Verified | Parentage Verified | Avg Confidence |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: |
| 0 | Self | 1 | 0% | 0% | 0% | 0.0% |
| 1 | Parents | 3 | 33% | 0% | 33% | 30.7% |
| 2 | Grandparents | 4 | 100% | 100% | 100% | **100.0%** |
| 3 | 1st Great-Grandparents | 8 | 100% | 100% | 100% | **100.0%** |
| 4 | 2nd Great-Grandparents | 16 | 100% | 94% | 100% | **98.9%** |
| 5 | 3rd Great-Grandparents | 32 | 88% | 78% | 78% | **84.8%** |
| 6 | 4th Great-Grandparents | 51 | 69% | 45% | 37% | **57.2%** |
| 7 | 5th Great-Grandparents | 56 | 59% | 36% | 41% | **57.2%** |
| 8 | 6th Great-Grandparents | 85 | 61% | 42% | 48% | **59.9%** |
| 9 | 7th Great-Grandparents | 123 | 54% | 28% | 44% | **52.7%** |
| 10 | 8th Great-Grandparents | 163 | 55% | 34% | 43% | **52.1%** |
| 11 | 9th Great-Grandparents | 214 | 69% | 48% | 53% | **64.2%** |
| 12 | 10th Great-Grandparents | 306 | 64% | 44% | 47% | **59.5%** |
| 13 | 11th Great-Grandparents | 399 | 51% | 35% | 36% | **48.6%** |
| 14 | 12th Great-Grandparents | 491 | 40% | 25% | 29% | **38.7%** |
| 15 | 13th Great-Grandparents | 651 | 30% | 22% | 1% | **20.2%** |
