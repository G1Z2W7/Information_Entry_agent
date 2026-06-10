# Distributor Agent Contact Fallback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix contact follow-up capture, add extraction fallback, support contact structured patching, and handle address-resume chat turns safely.

**Architecture:** Keep the existing chat flow and state model intact, but harden it in three places: rule extraction for contact fragments, service-level fallback/intent interception, and structured patch validation plus frontend quick-fill support. Changes stay incremental and test-first to avoid refactoring the session/state model.

**Tech Stack:** FastAPI, Pydantic, pytest, vanilla HTML/JS playground, Docker Compose

---

### Task 1: Red Tests For Broken Contact Follow-Ups

**Files:**
- Modify: `tests/test_rule_extractor.py`
- Modify: `tests/test_state_merge.py`
- Modify: `tests/test_api_chat.py`
- Modify: `tests/test_models.py`

- [ ] Add failing extractor tests for `联系人职位是销售，微信号是手机号` and `联系人职位销售微信就是手机号`.
- [ ] Add failing merge test proving a single existing contact absorbs a position/wechat fragment instead of appending a new contact.
- [ ] Add failing API tests for chat fallback, contact structured patch, and `继续地址确认`.
- [ ] Run the targeted tests and confirm they fail for the intended reasons.

### Task 2: Backend Minimal Fixes

**Files:**
- Modify: `app/agent/extractor.py`
- Modify: `app/agent/state.py`
- Modify: `app/agent/service.py`
- Modify: `app/agent/models.py`
- Modify: `app/agent/enums.py`

- [ ] Tighten contact fragment extraction so contact role phrases are not misread as contact names, and normalize `微信号是手机号`.
- [ ] Merge fragment-only contact updates into the single/primary existing contact.
- [ ] Add rule-based fallback merging after LLM extraction and intercept `继续地址确认` before normal extraction.
- [ ] Expand structured patch validation to allow safe `contacts` updates.

### Task 3: Frontend Quick-Fill Support

**Files:**
- Modify: `app/playground/distributor_chat/index.html`
- Modify: `app/agent/enums.py`

- [ ] Add field option metadata for supported contact quick-fill fields.
- [ ] Let the playground build/send preview text for both `main_info` and `contacts`.
- [ ] Keep existing `main_info` behavior unchanged while enabling contact补录.

### Task 4: Verification

**Files:**
- Test: `tests/test_rule_extractor.py`
- Test: `tests/test_state_merge.py`
- Test: `tests/test_api_chat.py`
- Test: `tests/test_models.py`

- [ ] Run targeted pytest cases in Docker.
- [ ] Reproduce the original contact补录 messages in Docker Python and confirm the resulting state is correct.
- [ ] Summarize what changed, what passed, and any residual limitations.
