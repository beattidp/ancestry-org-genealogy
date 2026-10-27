# Feature Documentation: Genealogical Source & Citation Auditor

**Feature Name:** Genealogical Source & Citation Auditor  
**Status:** Implemented & Verified  
**Date:** 2026-10-27  
**Module(s):** `src/audit/classifier.py`, `src/audit/auditor.py`, `src/storage/db.py`, `audit_sources.py`

---

## 1. Architectural Overview

The **Source & Citation Auditor** implements the principles of the **Genealogical Proof Standard (GPS)** to programmatically assess the evidence quality, fact verification, and confidence ratings of every ancestor in the local database.

```
+-------------------------------------------------------------------------------+
|                       FamilySearch Platform API                               |
|                GET /platform/tree/persons/{pid}/sources                       |
+--------------------------------------|----------------------------------------+
                                       | Raw Source Descriptions & Citations
                                       v
+-------------------------------------------------------------------------------+
|                         src/audit/classifier.py                               |
|                                                                               |
|  Classifies evidence into GPS Quality Tiers:                                  |
|  - Tier 1 (Primary Contemporary): Censuses, Birth/Death Certificates,        |
|                                   WW1/WW2 Military, Social Security NUMIDENT  |
|  - Tier 2 (Secondary / Derivative): Obituaries, County Histories, Memorials   |
|  - Tier 3 (Unverified / Hypotheses): Member Trees, Legacy NFS, User Notes     |
+--------------------------------------|----------------------------------------+
                                       | Classified Evidence
                                       v
+-------------------------------------------------------------------------------+
|                          src/audit/auditor.py                                 |
|                         (SourceAuditor Engine)                                |
|                                                                               |
|  - Birth Verification: Checks for Tier 1 vital_birth, census, or SSN          |
|  - Death Verification: Checks for Tier 1 vital_death, cemetery, or SSN        |
|  - Parentage Verification: Checks contemporary records proving child-parent   |
|  - Weighted Confidence Score (0-100%):                                        |
|      * 40% Parentage proof                                                    |
|      * 30% Birth primary proof                                                |
|      * 20% Death primary proof                                                |
|      * 10% Corroborating primary record depth                                 |
|      * Tier 3 pure user trees capped at <= 25%                                |
+--------------------------------------|----------------------------------------+
                                       | Evidentiary Assessments
                                       v
+-------------------------------------------------------------------------------+
|                            src/storage/db.py                                  |
|                       data/pedigree.sqlite (WAL Mode)                         |
|                                                                               |
|  - sources (id, title, about_url, citation_text, tier, record_type)           |
|  - person_sources (id, person_pid, source_id, tags, contributor)              |
|  - person_audit_scores (person_pid, confidence_score, confidence_level,       |
|                         birth_verified, death_verified, parentage_verified)   |
+-------------------------------------------------------------------------------+
```

---

## 2. Evidence Tiering Rules

| Tier | Quality Level | Included Record Types | Genealogical Weight |
| :--- | :--- | :--- | :--- |
| **Tier 1** | **Primary Contemporary Documentary** | Federal/State Censuses (1850–1950), Birth Certificates/Indexes, Christening/Baptism Parish Books, Marriage Returns/Licenses, Death Certificates, Cemetery Interments/Find A Grave, WW1/WW2 Draft Registrations, Social Security Applications/NUMIDENT, Wills & Probate Packets. | **High (Primary Evidence)**. Sufficient to verify core life events and parentage links. |
| **Tier 2** | **Secondary / Derivative** | Newspaper Obituaries, Published County Histories, Compiled Genealogies, Passenger Lists / Manifests, City Directories, Memorials without primary headstone images. | **Medium (Corroborating)**. Useful for hints and family context, but subject to informant error. |
| **Tier 3** | **Unverified Hypotheses** | Pedigree Resource Files, Ancestry Member Trees, FamilySearch Family Tree user submissions, Legacy NFS Sources, unsourced personal notes. | **Zero Proof Value**. Treated strictly as unproven leads; capped at $\le 25\%$ confidence. |

---

## 3. CLI Usage & Reporting

### Running Live Audit with API Synchronization
```bash
python audit_sources.py --db data/pedigree.sqlite --fetch
```

### Running Offline Inspection
```bash
python audit_sources.py --db data/pedigree.sqlite
```

### Output Tables
1. **Confidence Distribution**: High ($\ge 80\%$), Medium ($50-79\%$), Low ($1-49\%$), and Unsourced ($0\%$).
2. **Generational Coverage Matrix**: % Birth Verified, % Death Verified, % Parentage Verified across each generation.
3. **Priority Evidentiary Deficits**: Actionable backlog listing ancestors missing primary sources to direct future archive searches.
