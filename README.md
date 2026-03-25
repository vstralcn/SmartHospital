# Medical EMR Web Assistant

智能医疗电子病历（EMR）Web 辅助系统 —— 基于语音识别与大语言模型，实时将医患问诊对话转录并自动生成结构化电子病历。

## 技术架构

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
│              │  └─────┬─────┘  └──────┬──────┘  │
│              │        │               │          │
│              │  ┌─────┴───────────────┴──────┐  │
│              │  │       Service Layer         │  │
│              │  │  LLM · ASR · EMR · Auth    │  │
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
- **仪表盘** — 系统概览
- **医生管理** — 增删改查医生账号
- **模型配置** — LLM Provider / 模型 / 参数动态配置
- **ASR 配置** — 语音识别引擎参数管理

## 项目结构

```
HospitalWeb/
├── docker-compose.yml          # 容器编排
├── .env.example                # 环境变量模板
├── backend/
│   ├── main.py                 # FastAPI 应用入口
│   ├── database.py             # SQLAlchemy 数据库配置
│   ├── config/settings.yaml    # 应用配置
│   ├── models/                 # 数据模型 (SQLAlchemy / Pydantic)
│   ├── routers/                # API 路由
│   ├── services/               # 业务逻辑层
│   ├── providers/              # LLM Provider 抽象 (OpenAI / Local / Mock)
│   ├── prompts/                # LLM Prompt 模板
│   ├── ws/                     # WebSocket 处理 (音频流)
│   ├── utils/                  # 工具函数
│   └── data/                   # 运行时数据 (SQLite DB / 临时文件)
├── frontend/
│   ├── src/
│   │   ├── views/              # 页面视图
│   │   ├── components/         # 可复用组件
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
