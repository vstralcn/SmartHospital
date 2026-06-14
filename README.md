# Medical EMR Web Assistant

智能医疗电子病历（EMR）Web 辅助系统 —— 基于语音识别与大语言模型，实时将医患问诊对话转录并自动生成结构化电子病历。

## 系统技术架构

```
┌──────────────────────────────────────────────────┐
│                   Nginx (:9080)                  │
│              静态资源 + 反向代理                    │
├──────────────┬───────────────────────────────────┤
│   Frontend   │            Backend                │
│  Vue 3 SPA   │     FastAPI + Uvicorn (:8000)     │
│  Vite 构建    │                                   │
│  Element Plus │  ┌───────────┐  ┌─────────────┐  │
│  Vue Router   │  │ REST API  │  │ WebSocket   │  │
│  Axios        │  │ /api/*    │  │ 实时音频流    │  │
│ Agent Monitor │  └─────┬─────┘  └──────┬──────┘  │
│              │        │               │          │
│              │  ┌─────┴───────────────┴──────┐  │
│              │  │  Orchestrator + 7 Agents    │  │
│              │  │ MCP·RAG(向量库)·ASR·LangGraph│  │
│              │  └─────────────┬───────────────┘  │
│              │          ┌─────┴─────┐            │
│              │          │ SQLite DB │            │
│              │          │ (app.db)  │            │
│              │          └───────────┘            │
└──────────────┴───────────────────────────────────┘
```

## 技术栈

| 层级 | 技术 |
|------|------|
| **前端** | Vue 3 + Vite 5 + Element Plus + Vue Router + Axios |
| **后端** | Python / FastAPI + Uvicorn + Pydantic v2 |
| **数据库** | SQLite (SQLAlchemy ORM) |
| **语音识别 (ASR)** | Vosk（本地离线） / 腾讯云 ASR |
| **大语言模型 (LLM)** | OpenAI API 兼容接口（支持 Mock / 本地 / OpenAI 多 Provider） |
| **实时通信** | WebSocket（音频流实时传输） |
| **文档导出** | python-docx（DOCX 格式） |
| **日志** | Loguru |
| **部署** | Docker Compose + Nginx 反向代理 |
| **多智能体** | LangChain + LangGraph `StateGraph` 编排 + A2A 消息协议 |
| **知识检索** | RAG（LangChain 向量库 + 本地 Embeddings，离线可用） |
| **工具协议** | 模拟 MCP（Model Context Protocol）服务 |

---

## 多智能体协作架构（Internet of Agents）

本系统将原本「单体式 LLM 一次性生成病历」的逻辑，重构为遵循 **Internet of Agents (IoA)** 理念的**多智能体协作系统**：每个智能体只负责单一职责、拥有明确的 JSON 输出契约，并且**只能通过标准化消息（AgentMessage）通信，禁止任何直接的变量共享**。这种设计带来更强的可解释性、可观测性与可扩展性，便于在比赛与生产中独立演进、替换或并行化每个智能体。

### 七大智能体（Agent Workflow）

由 `Orchestrator`（LangGraph `StateGraph`）按固定顺序编排，上一个智能体的输出经 A2A 消息传递给下一个：

```
ASR 转写
   │
   ▼
InterviewAgent → DiagnosisAgent → KnowledgeAgent → DrugAgent → EMRAgent → QualityControlAgent → FollowUpAgent
  问诊采集          诊断推理          知识检索(RAG)     用药推荐      病历整合      质控审核              随访计划
                      │ MCP             │ RAG            │ MCP
                      ▼                 ▼                ▼
                 DiseaseServer      向量知识库       DrugServer / LabServer
```

| 智能体 | 职责 | 关键输出字段 | 协作工具 |
|--------|------|--------------|------------------|
| **InterviewAgent** | 从 ASR 转写中提取主诉、现病史、症状、既往史 | `chief_complaint` / `present_illness` / `symptoms` | — |
| **DiagnosisAgent** | 基于问诊结果生成候选疾病与诊断推理 | `primary_diagnosis` / `candidate_diseases` / `reasoning` | MCP `match_by_symptoms` / `query_disease` |
| **KnowledgeAgent** | RAG 向量检索循证医学知识，提供带来源的参考与摘要 | `references` / `summary` | RAG `rag_search`（向量库） |
| **DrugAgent** | 推荐药物并核查禁忌/相互作用 | `recommendations` / `contraindication_alerts` | MCP `search_drug` / `check_contraindication` |
| **EMRAgent** | 汇总上游全部输出，生成结构化病历与病历文本 | `structured` / `emr_text` | — |
| **QualityControlAgent** | 审核病历完整性与逻辑一致性，给出评分与风险提示 | `passed` / `score` / `issues` / `risk_alerts` | — |
| **FollowUpAgent** | 根据诊断与病历生成随访计划 | `next_visit` / `review_items` / `precautions` | — |

### Orchestrator（编排器）

`backend/agents/orchestrator.py` 负责：

1. 为每次问诊生成唯一 `task_id`，创建初始 `AgentMessage`；
2. 将 7 个智能体编译为 **LangGraph `StateGraph`** 状态机，节点间以 `AgentMessage` 为唯一状态通道依次流转（A2A 链式传递）；
3. 通过 `log_sink` 回调把每个智能体的执行记录（耗时、Token、工具调用、I/O、状态）写入 `agent_execution_log`；
4. `build_full_result()` 作为旧单体 EMR 服务的**直接替代**，返回与原接口兼容的 `EMRGenerationResult`，因此前端与既有 API 无需改动即可切换到多智能体流水线。

### Agent 通信协议（A2A）

所有智能体之间**仅通过** `AgentMessage`（`backend/agents/messages.py`）通信：

```python
class AgentMessage(BaseModel):
    message_id: str     # 全局唯一消息 ID
    task_id: str        # 贯穿整条流水线，用于关联同一次问诊的所有日志
    source: str         # 发送方智能体名 from_agent（或 "orchestrator"）
    target: str         # 接收方智能体名 to_agent
    timestamp: str      # ISO 8601 时间戳
    message_type: str   # MessageType: task_request / task_result / knowledge_query / ...
    payload: dict       # 累积的结构化数据（interview / diagnosis / knowledge / drug / emr / quality_control / follow_up）
```

- 下游消息通过 `message.reply(source, target, payload)` 创建，自动继承 `task_id` 并合并 payload；
- 智能体之间**不共享任何可变全局状态**，符合 IoA「以消息为唯一耦合面」的原则；
- 消息类型由 `MessageType`（`task_request` / `task_result` / `knowledge_query` / `knowledge_result` / `consensus_vote`）定义。

> 详细设计见 [`docs/DESIGN.md`](docs/DESIGN.md)、架构与流程图见 [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)、各智能体提示词见 [`docs/PROMPTS.md`](docs/PROMPTS.md)。

### MCP 服务设计（Model Context Protocol 模拟）

`backend/mcp/` 实现了一个轻量级的 MCP 模拟层，三个独立的工具服务以 **SQLite + JSON 种子**落地，统一由 `MCPRegistry` 路由调用：

| 服务 | 工具 | 说明 | 数据源 |
|------|------|------|--------|
| **DrugServer** | `search_drug(name)`<br>`check_contraindication(name, conditions)` | 查询药物说明/用法/禁忌；按患者状态核查禁忌 | `mcp/data/drugs.json` |
| **DiseaseServer** | `query_disease(name)`<br>`match_by_symptoms(symptoms)` | 查询疾病知识；按症状匹配候选疾病 | `mcp/data/diseases.json` |
| **LabServer** | `query_lab(name)` | 查询检验/检查项目参考范围与临床意义 | `mcp/data/labs.json` |

- 每个工具都带有 `name` / `description` / JSON `parameters` 模式，供智能体（及监控前端）发现与调用；
- 首次运行时自动从 JSON 种子文件填充 SQLite（`mcp/data/mcp.db`），数据库访问通过线程锁保证并发安全。

### 可观测性与监控（Observability）

- **后端**：新增 `agent_execution_log` 表，记录每个智能体的 `agent_name`、`status`、开始/结束时间、`duration_ms`、Token 用量（prompt/completion/total）、`llm_calls`、`tool_calls`、输入/输出 payload 与错误信息。`AgentLogService` 提供按 `task_id` / `session_id` 的查询与运行历史聚合。
- **监控 API**（`/api/agents/*`）：

  | 接口 | 说明 |
  |------|------|
  | `GET /api/agents/pipeline` | 智能体流水线定义 |
  | `GET /api/agents/servers` | MCP 服务及其工具清单 |
  | `GET /api/agents/runs` | 最近运行列表（含耗时/Token/状态聚合） |
  | `GET /api/agents/runs/latest` | 最近一次运行的完整日志 |
  | `GET /api/agents/runs/session/{session_id}` | 指定会话的最近一次运行 |
  | `GET /api/agents/runs/{task_id}` | 指定任务的完整日志 |

- **前端「智能体监控」面板**（`/agent-monitor`，Vue3 + Element Plus）：以**流程图**形式可视化 7 个智能体节点的实时执行状态、每个节点的执行耗时与 Token 用量，点击节点可查看其 MCP/RAG 工具调用与输入/输出 payload；并独立展示 **知识参考(RAG)** 与 **随访计划** 面板，提供运行历史与 MCP 服务清单。面板默认每 1.5s 轮询后端，实时反映 Orchestrator 的执行进度。

### 如何运行多智能体流程

1. 启动后端与前端（见下方「快速开始」）。无需任何外部 LLM 密钥即可体验——默认 `mock` Provider 会驱动完整流水线，MCP 工具调用为真实的本地查询。
2. 医生端开始一次问诊（或在「智能体监控」中查看历史运行）。完成问诊时，`/api/diagnosis/complete` 会触发 `Orchestrator`（LangGraph）依次运行 7 个智能体并落库日志。
3. 打开顶部导航「**智能体监控**」进入 `/agent-monitor`，即可看到本次问诊的智能体协作流程图与实时指标。

> 说明：生成内容仅作为医生书写病历的辅助草稿，需由医生审核确认。

## 功能模块

### 医生端
- **医生登录** — 账号密码认证
- **问诊录音** — 浏览器录音，WebSocket 实时传输音频流
- **实时转录** — ASR 语音转文字，支持说话人分离（医生/患者）
- **AI 辅助诊断** — LLM 分析对话内容，提取结构化信息
- **EMR 生成** — 自动生成电子病历，支持编辑修改
- **病历导出** — 导出为 DOCX 文档
- **问诊历史** — 查看历史问诊记录

### 管理后台
- **管理员登录** — 独立认证体系
- **仪表盘** — 系统概览与各模块快捷入口
- **医生管理** — 增删改查医生账号
- **模型配置** — LLM Provider / 模型 / 参数动态配置
- **ASR 配置** — 语音识别引擎参数管理
- **病例管理** — 查看**全部医生**的问诊病历（按医生/关键字筛选、查看详情抽屉、删除），管理员专用接口 `admin_consultation_router`
- **智能体管理** — 全部智能体运行记录与统计（任务数/执行次数/Token/异常）、7 节点流水线总览、运行下钻（逐 Agent 输入输出与工具调用）与 MCP 服务面板

### 统一导航与跨端互通
- **医生端统一顶部导航**（`DoctorNav`）：品牌 + 高亮当前页的「问诊工作台 / 问诊记录 / 智能体监控」+ 医生信息下拉（科室 / 管理员后台 / 退出），三页复用，导航上下文（如当前会话）随路由保持。
- **管理员 ↔ 医生互通**：管理后台侧栏提供「返回医生工作台」入口；管理员登录页与医生登录页互设对方入口，实现两端一键跳转。
- **自适应布局**：页面容器统一采用 `min-height: 100dvh` 随文档自然滚动（替代旧的 `height:100%; overflow:hidden`），修复长内容页面底部被裁剪、无法滚动的问题；后台侧栏 `sticky` 常驻，问诊工作台保持底部操作栏固定的 app-shell 布局，并适配移动端浏览器地址栏。

## 项目结构

```
HospitalWeb/
├── docker-compose.yml          # 容器编排
├── .env.example                # 环境变量模板
├── backend/
│   ├── main.py                 # FastAPI 应用入口
│   ├── database.py             # SQLAlchemy 数据库配置
│   ├── config/settings.yaml    # 应用配置
│   ├── agents/                 # 多智能体 (BaseAgent / 7 Agents / LangGraph Orchestrator / A2A 消息)
│   ├── data/                   # RAG 医学知识语料 (medical_knowledge.json)
│   ├── mcp/                    # 模拟 MCP 工具服务 (Drug / Disease / Lab + JSON 种子)
│   ├── models/                 # 数据模型 (SQLAlchemy / Pydantic, 含 agent_execution_log)
│   ├── routers/                # API 路由 (含 agents_router 监控接口、admin_consultation_router 全病例管理)
│   ├── services/               # 业务逻辑层 (含 agent_log_service)
│   ├── providers/              # LLM Provider 抽象 (OpenAI / Local / Mock)
│   ├── prompts/                # LLM Prompt 模板
│   ├── ws/                     # WebSocket 处理 (音频流)
│   ├── utils/                  # 工具函数
│   └── data/                   # 运行时数据 (SQLite DB / 临时文件)
├── frontend/
│   ├── src/
│   │   ├── views/              # 页面视图 (含 AgentMonitorView 智能体监控、admin/ 后台病例与智能体管理)
│   │   ├── components/         # 可复用组件 (含 DoctorNav 统一顶部导航)
│   │   ├── api/                # API 请求封装
│   │   ├── composables/        # Vue 组合式函数
│   │   ├── router/             # 路由配置
│   │   ├── layouts/            # 布局组件
│   │   └── styles/             # 样式文件
│   ├── index.html
│   ├── vite.config.js
│   └── nginx.conf              # Nginx 配置
```

## 快速开始

### 环境要求

- Docker & Docker Compose

### 部署

```bash
# 1. 克隆项目
git clone <repo-url> && cd HospitalWeb

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env，填入 OPENAI_API_KEY 等配置

# 3. 启动服务
docker compose up -d
```

访问 `http://localhost:9080` 即可使用。

### 本地开发

**后端：**
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**前端：**
```bash
cd frontend
npm install
npm run dev
```

## 环境变量

| 变量名 | 说明 |
|--------|------|
| `OPENAI_API_KEY` | OpenAI API 密钥（LLM 功能必需） |

## License

Private
