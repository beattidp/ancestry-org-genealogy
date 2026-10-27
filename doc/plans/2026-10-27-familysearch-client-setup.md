# FamilySearch API Client & Local Credential Management

Establish the foundational authentication, credential management, and API client layer to interact with FamilySearch's platform API (`api.familysearch.org/platform`) with high reliability and zero risk of credential leakage.

## User Review Required

> [!IMPORTANT]
> **Understanding `.env.example` vs `.env`**:
> - **`.env.example`**: A version-controlled template documenting all required configuration variables with placeholder values. **Do not rename or delete it.**
> - **`.env`**: Your local file containing your **real private credentials**. This file is strictly excluded by `.gitignore` so your login information is never committed to git.
> - **How to create `.env`**: Copy the template: `cp .env.example .env`, then open `.env` in an editor and insert your actual token or credentials.

> [!TIP]
> **How to get your FamilySearch `fssessionid` token**:
> 1. In your browser, log in to [familysearch.org](https://www.familysearch.org) (using your normal SSO, Google/Apple login, or Church account credentials).
> 2. Open Developer Tools (Press `F12` or `Ctrl+Shift+I` / `Cmd+Option+I`).
> 3. Navigate to **Application** (Chrome/Edge) or **Storage** (Firefox).
> 4. Expand **Cookies** in the left sidebar and click `https://www.familysearch.org`.
> 5. Find the row named `fssessionid` and copy the text in the **Value** column.
> 6. Paste it into your `.env` file: `FAMILYSEARCH_SESSION_ID="<pasted_token>"`.

## Proposed Changes

 Grouped by layer:

---

### Project Scaffolding & Security Layer

#### [NEW] [.gitignore](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/.gitignore)
- Ensure `.env`, `.venv/`, `scratch/`, `credentials.json`, `*.sqlite`, and Python cache directories are never committed.

#### [NEW] [.env.example](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/.env.example)
- Template file containing configuration keys:
  - `FAMILYSEARCH_SESSION_ID` (active session token from browser)
  - `FAMILYSEARCH_ENV` (`production` or `beta`, default `production`)
  - `FAMILYSEARCH_APP_KEY` (optional, for developer portal App Key)
  - Clear comments explaining how to fill in each value.

#### [NEW] [requirements.txt](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/requirements.txt)
- Pin core dependencies:
  - `httpx` (modern HTTP client with HTTP/2 and async/sync support)
  - `python-dotenv` (loads `.env` securely)
  - `pydantic` & `pydantic-settings` (typed configuration validation and schema enforcement)
  - `rich` (clean terminal formatting for research logs and verification probes)

---

### Core Client Architecture

#### [NEW] [src/config.py](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/src/config.py)
- Pydantic-based configuration model.
- Automatically reads `.env`.
- Validates token presence and provides user-friendly error instructions if `.env` is missing or the token is empty.

#### [NEW] [src/familysearch/auth.py](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/src/familysearch/auth.py)
- Session manager and token validator.
- Validates token by making a lightweight probe call to `GET /platform/users/current`.
- Distinguishes between valid sessions, expired sessions (`401 Unauthorized`), and permission boundaries.

#### [NEW] [src/familysearch/client.py](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/src/familysearch/client.py)
- Main `FamilySearchClient` class wrapping GEDCOM X REST endpoints:
  - `get_current_user()`: Returns authenticated user profile, display name, and contact ID.
  - `get_person(pid)`: Fetches full person GEDCOM X payload (vital events, names, gender).
  - `get_ancestry(pid, generations=4)`: Traverses pedigree ancestors.
  - `get_matches(pid)`: Fetches record hints / potential duplicates.
  - `get_sources(pid)`: Fetches citations, archival links, and evidence descriptions.
  - `search_records(query_params)`: Executes parameterized searches across the historical record archives.

#### [NEW] [probe.py](file:///home/beattidp/Documents/antigravity/ancestry-genealogy/probe.py)
- CLI connection test utility.
- Runs on startup:
  1. Checks if `.env` exists.
  2. Loads and tests the token against FamilySearch.
  3. Displays current user name, tree root PID, and connection health with rich formatting.

---

## Verification Plan

### Automated / Diagnostic Tests
1. **Virtual Environment & Dependencies**:
   - Create `.venv` and verify installation: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`.
2. **Configuration Validation**:
   - Run `probe.py` without `.env` to verify clear user guidance is displayed.
   - Copy `.env.example` to `.env` and verify prompt instructions.
3. **Live FamilySearch Connection Probe**:
   - Once the user enters their `FAMILYSEARCH_SESSION_ID` into `.env`, run:
     ```bash
     .venv/bin/python probe.py
     ```
   - Verify it returns HTTP 200 with the authenticated user profile and tree root PID.
