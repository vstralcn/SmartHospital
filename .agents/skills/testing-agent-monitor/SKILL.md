---
name: testing-agent-monitor
description: End-to-end test of the SmartHospital Multi-Agent (IoA) EMR system, the Agent Monitor dashboard, and the admin console (病例管理 / 智能体管理). Use when verifying the 7-agent pipeline, MCP tool calls, QC scoring, the /agent-monitor UI, or the admin case/agent management pages.
---

# Testing the Multi-Agent (IoA) Agent Monitor flow

## Architecture under test
7-agent pipeline (Interview -> Diagnosis -> Knowledge(RAG) -> Drug -> EMR -> QC -> FollowUp) orchestrated via LangGraph StateGraph in `backend/agents/orchestrator.py`, communicating via `AgentMessage`. Agents call a mock MCP layer (`backend/mcp/`: Drug/Disease/Lab); KnowledgeAgent does offline RAG over a local vector store (`backend/services/knowledge_base_service.py`, no API key). Each run persists rows to the `agent_execution_log` table; the Vue3 `/agent-monitor` dashboard polls `/api/agents/*` every ~1.5s.

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
  -d "{\"session_id\":\"$SID\",\"dialogues\":[{\"speaker\":\"patient\",\"text\":\"高血压头晕，吃过氨氯地平\"}]}"
curl -s -X POST :8000/api/diagnosis/complete -H 'Content-Type: application/json' -d "{\"session_id\":\"$SID\"}"
```
With the Agent Monitor open (auto-refresh ON), the new run appears live. Use a dialogue mentioning symptoms + drug names (e.g. high blood pressure, 氨氯地平/美托洛尔) to exercise drug MCP tools and to make cardiovascular RAG entries rank first.

## What to verify (UI — doctor /agent-monitor)
- `/agent-monitor` is behind the doctor auth guard -> logged-out visit redirects to `/login`.
- Flowchart: exactly 7 nodes, correct order (问诊采集 -> 诊断推理 -> 知识检索 -> 用药推荐 -> 病历整合 -> 质控审核 -> 随访计划), all reach `成功` (success); metrics show 7/7 completed, total tokens > 0.
- Click a node -> `MCP 工具调用` lists tools with args: diagnosis_agent -> `match_by_symptoms`,`query_disease`; drug_agent -> `search_drug`,`check_contraindication`; knowledge_agent -> `rag_search`. interview/emr/qc/followup call no MCP tools.
- `知识参考(RAG)` panel renders evidence citations with relevance scores; `随访计划` panel renders 复诊建议 + 复查项目 + 注意事项.
- QC node output `quality_control.score` MUST equal `100 - 15*len(issues) - 5*len(risk_alerts)` (verifies the score-recompute fix; a stale score would not match).
- `运行历史` gains new rows; clicking a row loads that run into the flowchart. MCP 服务 panel lists Drug/Disease/Lab + tools.

## What to verify (UI — admin console: 病例管理 / 智能体管理)
Admin pages live at `/admin/consultations` (`views/admin/AdminConsultationsView.vue`) and `/admin/agents` (`views/admin/AdminAgentsView.vue`), in the sidebar of `AdminLayout.vue`. Backend: `backend/routers/admin_consultation_router.py` (admin-only, `Depends(get_current_admin)`) + reused `/api/agents/*`. Login `admin`/`admin123`.
- **病例管理 (cross-doctor)**: stat cards `病例总数` / `涉及医生数` reflect ALL doctors' records (this is the key difference vs the doctor-scoped `/api/consultations`). Table lists every doctor's cases with 接诊医生 = name+department. A broken impl that reused the doctor-scoped endpoint would show 0 rows or only one doctor's cases.
- Doctor filter dropdown + keyword search (matches patient / EMR text / session ID) -> table narrows to matching rows.
- `查看详情` -> drawer shows 接诊医生, 会话 ID, 风险提示, structured fields, non-empty 病历全文, dialogue records.
- `删除` -> confirm dialog -> toast `病例已删除`, row disappears, `病例总数` stat decrements.
- **智能体管理**: stat cards 运行任务数 / 智能体执行次数 / 累计 Token / 异常次数 (from `agent_log_service.stats()`); 7-node pipeline overview; 运行记录 table (each row 节点=7, 成功); `详情` -> drawer with per-agent collapsible panels showing input/output JSON + 工具调用 tags; MCP 服务 panel.
- To seed admin test data: create a second doctor too (so `涉及医生数` > 1), then run the diagnosis pipeline under each doctor (set `doctor_id` in `/api/diagnosis/start`). The completed consultations + agent runs then populate both admin pages.

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
