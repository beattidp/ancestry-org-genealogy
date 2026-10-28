# Worklog: Multi-Source Expansion & Scottish Open Data API Evaluation

* **Date:** 2026-10-27
* **Time:** 19:30 MDT
* **Agent:** Antigravity
* **User:** Douglas Paul Beattie Jr (`KWHS-6NN`)

---

## Summary of Actions

1. **Investigated Historical Source Provenance**:
   - Analyzed existing source ingestion pipeline (`src/ingest/sources.py`).
   - Confirmed that while current queries strictly target the FamilySearch REST API, the citations embedded within FamilySearch reference both internal collections and external repositories (Find A Grave, state archives, military records).
   - Identified the fundamental limitation: FamilySearch queries are reactive to what is already attached; they cannot autonomously discover unindexed or unattached immigrant manifests, newspaper notices, or missing relatives outside FamilySearch.

2. **Evaluated Scottish Open Data Portals**:
   - `https://data.gov.scot/help/technical-support/how-to-access-data-using-the-api`:
     - Inspected CKAN API architecture (`api.data.gov.scot/api/3/action/`).
     - Determined that it publishes macro-level administrative and geospatial data, NOT nominal records (no individual ancestor names or manifests).
     - Identified viable application: Scottish Civil Parish and National Records of Scotland registration district boundary mapping and gazetteer normalization.
   - `https://www.api.gov.uk/scot/statistics-gov-scot/#statistics-gov-scot`:
     - Inspected SPARQL 1.1 Linked Open Data endpoint (`statistics.gov.scot/sparql`).
     - Determined that it publishes aggregate statistical data (population, mortality, economic metrics), NOT person-level records.
     - Identified viable application: Demographic and historical migration trend modeling for Genealogical Proof Standard (GPS) arguments.

3. **Surveyed External Primary Source APIs for Ship Manifests & Unidentified Relatives**:
   - Evaluated Library of Congress Chronicling America API (open REST, OCR historical newspapers with maritime intelligence and port arrival passenger lists).
   - Evaluated The National Archives (UK) Discovery API (Board of Trade BT 27 outward manifests).
   - Evaluated National Archives and Records Administration (NARA) Catalog API (US customs and INS passenger arrivals).
   - Evaluated Internet Archive API (digitized passenger list books by Rupp, Tepper, Filby).
   - Clarified the status of ScotlandsPeople (authoritative for statutory registers, OPRs, and wills, but no public API; closed pay-per-view).

4. **Architectural Proposal**:
   - Designed multi-source harvester architecture in `doc/features/external_sources_and_scottish_api_evaluation.md` for integrating external APIs to target our 16 Gen 4 brick-wall ancestors and 706 unsourced individuals.
