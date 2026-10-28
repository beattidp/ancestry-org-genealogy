# External Sources, Ship Manifests & Scottish Open Data API Evaluation

**Document Version:** 1.0  
**Date:** 2026-10-27  
**Author:** Antigravity  
**Target Pedigree:** Root `ABCD-123` (Sample User) — 2,603 Ancestors across 15 Generations

---

## 1. Executive Summary

This document evaluates the existing source ingestion architecture, addresses whether historical source citations are exclusive to FamilySearch, investigates external primary sources and APIs for ship manifests/passenger arrivals to identify unknown relatives, and provides an in-depth technical analysis of two Scottish open-government data APIs:
1. `https://data.gov.scot/help/technical-support/how-to-access-data-using-the-api` (`data.gov.scot` CKAN Open Data API)
2. `https://www.api.gov.uk/scot/statistics-gov-scot/#statistics-gov-scot` (`statistics.gov.scot` SPARQL Linked Data API)

---

## 2. Analysis: Current Source Ingestion Architecture

### 2.1 FamilySearch API as the Transport Layer
Currently, 100% of our raw source ingestion (`src/ingest/sources.py`) uses the FamilySearch REST API:
- Endpoint: `/platform/tree/persons/{pid}/sources`
- Endpoint: `/platform/sources/descriptions/{sdid}`

### 2.2 Internal vs. External Citations
While the transport layer is FamilySearch, the **citations themselves** represent a mix:
- **FamilySearch Indexed Records:** Censuses (US, UK, Canadian), vital records (state birth/death indexes), military draft cards, Old Parish Registers (Scotland, England).
- **External Citations attached by Researchers:** Citations pointing to Find A Grave, state historical societies, private family bibles, and references to ScotlandsPeople or National Archives documents.

### 2.3 The Critical Bottleneck
Our current system is **reactive**: it only ingests records that have *already been found and attached* to a profile on FamilySearch. If an immigrant ancestor arrived on a ship, settled under an alternative surname spelling, or was recorded in an unindexed parish register that has not yet been attached to the FamilySearch Family Tree:
- **Our database has zero awareness of it.**
- **We cannot autonomously discover missing relatives or break through the 16 Gen 4 brick-wall ancestors without querying external record repositories.**

---

## 3. Evaluation: Scottish Open Data APIs

The user proposed investigating two official Scottish public data endpoints. Below is an exhaustive technical and genealogical assessment:

| Dimension | `data.gov.scot` | `statistics.gov.scot` |
| :--- | :--- | :--- |
| **Portal Name** | Scottish Government Open Data Repository | Statistics.gov.scot (UK API Catalogue) |
| **Underlying Engine** | **CKAN v3** (Comprehensive Knowledge Archive Network) | **SPARQL 1.1** Triple Store & Linked Data REST API |
| **Primary Base Endpoint** | `https://api.data.gov.scot/api/3/action/` | `https://statistics.gov.scot/sparql` |
| **Authentication** | Open access (Open Government Licence - OGL); no key required for read queries | Open access (OGL); no key required |
| **Data Publishing Bodies** | Scottish Government, National Records of Scotland (NRS), NHS Scotland, SEPA, Local Authorities | Scottish Government, NRS, Scottish Public Bodies |
| **Data Scope** | Macro-datasets: Geospatial boundaries, transport networks, health boards, public spending, SIMD indices | Statistical datasets: Population demographics, historical census aggregates, health/economic indicators |
| **Nominal Records?** | **No** (No individual names, births, deaths, marriages, or passenger manifests) | **No** (Aggregated statistical data only) |

### 3.1 Can they be used to find named relatives or ship manifests?
**No.** Under UK and Scottish Data Protection legislation (GDPR and Data Protection Act 2018), open statistical platforms publish strictly aggregate and anonymized data. They do not hold person-level genealogical records, nominal passenger manifests, or parish registers.

### 3.2 How CAN they be utilized in our genealogical pipeline?
While they cannot provide person-level records, they offer high-value **contextual, geographic, and gazetteer infrastructure**:
1. **Scottish Civil Parish Gazetteer Resolution:**
   - `data.gov.scot` publishes National Records of Scotland (NRS) civil parish boundary shapefiles, historical parish codes, and registration district identifiers.
   - We can build an automated resolver that validates Scottish birth, marriage, and death places across our 2,603 ancestors (e.g., verifying archaic parish spellings in Lanarkshire, Ayrshire, Dumfriesshire, or Midlothian against official Scottish geographic entities).
2. **Historical Demographics & Migration Patterns:**
   - `statistics.gov.scot` provides SPARQL queries for historical population movements and demographic changes across Scottish regions, providing historical context for Genealogical Proof Standard (GPS) proof arguments.

---

## 4. Authoritative Scottish Primary Record Repositories

Where do true Scottish genealogical primary records (births, marriages, deaths, wills, ship departures) reside?

### 4.1 ScotlandsPeople (`scotlandspeople.gov.uk`)
- **Operator:** National Records of Scotland (NRS) in partnership with the Court of the Lord Lyon.
- **Holdings:**
  - **Statutory Registers:** Official civil registration of Births, Marriages, and Deaths (from 1 Jan 1855 to present).
  - **Old Parish Registers (OPRs):** Church of Scotland parish registers of baptisms, marriages, and burials (1553 to 1854).
  - **Scottish Census Returns:** Every decennial census from 1841 through 1921.
  - **Scottish Wills and Testaments:** Commissariot and Sheriff Court wills and inventories (1513 to 1925).
  - **Kirk Session Records & High Court Trials.**
- **API Availability:** **No public API.** ScotlandsPeople operates on a commercial pay-per-view/search credit model with active anti-bot protections. Automated scraping violates Terms of Service. Searches must be performed interactively or referenced via transcript citations.

### 4.2 Scottish Archive Network (SCAN - `scan.org.uk`)
- Electronic catalogue indexing holdings across 50+ local and national archives in Scotland.

### 4.3 Highland and Island Emigration Society (HIES) & NRS Passenger Records
- Emigration records, clearances passenger lists (e.g. vessels departing Glasgow, Greenock, and Leith for North America and Australia), preserved under NRS record classes (e.g., HD4 series).

---

## 5. External Primary Sources & APIs for Passenger Manifests & Discovery

To find unidentified ancestors, immigrant origins, and missing passenger manifests programmatically, the following external resources feature open or accessible APIs:

### 5.1 Library of Congress — Chronicling America API
- **Endpoint:** `https://chroniclingamerica.loc.gov/about/api/`
- **Format:** REST / JSON + OCR text + PDF / JP2 images.
- **Access:** Completely free, open, no API key required.
- **Genealogical Value:**
  - Historical American newspapers spanning 1777 to 1963.
  - In the 18th and 19th centuries, **marine shipping columns** routinely published vessel arrivals, ports of origin, ship captains, and notable passenger lists (e.g. arrivals in New York, Philadelphia, Baltimore, Boston, New Orleans).
  - Critical for finding obituaries, probate and estate notices, legal notices, and family migration reports.

### 5.2 The National Archives (UK) — Discovery API
- **Endpoint:** `https://discovery.nationalarchives.gov.uk/API/`
- **Format:** REST API.
- **Access:** Free API key upon developer registration.
- **Genealogical Value:**
  - Indexes 32+ million record descriptions held at Kew, London.
  - Includes **Board of Trade Outward Passenger Lists (BT 27)** (1890–1960) and Inward Passenger Lists (BT 26).
  - Naturalization certificates (Home Office HO 1 / HO 405) and Alien arrival certificates (HO 2).

### 5.3 National Archives and Records Administration (USA) — NARA Catalog API
- **Endpoint:** `https://catalog.archives.gov/api/v2/`
- **Format:** REST API.
- **Access:** Free API key.
- **Genealogical Value:**
  - Comprehensive catalog of US federal records, including Record Group 85 (Immigration and Naturalization Service - INS passenger arrival manifests for Castle Garden 1820–1892, Ellis Island 1892–1957, Boston, Philadelphia, Baltimore, New Orleans, San Francisco).

### 5.4 Internet Archive API
- **Endpoint:** `https://archive.org/advancedsearch.php`
- **Format:** JSON / XML search + full text text-search.
- **Access:** Free and open.
- **Genealogical Value:**
  - Digitized public-domain genealogical compendiums, county histories, published parish registers, and standard immigration reference works:
    - I. D. Rupp: *A Collection of Upwards of Thirty Thousand Names of German, Swiss, Dutch, French and Other Immigrants in Pennsylvania* (1727–1776).
    - Michael Tepper: *Passengers to America: A Consolidation of Ship Passenger Lists*.
    - P. W. Filby: *Passenger and Immigration Lists Index*.
    - Historical clan monographs, Scotch-Irish pioneer settlement histories, and colonial militia rolls.

---

## 6. Proposed Multi-Source Ingestion Architecture

```
                                  +------------------------------------+
                                  |    Multi-Source Harvester Orchestrator    |
                                  +------------------------------------+
                                                    |
           +--------------------+-------------------+--------------------+--------------------+
           |                    |                   |                    |                    |
+--------------------+ +--------------------+ +--------------------+ +--------------------+ +--------------------+
|  FamilySearch API  | | Chronicling America| |  NARA / TNA UK APIs| |  Internet Archive  | | data.gov.scot CKAN |
| (Existing Pedigree | |   (LOC Historical  | |(Ship Manifests and | |  (Published Lists  | | (Scottish Parish & |
|  & Source Trees)   | |     Newspapers)    | | Naturalizations)   | |  & County Records) | | Gazetteer Mapping) |
+--------------------+ +--------------------+ +--------------------+ +--------------------+ +--------------------+
           |                    |                   |                    |                    |
           v                    v                   v                    v                    v
+-----------------------------------------------------------------------------------------------------------------+
|                                 Candidate Entity & Source Extraction Layer                                      |
|            (Normalizes names, dates, places, ports of entry, ship names into Candidate Fact Records)             |
+-----------------------------------------------------------------------------------------------------------------+
                                                    |
                                                    v
+-----------------------------------------------------------------------------------------------------------------+
|                                  Deterministic Disambiguation & Linkage Engine                                  |
|     (Matches candidate sources against 16 Gen 4 brick walls & 706 unsourced ancestors using spatial/temporal bounds)|
+-----------------------------------------------------------------------------------------------------------------+
                                                    |
                                                    v
+-----------------------------------------------------------------------------------------------------------------+
|                                      `pedigree.sqlite` Local Knowledge Graph                                    |
+-----------------------------------------------------------------------------------------------------------------+
```

---

## 7. Next Steps & Recommendations

1. **Phase 1: Scottish Place & Parish Gazetteer Engine**
   - Implement `src/geo/scottish_gazetteer.py` using `data.gov.scot` to normalize Scottish birth/marriage/death locations in our pedigree tree, linking them to historical registration districts.
2. **Phase 2: Historical Newspaper Harvester (Chronicling America)**
   - Implement `src/sources/chronicling_america.py` to query for ship arrival notices and obituaries matching our 16 Gen 4 brick-wall ancestors.
3. **Phase 3: Digitized Monograph & Passenger List Search (Internet Archive)**
   - Implement `src/sources/internet_archive.py` to query out-of-copyright passenger manifests and published genealogies.
