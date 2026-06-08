# Location Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone location parsing agent that resolves location inputs into normalized address fields without integrating it into the main distributor agent flow yet.

**Architecture:** Create an independent `app/location_agent` package with its own request/response models, tool interfaces, LLM analysis contract, and orchestration service. Keep the current `app/agent` flow untouched; verify behavior with focused unit tests that use fake tools and fake LLM outputs.

**Tech Stack:** Python 3.11, FastAPI, Pydantic, httpx, pytest, Docker Compose

---

### Task 1: Define standalone models and first failing tests

**Files:**
- Create: `app/location_agent/__init__.py`
- Create: `app/location_agent/models.py`
- Test: `tests/test_location_agent.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_location_agent_requests_current_location_candidates_when_user_did_not_provide_address() -> None:
    ...


def test_location_agent_returns_resolved_address_when_precise_search_hits_single_candidate() -> None:
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec app python -m pytest .worktrees/location-agent/tests/test_location_agent.py -q`
Expected: FAIL with import errors for `app.location_agent`

- [ ] **Step 3: Write minimal implementation**

```python
class LocationAgentRequest(BaseModel):
    session_id: str
    user_message: str | None = None
    state: LocationState | None = None


class LocationAgentResponse(BaseModel):
    status: str
```

- [ ] **Step 4: Run test to verify it still fails for missing behavior**

Run: `docker compose exec app python -m pytest .worktrees/location-agent/tests/test_location_agent.py -q`
Expected: FAIL on assertions instead of import errors

- [ ] **Step 5: Commit**

```bash
git add app/location_agent/__init__.py app/location_agent/models.py tests/test_location_agent.py
git commit -m "test: add standalone location agent model coverage"
```

### Task 2: Implement orchestration service and tool contracts

**Files:**
- Create: `app/location_agent/service.py`
- Create: `app/location_agent/tools.py`
- Modify: `app/location_agent/models.py`
- Test: `tests/test_location_agent.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_location_agent_returns_candidate_selection_when_precise_search_has_multiple_matches() -> None:
    ...


def test_location_agent_resolves_selected_candidate_from_previous_search_state() -> None:
    ...


def test_location_agent_requests_more_detail_for_fuzzy_location() -> None:
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec app python -m pytest .worktrees/location-agent/tests/test_location_agent.py -q`
Expected: FAIL because service logic is missing

- [ ] **Step 3: Write minimal implementation**

```python
class LocationAgentService:
    def handle(self, request: LocationAgentRequest) -> LocationAgentResponse:
        ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose exec app python -m pytest .worktrees/location-agent/tests/test_location_agent.py -q`
Expected: PASS for candidate selection and fuzzy-detail tests

- [ ] **Step 5: Commit**

```bash
git add app/location_agent/models.py app/location_agent/service.py app/location_agent/tools.py tests/test_location_agent.py
git commit -m "feat: add standalone location agent service flow"
```

### Task 3: Add typo-correction and user-confirmed fallback behavior

**Files:**
- Modify: `app/location_agent/service.py`
- Modify: `app/location_agent/models.py`
- Test: `tests/test_location_agent.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_location_agent_uses_corrected_queries_before_asking_user_to_select() -> None:
    ...


def test_location_agent_returns_user_confirmed_address_when_manual_confirmation_is_provided() -> None:
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec app python -m pytest .worktrees/location-agent/tests/test_location_agent.py -q`
Expected: FAIL on typo-correction or `user_confirmed` fallback assertions

- [ ] **Step 3: Write minimal implementation**

```python
if analysis.corrected_queries:
    ...

if request.manual_input_payload and request.manual_input_payload.confirm:
    ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose exec app python -m pytest .worktrees/location-agent/tests/test_location_agent.py -q`
Expected: PASS for corrected query and manual confirmation fallback

- [ ] **Step 5: Commit**

```bash
git add app/location_agent/models.py app/location_agent/service.py tests/test_location_agent.py
git commit -m "feat: add location agent fallback resolution"
```

### Task 4: Focused verification

**Files:**
- Test: `tests/test_location_agent.py`
- Test: `tests/test_address_resolver.py`
- Test: `tests/test_models.py`

- [ ] **Step 1: Run focused verification for the new standalone agent**

Run: `docker compose exec app python -m pytest .worktrees/location-agent/tests/test_location_agent.py -q`
Expected: PASS

- [ ] **Step 2: Run nearby existing tests to detect regressions**

Run: `docker compose exec app python -m pytest .worktrees/location-agent/tests/test_address_resolver.py .worktrees/location-agent/tests/test_models.py -q`
Expected: PASS

- [ ] **Step 3: Review diff**

Run: `git -C /Users/ganzhiwen/workspace/InformationEntryAgent/.worktrees/location-agent diff --stat`
Expected: Only standalone location-agent files and tests are touched

- [ ] **Step 4: Commit**

```bash
git add app/location_agent tests/test_location_agent.py docs/superpowers/plans/2026-06-05-location-agent-implementation.md
git commit -m "feat: implement standalone location agent"
```

### Task 5: Add real AMap adapters and API coverage

**Files:**
- Modify: `app/location_agent/models.py`
- Modify: `app/location_agent/tools.py`
- Create: `app/location_agent/amap.py`
- Create: `app/api/location_agent.py`
- Modify: `app/main.py`
- Test: `tests/test_location_agent_amap.py`
- Test: `tests/test_api_location_agent.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_amap_searcher_maps_regeo_and_nearby_results_into_candidates() -> None:
    ...


def test_location_agent_api_nearby_endpoint_uses_request_coordinates() -> None:
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec app python -c "import os, pytest; os.chdir('/workspace/.worktrees/location-agent'); raise SystemExit(pytest.main(['tests/test_location_agent_amap.py', 'tests/test_api_location_agent.py', '-q']))"`
Expected: FAIL because AMap adapter and standalone API router are missing

- [ ] **Step 3: Write minimal implementation**

```python
class AMapSearchError(RuntimeError):
    ...


class AMapMapSearcher:
    def nearby(self, latitude: float, longitude: float) -> list[LocationCandidate]:
        ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose exec app python -c "import os, pytest; os.chdir('/workspace/.worktrees/location-agent'); raise SystemExit(pytest.main(['tests/test_location_agent_amap.py', 'tests/test_api_location_agent.py', '-q']))"`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/location_agent/amap.py app/api/location_agent.py app/main.py tests/test_location_agent_amap.py tests/test_api_location_agent.py
git commit -m "feat: add standalone location agent amap api"
```

### Task 6: Add browser playground for real manual testing

**Files:**
- Create: `app/playground/location_agent/index.html`
- Modify: `app/main.py`
- Test: `tests/test_playground.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_location_agent_playground_page_is_served() -> None:
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec app python -c "import os, pytest; os.chdir('/workspace/.worktrees/location-agent'); raise SystemExit(pytest.main(['tests/test_playground.py', '-q']))"`
Expected: FAIL because the standalone location playground route is missing

- [ ] **Step 3: Write minimal implementation**

```html
<button id="locate">获取当前位置</button>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose exec app python -c "import os, pytest; os.chdir('/workspace/.worktrees/location-agent'); raise SystemExit(pytest.main(['tests/test_playground.py', '-q']))"`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/playground/location_agent/index.html app/main.py tests/test_playground.py
git commit -m "feat: add location agent playground"
```

### Task 7: Docker end-to-end verification

**Files:**
- Test: `tests/test_location_agent.py`
- Test: `tests/test_location_agent_amap.py`
- Test: `tests/test_api_location_agent.py`
- Test: `tests/test_playground.py`

- [ ] **Step 1: Run focused standalone suite**

Run: `docker compose exec app python -c "import os, pytest; os.chdir('/workspace/.worktrees/location-agent'); raise SystemExit(pytest.main(['tests/test_location_agent.py', 'tests/test_location_agent_amap.py', 'tests/test_api_location_agent.py', 'tests/test_playground.py', 'tests/test_address_resolver.py', 'tests/test_models.py', '-q']))"`
Expected: PASS

- [ ] **Step 2: Start or reload Docker app service if needed**

Run: `docker compose up -d app`
Expected: app service is running with the worktree code mounted

- [ ] **Step 3: Browser smoke test**

Open: `http://localhost:8000/playground/location-agent`
Expected: page loads, can fetch browser coordinates, can hit standalone location-agent API endpoints, and can render nearby/search candidates

- [ ] **Step 4: Commit**

```bash
git add app/api/location_agent.py app/location_agent app/playground/location_agent tests docs/superpowers/plans/2026-06-05-location-agent-implementation.md
git commit -m "feat: wire real amap location agent testing flow"
```
