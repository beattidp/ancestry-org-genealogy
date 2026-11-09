# Feature: FamilySearch Targeted Synchronization & GEDCOM X REST Write Endpoints

## Overview & Architecture

The **FamilySearch Targeted Synchronization Engine** enables selective, evidence-backed publication of local discoveries from `data/pedigree.sqlite` directly to FamilySearch Tree profiles. Unlike legacy systems that attempt monolithic GEDCOM 5.5.1 imports, FamilySearch's Platform API uses fine-grained GEDCOM X JSON payloads dispatched against specific REST endpoints.

```
                              ┌──────────────────────────────────┐
                              │       data/pedigree.sqlite       │
                              │  - candidate_discoveries (37)    │
                              │  - facts (Scottish vital events) │
                              └────────────────┬─────────────────┘
                                               │
                                               ▼
                              ┌──────────────────────────────────┐
                              │            SyncEngine            │
                              │     (src/familysearch/sync.py)   │
                              │  - Stages confirmed discoveries  │
                              │  - Standardizes parishes/coords  │
                              │  - Validates GPS changeMessages  │
                              └────────┬─────────────────────────┘
                                       │
                      ┌────────────────┴────────────────┐
                      │                                 │
           (dry_run = True)                  (dry_run = False)
                      ▼                                 ▼
         ┌────────────────────────┐        ┌─────────────────────────┐
         │ Structured Dry-Run     │        │   FamilySearchClient    │
         │ Inspection & Auditing  │        │ (POST /platform/tree/*) │
         └────────────────────────┘        └────────────┬────────────┘
                                                        │
                      ┌─────────────────────────────────┼──────────────────────────────┐
                      ▼                                 ▼                              ▼
          POST /platform/tree/sources       POST /platform/tree/persons/{pid}   POST /platform/tree/relationships
          (SourceDescription creation)      (Facts & geospatial coords)         (ParentChild / Couple)
```

---

## Implemented API Endpoints (`src/familysearch/client.py`)

### 1. Person Facts & Geospatial Place References
- **Method & Endpoint**: `POST /platform/tree/persons/{pid}`
- **GEDCOM X Payload**:
  ```json
  {
    "persons": [
      {
        "id": "KZDJ-4JK",
        "facts": [
          {
            "type": "http://gedcomx.org/Birth",
            "date": {"original": "about 1605"},
            "place": {
              "original": "Liberton, Midlothian, Scotland",
              "description": "#place-ref"
            },
            "attribution": {
              "changeMessage": "Standardized Scottish Civil Parish to Liberton (NRS Parish #693, Midlothian) with coordinates (55.9142, -3.1611) based on National Records of Scotland OPR gazetteer."
            }
          }
        ]
      }
    ],
    "places": [
      {
        "id": "place-ref",
        "names": [{"value": "Liberton, Midlothian, Scotland"}],
        "latitude": 55.9142,
        "longitude": -3.1611
      }
    ]
  }
  ```
- **Validation**: Enforces non-empty `changeMessage`. Handles `HTTP 204 No Content` / `200 OK`.

### 2. Source Description & Citation Attachment
- **Creation Endpoint**: `POST /platform/tree/sources`
  - Captures `Location` header or `X-Entity-ID` from `HTTP 201 Created`.
- **Attachment Endpoint**: `POST /platform/tree/persons/{pid}/sources`
  - Links the newly created source description URL into the person's source list with attribution.
- **Convenience Composite**: `add_person_source_citation(pid, url, title, citation, change_message)`.

### 3. Relationship Mutations
- **Method & Endpoint**: `POST /platform/tree/relationships`
- **Supported Relationship Types**: `http://gedcomx.org/ParentChild`, `http://gedcomx.org/Couple`.

### 4. Duplicate Detection Gate
- **Method & Endpoint**: `GET /platform/tree/matches`
- **Guard**: `create_person(person_payload, change_message, check_duplicates=True)` runs search matches against givenName/surname before initiating person creation, throwing `ValueError` if candidates exist.

---

## Geospatial Scottish Gazetteer Enhancement (`src/geo/scottish_gazetteer.py`)

Added centroid coordinates (`latitude`, `longitude`) to `ScottishParish` and `SCOTTISH_PARISH_DATA` covering all curated civil parishes (e.g. Liberton #693: `55.9142, -3.1611`, St Cuthbert's Edinburgh #685/1: `55.9508, -3.2053`, Alloa #465: `56.1165, -3.7915`, Peebles #768: `55.6533, -3.1906`, Jura & Colonsay #539: `55.9961, -5.9922`).

Method added:
```python
gazetteer.get_parish_coordinates(parish_number: str) -> tuple[float, float] | None
```

---

## Synchronization CLI & Usage

Run dry-run inspection:
```bash
python3 -m src.familysearch.sync
```

Run live synchronization (requires valid FamilySearch session with Tree Write permission):
```bash
python3 -m src.familysearch.sync --live
```

Include pending high-confidence candidate discoveries:
```bash
python3 -m src.familysearch.sync --include-pending --min-confidence 0.70
```

---

## Verification & Test Coverage

- `tests/test_client.py`: 10 unit tests covering fact updates, source creation (201 Location header), relationship creation, duplicate detection, and 403 Tree Write permission errors.
- `tests/test_gazetteer.py`: 4 unit tests covering Scottish civil parish resolution and coordinate lookups.
- `tests/test_sync.py`: 7 unit tests covering candidate discovery staging, Scottish parish fact staging, dry-run execution, validation gates, and live execution mocking with SQLite status updates.
