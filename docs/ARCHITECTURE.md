# 系统架构图

## 1. 整体架构

```mermaid
graph TD
    subgraph Frontend["前端 Vue 3 + Element Plus"]
        UI1[医生工作台 问诊/录音/病历]
        UI2[Agent Monitor 多智能体监控]
    end

    subgraph Backend["后端 FastAPI"]
        API[REST API /api/*]
        WS[WebSocket 实时音频流]
        ORC[Orchestrator · LangGraph StateGraph]
        subgraph Agents["智能体集群 (LangChain)"]
            A1[InterviewAgent]
            A2[DiagnosisAgent]
            A3[KnowledgeAgent · RAG]
            A4[DrugAgent]
            A5[EMRAgent]
            A6[QualityControlAgent]
            A7[FollowUpAgent]
        end
        MCP[MCP Registry<br/>Drug · Disease · Lab]
        KB[KnowledgeBaseService<br/>向量库 + 本地 Embeddings]
        PROV[Providers<br/>OpenAI / 本地 / Mock]
    end

    DB[(SQLite<br/>病历 / 智能体日志 / 配置)]

    UI1 -->|音频| WS
    UI1 -->|生成病历| API
    UI2 -->|拉取执行日志| API
    API --> ORC
    ORC --> Agents
    A2 --> MCP
    A3 --> KB
    A4 --> MCP
    Agents --> PROV
    ORC -->|执行日志 log_sink| DB
    API --> DB
```

## 2. 智能体协作流程（A2A 消息链）

```mermaid
graph LR
    START([ASR 转写]) --> I[InterviewAgent<br/>问诊采集]
    I --> D[DiagnosisAgent<br/>诊断推理]
    D --> K[KnowledgeAgent<br/>知识检索 RAG]
    K --> R[DrugAgent<br/>用药推荐]
    R --> E[EMRAgent<br/>病历整合]
    E --> Q[QualityControlAgent<br/>质控审核]
    Q --> F[FollowUpAgent<br/>随访计划]
    F --> OUT([结构化病历 + 质控意见 + 随访计划])

    D -. MCP .-> DS[(DiseaseServer)]
    K -. RAG .-> VS[(向量知识库)]
    R -. MCP .-> DR[(DrugServer/LabServer)]
```

每条箭头都是一次 `AgentMessage`（A2A）传递：上游智能体的输出经 `message.reply()` 合并进 `payload` 后递交给下游，`task_id` 贯穿全链路。

## 3. 数据流（一次问诊）

```mermaid
sequenceDiagram
    participant Doctor as 医生端
    participant API as FastAPI
    participant ORC as Orchestrator(LangGraph)
    participant AG as Agents
    participant KB as RAG 向量库
    participant DB as SQLite

    Doctor->>API: POST /api/diagnosis/generate-emr {session_id}
    API->>ORC: build_full_result(dialogues)
    ORC->>AG: invoke StateGraph (init AgentMessage)
    loop 每个智能体节点
        AG->>AG: handle(message) → 新 AgentMessage
        AG-->>DB: log_sink(执行记录)
    end
    AG->>KB: KnowledgeAgent.search(query)
    KB-->>AG: 循证参考片段
    ORC-->>API: EMRGenerationResult
    API-->>Doctor: 结构化病历 + 风险提示
    Doctor->>API: GET /api/agents/runs/session/{id}
    API->>DB: 查询执行日志
    DB-->>Doctor: 流水线/知识参考/随访计划 可视化
```

## 4. LangGraph 状态机

```mermaid
stateDiagram-v2
    [*] --> interview_agent
    interview_agent --> diagnosis_agent
    diagnosis_agent --> knowledge_agent
    knowledge_agent --> drug_agent
    drug_agent --> emr_agent
    emr_agent --> quality_control_agent
    quality_control_agent --> followup_agent
    followup_agent --> [*]
```

唯一状态通道为 `_WorkflowState.message`（`AgentMessage`）。当前为线性管线，架构上可平滑扩展为：质控不通过时回环至问诊补充（条件边）、知识检索与用药推荐并行（并行节点）等。
