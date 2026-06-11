# 智能医疗病历系统 · 智能体互联网（IoA）设计文档

## 1. 系统概述

本系统是一个面向门诊问诊场景的 **智能体互联网（Internet of Agents, IoA）** 电子病历（EMR）辅助平台。它将医患问诊语音实时转写为文本后，交由一组**职责单一、相互协作的智能体**完成「问诊理解 → 诊断推理 → 循证检索 → 用药推荐 → 病历整合 → 质量控制 → 随访计划」的端到端流程。

与传统「单一 LLM 一次性生成病历」相比，IoA 架构带来三点核心价值：

- **可解释**：每个智能体只负责一件事并产出结构化结果，推理链条清晰可追溯；
- **可观测**：每次智能体执行的耗时、Token、工具调用、输入/输出全部落库，前端 Agent Monitor 实时回放；
- **可演进**：智能体之间只通过标准化消息（A2A）耦合，可独立替换、扩展或并行化。

技术上以 **LangChain + LangGraph** 为智能体开发与编排框架，以 **模拟 MCP（Model Context Protocol）** 工具服务为外部知识/工具接入层，以本地 **RAG 向量检索** 提供循证医学参考。

## 2. 总体架构

```
前端 (Vue 3 + Element Plus)
  ├─ 医生工作台 (问诊/录音/病历)
  └─ Agent Monitor (多智能体协作可视化)
        │  REST / WebSocket
        ▼
后端 (FastAPI)
  ├─ Orchestrator (LangGraph StateGraph)
  │     Interview → Diagnosis → Knowledge(RAG) → Drug → EMR → QualityControl → FollowUp
  ├─ Agents (LangChain)          每个智能体 = ProviderLLM + 角色提示词 + 工具
  ├─ MCP Registry                Drug / Disease / Lab 工具服务
  ├─ KnowledgeBaseService        RAG: 向量库 + 本地 Embeddings
  └─ Providers                   OpenAI / 本地 / Mock 可切换
        │
        ▼
持久层 (SQLite)  病历 / 智能体执行日志 / 配置
```

## 3. 智能体列表与职责

| # | 智能体 | 职责 | 关键输出字段 | 协作工具 |
|---|--------|------|--------------|----------|
| 1 | **InterviewAgent** 问诊采集 | 从 ASR 转写中提取主诉、现病史、症状、既往史等 | `chief_complaint` / `present_illness` / `symptoms` / `missing_info` | — |
| 2 | **DiagnosisAgent** 诊断推理 | 基于症状与疾病知识生成候选疾病与推理 | `primary_diagnosis` / `candidate_diseases` / `reasoning` | MCP: `match_by_symptoms` / `query_disease` |
| 3 | **KnowledgeAgent** 知识检索 | RAG 向量检索循证医学知识，给出参考与摘要 | `references[]` / `summary` | RAG: `rag_search`（向量库） |
| 4 | **DrugAgent** 用药推荐 | 推荐药物并核查禁忌/相互作用 | `recommendations` / `contraindication_alerts` | MCP: `search_drug` / `check_contraindication` |
| 5 | **EMRAgent** 病历整合 | 汇总上游结果生成结构化病历与病历文本 | `structured` / `emr_text` | — |
| 6 | **QualityControlAgent** 质控审核 | 审核完整性、逻辑一致性，评分与风险提示 | `passed` / `score` / `issues` / `risk_alerts` | — |
| 7 | **FollowUpAgent** 随访计划 | 生成复诊时间、复查项目与注意事项 | `next_visit` / `review_items` / `precautions` | — |

每个智能体继承 `BaseAgent`，统一封装：LangChain 运行链（`PromptTemplate | ProviderLLM | StrOutputParser`）、JSON 解析、MCP 工具调用、Token 估算与执行日志。所有智能体均带**启发式回退**，在 Mock Provider（无外部 LLM/API Key）下仍能产出可用结果，保证离线可演示。

## 4. 智能体通信协议（A2A）

智能体之间**禁止直接共享变量**，只通过标准化消息 `AgentMessage` 通信（见 `backend/agents/messages.py`）：

```python
class AgentMessage(BaseModel):
    message_id: str      # 全局唯一消息 ID
    task_id: str         # 贯穿同一次问诊的所有消息
    source: str          # 发送方智能体 (from_agent)
    target: str          # 接收方智能体 (to_agent)
    timestamp: str       # ISO 8601
    message_type: str    # MessageType 之一
    payload: dict        # 累积的结构化数据
```

消息类型 `MessageType`：

| 类型 | 用途 |
|------|------|
| `TASK_REQUEST` | 编排器/上游派发任务 |
| `TASK_RESULT` | 智能体回传处理结果 |
| `KNOWLEDGE_QUERY` | 知识检索请求 |
| `KNOWLEDGE_RESULT` | 知识检索结果 |
| `CONSENSUS_VOTE` | 多智能体共识投票（预留扩展） |

下游消息通过 `message.reply(source, target, payload)` 创建，自动继承 `task_id` 并在不可变前提下合并 `payload`，因此整条流水线天然可审计、可回放。

## 5. 编排：LangGraph 工作流

编排器 `Orchestrator`（`backend/agents/orchestrator.py`）使用 **LangGraph `StateGraph`** 将 7 个智能体编译为一个状态机：

```python
workflow = StateGraph(_WorkflowState)        # 状态唯一通道为 AgentMessage
for agent in agents:
    workflow.add_node(agent.name, make_node(agent, next_target))
workflow.set_entry_point("interview_agent")
# interview → diagnosis → knowledge → drug → emr → quality_control → followup → END
graph = workflow.compile()
final_state = graph.invoke({"message": init_message})
```

- **状态通道**：唯一可变状态是 A2A `message`；每个节点读入消息、运行对应智能体、产出新消息，符合 IoA「以消息为唯一耦合面」原则。
- **隔离性**：每次 `run()` 创建全新智能体实例并重新编译图，避免并发问诊间互相污染。
- **兼容性**：`build_full_result()` 作为旧单体 EMR 接口的**直接替代**，返回结构不变，前端零改动即可切换到多智能体流水线。

## 6. RAG 知识库

`KnowledgeBaseService`（`backend/services/knowledge_base_service.py`）：

1. 加载 `backend/data/medical_knowledge.json` 中的循证医学语料；
2. `RecursiveCharacterTextSplitter` 分块；
3. `LocalEmbeddings`（确定性、离线、无需 API Key）生成向量；
4. LangChain `InMemoryVectorStore` 建立索引，提供 `search(query, k)` 余弦相似度检索。

KnowledgeAgent 据诊断结果与症状构建查询，检索出带来源引用的知识片段供前端展示，并（在配置真实 LLM 时）由 LLM 蒸馏为循证摘要。

> 注：比赛提纲将 Qdrant / Redis 列为加分项。为保证评委可一键离线运行演示，本实现以**等价的轻量本地方案**替代重型外部服务；架构上 `KnowledgeBaseService` 的检索接口可平滑替换为 Qdrant 后端。

## 7. 可观测性

`BaseAgent.run()` 对每个智能体记录：状态、起止时间、耗时、Prompt/Completion Token、LLM 调用次数、MCP/RAG 工具调用、输入/输出快照，经 `log_sink` 写入 `agent_execution_log` 表。前端 `Agent Monitor` 通过 `/api/agents/*` 拉取并实时渲染流水线、节点详情、知识参考与随访计划。

## 8. 技术选型

| 维度 | 选型 | 理由 |
|------|------|------|
| 智能体框架 | LangChain | 比赛硬性要求；成熟的 LLM/链/工具抽象 |
| 编排 | LangGraph `StateGraph` | 显式多智能体工作流，状态可控、可扩展为条件分支/并行 |
| 工具协议 | 模拟 MCP | 显式工具边界，贴近真实 MCP 客户端分发 |
| 检索 | LangChain 向量库 + 本地 Embeddings | 离线可运行的 RAG，无需外部依赖 |
| 后端 | FastAPI | 高性能异步，便于 WebSocket 实时音频 |
| 前端 | Vue 3 + Element Plus | 既有技术栈，组件完善 |
| 模型接入 | Provider 抽象（OpenAI/本地/Mock） | 一键切换，离线可演示 |
