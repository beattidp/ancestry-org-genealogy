# Walkthrough — FamilySearch Credentials & API Client Setup

We have set up the local credential architecture and built the core FamilySearch Platform API client, fully integrated with your `pyenv` virtual environment (`ancestry-genealogy`).

---

## 1. What Was Created & Configured

### Security & Environment
* **[.gitignore](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/.gitignore)**: Configured to strictly ignore `.env`, `credentials.json`, `scratch/`, `*.sqlite`, and test/build artifacts.
* **[.env.example](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/.env.example)**: Reference template with step-by-step instructions on extracting the active `fssessionid` cookie from `familysearch.org`.
* **[requirements.txt](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/requirements.txt)**: Maintained with `>=` version constraints (`httpx>=0.28.0`, `pydantic>=2.10.0`, `pydantic-settings>=2.7.0`, `python-dotenv>=1.0.0`, `rich>=13.9.0`, `pytest>=8.0.0`) and installed into the active `pyenv` environment.

### Core Modules
* **[src/config.py](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/src/config.py)**: Pydantic settings module that loads configuration from `.env` and selects the appropriate base URL (`https://api.familysearch.org`).
* **[src/familysearch/auth.py](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/src/familysearch/auth.py)**: `SessionManager` module providing Bearer token formatting (`Authorization: Bearer <fssessionid>`), session validation against `/platform/users/current`, and actionable error diagnostics for expired tokens.
* **[src/familysearch/client.py](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/src/familysearch/client.py)**: `FamilySearchClient` providing synchronous GEDCOM X endpoints:
  * `get_current_user()`
  * `get_person(pid)`
  * `get_ancestry(pid, generations)`
  * `get_person_parents(pid)`, `get_person_spouses(pid)`, `get_person_children(pid)`
  * `get_person_sources(pid)`
  * `get_person_matches(pid, collection)`
  * `get_person_changes(pid)`
  * `search_records(query_params)`
  * `search_tree(query_params)`

### Diagnostic Probe
* **[probe.py](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/probe.py)**: A rich command-line tool that tests credentials, probes the identity endpoint, and displays the authenticated user profile and root person in the tree.

---

## 2. Verification Results

### Automated Unit Tests
Ran the full test suite with `python -m pytest -v`:
```
============================= test session starts ==============================
platform linux -- Python 3.13.1, pytest-9.1.1, pluggy-1.7.0
rootdir: /home/beattidp/Documents/antigravity/ancestry-genealogy

tests/test_auth.py::test_auth_headers_empty_token PASSED                 [ 14%]
tests/test_auth.py::test_auth_headers_with_token PASSED                  [ 28%]
tests/test_auth.py::test_validate_session_missing_token PASSED           [ 42%]
tests/test_client.py::test_client_missing_headers PASSED                 [ 57%]
tests/test_client.py::test_client_mock_dispatch PASSED                   [ 71%]
tests/test_client.py::test_client_mock_404_not_found PASSED              [ 85%]
tests/test_client.py::test_client_mock_401_auth_error PASSED             [100%]

============================== 7 passed in 1.18s ===============================
```

### Live Connection & Profile Probe
Executed `python probe.py` against FamilySearch production:

```text
FamilySearch Research Engine — Credential & API Probe

Probing FamilySearch API identity endpoint...
       FamilySearch Authenticated Session Details        
┏━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Property               ┃ Value                        ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ API Environment        │ PRODUCTION                   │
│ Base URL               │ https://api.familysearch.org │
│ User ID                │ cis.user.MM9W-QYW8           │
│ Display Name           │ Douglas Beattie Jr           │
│ Contact Name           │ Douglas Beattie Jr           │
│ Tree Person ID (Root)  │ KWHS-6NN                     │
└────────────────────────┴──────────────────────────────┘
╭─────────────────────────── Tree Profile Verified ────────────────────────────╮
│ Root Person in Tree: Douglas Paul Beattie Jr (Male) - 1966-Living            │
│ PID: KWHS-6NN                                                                │
│ ✓ Tree read access verified successfully.                                    │
╰──────────────────────────────────────────────────────────────────────────────╯
╭──────────────────────────────────────────────────────────────────────────────╮
│ ✓ FamilySearch API connection active and verified!                           │
│ You are ready to begin programmatic research and pedigree analysis.          │
╰──────────────────────────────────────────────────────────────────────────────╯
```

---

## 3. Next Steps

With live read access verified against your root person profile (`KWHS-6NN`), we can proceed to build the next research components:
1. **Pedigree Tree Ingestion & Local Cache:** Traverse $N$ generations of ancestors starting from `KWHS-6NN` and cache nodes in a local SQLite database.
2. **Evidence & Source Auditor:** Ingest all attached sources for each ancestor and classify them (Primary Vital vs Census vs Secondary vs Unsourced assertions).
3. **Automated GPS & Conflict Resolver:** Cross-reference censuses (1850–1950) with household cluster triangulation to verify each ancestral link.
