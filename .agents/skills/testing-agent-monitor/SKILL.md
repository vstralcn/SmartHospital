---
name: testing-agent-monitor
description: End-to-end test of the SmartHospital Multi-Agent (IoA) EMR system and the Agent Monitor dashboard. Use when verifying the 5-agent pipeline, MCP tool calls, QC scoring, or the /agent-monitor UI.
---

# Testing the Multi-Agent (IoA) Agent Monitor flow

## Architecture under test
5-agent pipeline (Interview -> Diagnosis -> Drug -> EMR -> QC) orchestrated in `backend/agents/orchestrator.py`, communicating via `AgentMessage`. Agents call a mock MCP layer (`backend/mcp/`: Drug/Disease/Lab). Each run persists rows to the `agent_execution_log` table; the Vue3 `/agent-monitor` dashboard polls `/api/agents/*` every ~1.5s.

## Setup
- Backend: `cd backend && source .venv/bin/activate && LLM_PROVIDER=mock python -m uvicorn main:app --host 127.0.0.1 --port 8000` (mock provider needs no API key).
- Frontend: `cd frontend && npm run dev` (Vite on :5173, proxies `/api` -> :8000).
- Admin is auto-seeded: `admin` / `admin123` (see `services/admin_bootstrap_service.py`).
- No doctor is seeded. Create one (setup, not an assertion): admin login `POST /api/admin/auth/login` -> use token at `POST /api/admin/doctors` with `{username,password,full_name,department}`. Then doctor login at `/login`.

## Key limitation: no microphone / ASR
The UI voice flow (`开始诊断` -> record -> `完成诊断`) requires Tencent Cloud ASR config + a real mic. In a headless test box this is unavailable (warns `NO_ASR_CONFIG`), so `handleStart` keeps status `idle` and you cannot reach the `recording` state to click `完成诊断`. This is a PRE-EXISTING external dependency, NOT a refactor bug.

**Workaround:** trigger pipeline runs via the same endpoints the frontend calls after ASR produces text (all unauthenticated):
```
SID=$(curl -s -X POST :8000/api/diagnosis/start -d '{"doctor_id":1}' -H 'Content-Type: application/json' | jq -r .session_id)
curl -s -X POST :8000/api/diagnosis/transcribe -H 'Content-Type: application/json' \
  -d "{\"session_id\":\"$SID\",\"dialogues\":[{\"speaker\":\"patient\",\"text\":\"高血压头晕，吃过氨氯地平"}]}"
curl -s -X POST :8000/api/diagnosis/complete -H 'Content-Type: application/json' -d "{\"session_id\":\"$SID\"}"
```
With the Agent Monitor open (auto-refresh ON), the new run appears live. Use a dialogue mentioning symptoms + drug names (e.g. high blood pressure, 氨氯地平/美托洛尔) to exercise drug MCP tools.

## What to verify (UI)
- `/agent-monitor` is behind the doctor auth guard -> logged-out visit redirects to `/login`.
- Flowchart: exactly 5 nodes, correct order, all reach `成功` (success); metrics show 5/5 completed, total tokens > 0.
- Click a node -> `MCP 工具调用` lists tools with args: diagnosis_agent -> `match_by_symptoms`,`query_disease`; drug_agent -> `search_drug`,`check_contraindication`. interview/emr/qc call no tools.
- QC node output `quality_control.score` MUST equal `100 - 15*len(issues) - 5*len(risk_alerts)` (verifies the score-recompute fix; a stale score would not match).
- `运行历史` gains new rows; clicking a row loads that run into the flowchart. MCP 服务 panel lists Drug/Disease/Lab + tools.

## Concurrency check (race-condition fix, shell)
Fire several `/complete` runs in parallel, then assert each `task_id` has exactly 7 unique agent logs, all `success`, with consistent token sums:
```sql
select task_id, count(*), count(distinct agent_name) from agent_execution_log group by task_id;
```
logs table lives in `backend/data/app.db`. Per-task corruption (duplicate/missing agents, bleeding token counts) would indicate the singleton Orchestrator regressed to shared agent state.

## Notes
- No CI / GitHub Actions configured (Devin Review only).
- `/api/agents/*` endpoints are unauthenticated (read-only observability); the `/agent-monitor` route requires a doctor token in the browser. The admin `/api/admin/consultations*` endpoints DO require an admin token (`Depends(get_current_admin)`).

## Devin Secrets Needed
- None for the mock-provider path. Real LLM/ASR testing would need `OPENAI_API_KEY` and Tencent ASR credentials (configured via the admin panel), which are not required for verifying the multi-agent pipeline, dashboard, or admin pages.
