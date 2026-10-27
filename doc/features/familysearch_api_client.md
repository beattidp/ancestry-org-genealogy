# Feature Documentation: FamilySearch Platform API Client & Authentication

**Feature Name:** FamilySearch Platform API Client & Credential Architecture  
**Status:** Implemented & Verified  
**Date:** 2026-10-27  
**Module(s):** `src/config.py`, `src/familysearch/auth.py`, `src/familysearch/client.py`, `probe.py`

---

## 1. Architectural Overview

This feature provides the foundational connectivity, authentication, and GEDCOM X REST API client layer connecting the local Python application to the FamilySearch Platform API (`https://api.familysearch.org`).

```
+-------------------------------------------------------------+
|                        Local Client                         |
|                                                             |
|  .env (local only)  -->  src/config.py (Pydantic Settings)   |
|                                |                            |
|                                v                            |
|                  src/familysearch/auth.py                   |
|                   (SessionManager & Headers)                |
|                                |                            |
|                                v                            |
|                  src/familysearch/client.py                 |
|                   (FamilySearchClient REST)                 |
+-------------------------------|-----------------------------+
                                |  HTTPS Bearer Token
                                v
          +-----------------------------------------+
          |      FamilySearch Platform API          |
          |                                         |
          |  /platform/users/current                |
          |  /platform/tree/persons/{pid}           |
          |  /platform/tree/ancestry                |
          |  /platform/tree/persons/{pid}/sources   |
          |  /platform/tree/persons/{pid}/matches   |
          |  /platform/search/records               |
          +-----------------------------------------+
```

### Components
1. **`src/config.py`**:
   - Uses `pydantic-settings` to parse configuration variables (`FAMILYSEARCH_SESSION_ID`, `FAMILYSEARCH_ENV`, `FAMILYSEARCH_APP_KEY`).
   - Automatically resolves `.env` path and provides `base_url` selection (`https://api.familysearch.org` for production, `https://apibeta.familysearch.org` for sandbox/beta).
2. **`src/familysearch/auth.py` (`SessionManager`)**:
   - Manages HTTP headers (`Authorization: Bearer <fssessionid>`, `Accept: application/x-gedcomx-v1+json`).
   - Implements `validate_session()` to probe `/platform/users/current`.
   - Distinguishes between network errors, expired tokens (401/403), and valid sessions, providing clear actionable console instructions if the token must be refreshed.
3. **`src/familysearch/client.py` (`FamilySearchClient`)**:
   - Implements REST methods using `httpx.Client`.
   - Maps GEDCOM X resources for persons, pedigrees, relationships, sources, matches, and historical record searches.
   - Throws strongly typed exceptions: `FamilySearchAPIError`, `FamilySearchAuthError`, `FamilySearchNotFoundError`.
4. **`probe.py`**:
   - Rich CLI diagnostic utility that inspects the environment, validates the active session, and prints user account and root person details.

---

## 2. API Usage & Examples

### Basic Client Initialization
```python
from src.familysearch.client import FamilySearchClient

client = FamilySearchClient()
user = client.get_current_user()
print("Authenticated User:", user["users"][0]["displayName"])
```

### Fetching Person & Ancestry
```python
# Fetch root person profile
person_data = client.get_person("ABCD-123")
name = person_data["persons"][0]["display"]["name"]

# Fetch 4-generation pedigree tree
ancestry_data = client.get_ancestry("ABCD-123", generations=4)
```

### Inspecting Sources & Matches
```python
# Attached evidentiary sources
sources = client.get_person_sources("ABCD-123")

# Algorithmic hints and duplicates
matches = client.get_person_matches("ABCD-123", collection="records")
```

---

## 3. Verification & Test Coverage

### Automated Unit Tests (`tests/`)
* `tests/test_auth.py`: Tests empty token handling, header formatting, and validation failures without `.env`.
* `tests/test_client.py`: Tests client initialization, mock 200 responses, mock 401 auth errors, and mock 404 not found exceptions.
* Ran via `python -m pytest -v`: 7 passed in 1.18s.

### Live Production Probe
* Tested against live FamilySearch API endpoint:
  * User ID: `cis.user.SAMPLE-USER` (`Sample User`)
  * Root Person in Tree: `ABCD-123` (`Sample Ancestor (Male) - Deceased`)
  * Status: HTTP 200 OK.
