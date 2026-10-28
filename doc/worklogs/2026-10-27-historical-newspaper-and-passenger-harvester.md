# Worklog: Historical Newspaper & Maritime and Digitized Passenger List Harvesters

* **Date:** 2026-10-27
* **Time:** 19:55 MDT
* **Agent:** Antigravity
* **User:** Douglas Paul Beattie Jr (`KWHS-6NN`)

---

## Summary of Actions

1. **Storage Layer Extensions (`src/storage/db.py`)**:
   - Added `candidate_discoveries` table with schema for `person_pid`, `harvester`, `discovery_type`, `title`, `date_str`, `url`, `source_identifier`, `snippet_text`, `confidence_score`, `relevance_reason`, `raw_json`, `status`, `created_at`, `updated_at`.
   - Added indexes on `person_pid`, `harvester`, and `confidence_score`.
   - Implemented `upsert_candidate_discovery(candidate)` with deduplication on URL or source ID.
   - Implemented `get_candidate_discoveries()` with filtering by person PID, harvester, min confidence, and status.
   - Implemented `get_terminal_brick_walls(max_generation)` querying pedigree ancestors with 0 parents in `relationships`.
   - Implemented `get_discovery_summary()` reporting aggregate metrics across harvesters and discovery types.

2. **Harvester Engine Implementation (`src/sources/`)**:
   - `src/sources/base.py`:
     - Created `CandidateDiscovery` dataclass and `BaseHarvester` abstract class.
     - Implemented `extract_year()` and `extract_person_lifespan_years()`.
     - Built multi-factor genealogical `score_candidate()` algorithm evaluating exact/surname name matches, lifespan compatibility, geographic matching against birth/death places and facts, and boosts for maritime arrival and obituary/probate keywords.
   - `src/sources/chronicling_america.py`:
     - Built `ChroniclingAmericaHarvester` connecting to Library of Congress `loc.gov/search/` endpoint.
     - Implemented name searching, in-lifespan date bounding, and maritime keyword queries (`ship`, `arrival`, `passengers`, `steamer`, `bark`).
     - Handled OCR snippets, publication metadata, location tags, and direct view URLs.
     - Tuned HTTP timeout to 35 seconds to accommodate Library of Congress server indexing latency.
   - `src/sources/internet_archive.py`:
     - Built `InternetArchiveHarvester` connecting to Internet Archive Advanced Search API (`archive.org/advancedsearch.php`).
     - Implemented family monograph queries (`"{surname} family"`, `"{surname} genealogy"`), compiled passenger lists, and regional/county histories.
     - Extracted document identifiers, metadata, descriptions, creators, and direct scan URLs (`archive.org/details/{id}`).

3. **CLI Tool (`harvest_records.py`)**:
   - Built command-line interface supporting targeted individual harvesting (`--pid`), batch brick-wall harvesting (`--target brick_walls`), and unsourced ancestor harvesting (`--target unsourced`).
   - Added summary table output, ranking by confidence score, and markdown export (`--export-markdown`).

4. **Testing & Verification**:
   - Created `tests/test_harvesters.py` with 8 comprehensive unit tests covering date extraction, candidate scoring, mocked Library of Congress queries, mocked Internet Archive queries, and database persistence.
   - Ran full test suite: **47/47 passed** across all modules (`pytest -v`).
   - Executed live targeted harvest on terminal immigrant ancestor **Adam Beattie** (`9ZMG-JSD`, b. 1828 Ireland, d. 1908 Sonoma CA): discovered 6 candidate records, led by a 70% match from an 1888 newspaper article.
   - Executed batch harvest on 5 Generation 5 terminal brick walls: discovered 24 candidate records across Adam Beattie, Catherine Kennedy, Charles Robinson, Joseph Thompson, and John Shields.
