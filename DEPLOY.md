# Cognee 安装部署说明

> 本文档面向开发人员，指导如何在本地或服务器上完成 Cognee 的安装、配置与测试。

---

## 目录

1. [环境要求](#1-环境要求)
2. [快速开始（本地开发）](#2-快速开始本地开发)
3. [Docker 部署（推荐生产方式）](#3-docker-部署推荐生产方式)
4. [环境变量配置详解](#4-环境变量配置详解)
5. [数据库配置](#5-数据库配置)
6. [前端部署](#6-前端部署)
7. [验证测试](#7-验证测试)
8. [常见问题排查](#8-常见问题排查)
9. [架构说明](#9-架构说明)

---

## 1. 环境要求

| 组件 | 版本要求 | 说明 |
|------|---------|------|
| Python | 3.10 - 3.13 | 推荐 3.12 |
| Node.js | >= 18 | 前端需要，推荐 22 |
| PostgreSQL | >= 15 | 关系型数据库，需安装 pgvector 扩展 |
| Git | 任意 | 代码获取 |
| Docker + Docker Compose | >= 24.0 | 如果使用容器化部署 |

### 操作系统

- **Windows 10/11**：已验证，需使用 `D:\` 或足够空间的磁盘
- **Linux (Ubuntu 20.04+)**：推荐生产环境
- **macOS**：开发环境可用

### 硬件建议

| 场景 | CPU | 内存 | 磁盘 |
|------|-----|------|------|
| 开发/测试 | 4 核 | 8 GB | 20 GB |
| 生产 | 8 核+ | 16 GB+ | 50 GB+ |

---

## 2. 快速开始（本地开发）

### 2.1 获取代码

```bash
git clone <仓库地址>
cd cognee
```

### 2.2 安装 Python 依赖

推荐使用 `uv`（比 pip 快 10-100 倍）：

```bash
# 安装 uv
pip install uv

# 创建虚拟环境并安装依赖
uv venv .venv

# Windows
.venv\Scripts\activate

# Linux/macOS
source .venv/bin/activate

# 安装项目（开发模式，含 PostgreSQL + 文档解析支持）
uv pip install -e ".[postgres,docs]"
```

如果不用 `uv`，也可以用 pip：

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # Linux/macOS
pip install -e ".[postgres,docs]"
```

### 2.3 配置环境变量

```bash
# 复制模板
cp .env.template .env

# 编辑 .env，至少配置以下必填项（详见第4节）
```

**最小必填配置**（`.env`）：

```env
# LLM 配置 - 使用阿里云 DashScope/Qwen
LLM_API_KEY=sk-你的密钥
LLM_MODEL=openai/qwen-plus
LLM_PROVIDER=custom
LLM_ENDPOINT=https://dashscope.aliyuncs.com/compatible-mode/v1

# Embedding 配置
EMBEDDING_PROVIDER=custom
EMBEDDING_MODEL=openai/text-embedding-v3
EMBEDDING_ENDPOINT=https://dashscope.aliyuncs.com/compatible-mode/v1
EMBEDDING_API_KEY=sk-你的密钥
EMBEDDING_DIMENSIONS=1024

# 数据库
DB_PROVIDER=postgres
POSTGRESQL_HOST=localhost
POSTGRESQL_PORT=5432
POSTGRESQL_USER=postgres
POSTGRESQL_PASSWORD=你的密码
POSTGRESQL_DATABASE=cognee_db

# 图数据库（默认 Kuzu，无需额外服务）
GRAPH_DATABASE_PROVIDER=kuzu

# 向量数据库（默认 LanceDB，无需额外服务）
VECTOR_DB_PROVIDER=lancedb
```

### 2.4 初始化 PostgreSQL 数据库

```bash
# 登录 PostgreSQL 并创建数据库
psql -U postgres
CREATE DATABASE cognee_db;
\q

# 运行数据库迁移
alembic upgrade head
```

### 2.5 启动后端服务

```bash
# 开发模式（支持热重载）
uvicorn cognee.api.client:app --host 0.0.0.0 --port 8000 --reload
```

访问 http://localhost:8000/health 验证服务状态。

### 2.6 启动前端（可选）

```bash
cd cognee-frontend
npm install
npm run dev
```

访问 http://localhost:3000 打开 Web UI。

---

## 3. Docker 部署（推荐生产方式）

### 3.1 使用 Docker Compose（一键启动）

```bash
# 确保 .env 文件已配置好
# 启动所有服务
docker-compose up -d

# 查看运行状态
docker-compose ps

# 查看日志
docker-compose logs -f cognee
```

Docker Compose 会启动以下服务：

| 服务 | 端口 | 说明 |
|------|------|------|
| `cognee` | 8000 | 后端 API |
| `frontend` | 3000 | Web UI |
| `postgres` | 5432 | PostgreSQL + pgvector |
| `qdrant` | 6333 | 向量数据库（可选） |

### 3.2 单独构建镜像

```bash
# 构建后端
docker build -t cognee/cognee:latest .

# 构建前端
docker build -t cognee/frontend:latest ./cognee-frontend

# 运行后端
docker run -d \
  --name cognee-api \
  -p 8000:8000 \
  --env-file .env \
  cognee/cognee:latest

# 运行前端
docker run -d \
  --name cognee-frontend \
  -p 3000:3000 \
  -e NEXT_PUBLIC_BACKEND_API_URL=http://你的服务器IP:8000 \
  cognee/frontend:latest
```

### 3.3 停止与清理

```bash
# 停止所有服务
docker-compose down

# 停止并删除数据卷（会丢失数据！）
docker-compose down -v
```

---

## 4. 环境变量配置详解

### 4.1 LLM（大语言模型）配置

| 变量名 | 说明 | 示例值 |
|--------|------|--------|
| `LLM_API_KEY` | LLM API 密钥 | `sk-xxxxxx` |
| `LLM_MODEL` | 模型名称 | `openai/qwen-plus` |
| `LLM_PROVIDER` | 提供商 | `openai` / `custom` / `ollama` |
| `LLM_ENDPOINT` | 自定义 API 端点 | `https://dashscope.aliyuncs.com/compatible-mode/v1` |

**支持的 LLM 提供商：**
- OpenAI（GPT-4 等）
- 阿里云 DashScope（Qwen 系列） - 当前配置
- Anthropic（Claude）
- Ollama（本地模型）
- Mistral、Groq 等

### 4.2 Embedding（向量嵌入）配置

| 变量名 | 说明 | 示例值 |
|--------|------|--------|
| `EMBEDDING_PROVIDER` | 嵌入提供商 | `custom` |
| `EMBEDDING_MODEL` | 嵌入模型 | `openai/text-embedding-v3` |
| `EMBEDDING_ENDPOINT` | API 端点 | 同 LLM 端点 |
| `EMBEDDING_API_KEY` | API 密钥 | 同 LLM 密钥 |
| `EMBEDDING_DIMENSIONS` | 向量维度 | `1024` |
| `EMBEDDING_BATCH_SIZE` | 批处理大小 | `10` |

### 4.3 数据库配置

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `DB_PROVIDER` | 关系型数据库 | `sqlite` |
| `POSTGRESQL_HOST` | PG 主机 | `localhost` |
| `POSTGRESQL_PORT` | PG 端口 | `5432` |
| `POSTGRESQL_USER` | PG 用户名 | `postgres` |
| `POSTGRESQL_PASSWORD` | PG 密码 | - |
| `POSTGRESQL_DATABASE` | PG 数据库名 | `cognee_db` |
| `GRAPH_DATABASE_PROVIDER` | 图数据库 | `kuzu` |
| `VECTOR_DB_PROVIDER` | 向量数据库 | `lancedb` |

### 4.4 安全与认证

| 变量名 | 说明 | 推荐值 |
|--------|------|--------|
| `REQUIRE_AUTHENTICATION` | 是否强制认证 | 生产: `True` |
| `ENABLE_BACKEND_ACCESS_CONTROL` | 多租户隔离 | 生产: `True` |

### 4.5 其他配置

| 变量名 | 说明 | 推荐值 |
|--------|------|--------|
| `LOG_LEVEL` | 日志级别 | 开发: `DEBUG`，生产: `INFO` |
| `ENV` | 环境标识 | `local` / `prod` |
| `CORS_ALLOWED_ORIGINS` | CORS 白名单 | `http://localhost:3000` |
| `UI_APP_URL` | 前端 URL | `http://localhost:3000` |
| `TELEMETRY_DISABLED` | 禁用遥测 | `true` |
| `TOKENIZERS_PARALLELISM` | 分词器并行 | `false` |

---

## 5. 数据库配置

### 5.1 PostgreSQL（关系型数据库）

**安装 PostgreSQL 15+：**

```bash
# Ubuntu
sudo apt update
sudo apt install postgresql-15

# Windows: 下载安装包
# https://www.postgresql.org/download/windows/
```

**创建数据库：**

```sql
-- 以 postgres 用户登录
psql -U postgres

-- 创建数据库
CREATE DATABASE cognee_db;

-- 可选: 创建专用用户
CREATE USER cognee_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE cognee_db TO cognee_user;

\q
```

**运行迁移：**

```bash
# 在项目根目录，激活虚拟环境后
alembic upgrade head
```

### 5.2 Kuzu（图数据库）

Kuzu 是 **文件型** 图数据库，无需额外安装或启动服务。

```env
GRAPH_DATABASE_PROVIDER=kuzu
# 可选: 指定存储路径
KUZU_DB_PATH=./data/kuzu_db
```

数据会自动存储在 `KUZU_DB_PATH` 指定的目录。

### 5.3 LanceDB（向量数据库）

LanceDB 也是 **文件型** 数据库，无需额外服务。

```env
VECTOR_DB_PROVIDER=lancedb
```

如在 Windows 上磁盘空间不足，可指定临时目录：

```env
LANCE_TEMP_DIR=D:\temp\lancedb_cache
```

### 5.4 可选: 使用 Neo4j 替代 Kuzu

```env
GRAPH_DATABASE_PROVIDER=neo4j
GRAPH_DATABASE_URL=bolt://localhost:7687
GRAPH_DATABASE_USERNAME=neo4j
GRAPH_DATABASE_PASSWORD=your_password
```

### 5.5 可选: 使用 Qdrant 替代 LanceDB

```env
VECTOR_DB_PROVIDER=qdrant
VECTOR_DB_URL=http://localhost:6333
```

---

## 6. 前端部署

### 6.1 开发模式

```bash
cd cognee-frontend
npm install
npm run dev
```

### 6.2 生产构建

```bash
cd cognee-frontend
npm install
npm run build
npm run start
```

### 6.3 环境变量

在 `cognee-frontend/.env` 中配置：

```env
NEXT_PUBLIC_BACKEND_API_URL=http://你的后端IP:8000
```

### 6.4 反向代理配置（Nginx 示例）

```nginx
server {
    listen 80;
    server_name your-domain.com;

    # 前端
    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # 后端 API
    location /api/ {
        proxy_pass http://127.0.0.1:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 300s;
    }

    # 健康检查
    location /health {
        proxy_pass http://127.0.0.1:8000/health;
    }
}
```

---

## 7. 验证测试

### 7.1 后端健康检查

```bash
# 基础健康检查
curl http://localhost:8000/health

# 期望返回:
# {"status": "healthy"}
```

### 7.2 API 接口测试

```bash
# 1. 添加文本数据
curl -X POST http://localhost:8000/api/v1/add \
  -H "Content-Type: application/json" \
  -d '{"data": "Natural language processing is a subfield of AI."}'

# 2. 构建知识图谱
curl -X POST http://localhost:8000/api/v1/cognify

# 3. 搜索
curl -X POST http://localhost:8000/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{"query": "What is NLP?"}'
```

### 7.3 运行单元测试

```bash
# 安装测试依赖
uv pip install -e ".[postgres,docs]"

# 运行全部单元测试
uv run pytest cognee/tests/unit/ -q

# 期望结果: 1311 passed, 4 skipped
```

### 7.4 CLI 测试

```bash
# 添加数据
cognee add "Cognee is a knowledge graph framework."

# 生成图谱
cognee cognify

# 搜索
cognee search "What is Cognee?"
```

### 7.5 前端测试

1. 打开 http://localhost:3000
2. 登录（默认用户会在首次启动时自动创建）
3. 上传一个文本文件或输入文本
4. 点击 "Cognify" 按钮
5. 查看生成的知识图谱可视化
6. 在搜索框输入查询并验证结果

---

## 8. 常见问题排查

### 8.1 后端启动失败

| 问题 | 原因 | 解决方案 |
|------|------|---------|
| `ModuleNotFoundError` | 依赖未安装 | `uv pip install -e ".[postgres,docs]"` |
| `Connection refused (PostgreSQL)` | 数据库未启动 | 启动 PostgreSQL 服务 |
| `Alembic migration error` | 数据库结构不匹配 | `alembic upgrade head` |
| 端口 8000 被占用 | 其他进程占用 | `netstat -ano \| findstr :8000` 找到并结束进程 |

### 8.2 LLM API 问题

| 问题 | 原因 | 解决方案 |
|------|------|---------|
| `API key not valid` | 密钥错误 | 检查 `.env` 中的 `LLM_API_KEY` |
| `Connection timeout` | 网络问题 | 检查网络或设置代理 |
| `Rate limit exceeded` | 请求过快 | 等待后重试，或升级 API 配额 |
| `Model not found` | 模型名错误 | 检查 `LLM_MODEL` 格式（如 `openai/qwen-plus`）|

### 8.3 前端问题

| 问题 | 原因 | 解决方案 |
|------|------|---------|
| 页面空白 | 后端未启动 | 确保后端在 8000 端口运行 |
| CORS 错误 | 跨域未配置 | `.env` 中设置 `CORS_ALLOWED_ORIGINS` |
| `npm install` 失败 | Node.js 版本低 | 升级到 Node.js 18+ |

### 8.4 Docker 问题

| 问题 | 原因 | 解决方案 |
|------|------|---------|
| 容器内无法连接 localhost | Docker 网络隔离 | 改用 `host.docker.internal` 或服务名 |
| 镜像构建缓慢 | 网络或缓存 | 使用国内镜像源 |
| 磁盘空间不足 | 镜像/卷过多 | `docker system prune` 清理 |

### 8.5 Windows 特有问题

| 问题 | 原因 | 解决方案 |
|------|------|---------|
| GBK 编码错误 | 文件读取编码 | 已修复（UTF-8 强制指定）|
| `nul` 文件错误 | Windows 保留文件名 | 已在 `.gitignore` 中排除 |
| 路径过长 | Windows 260 字符限制 | 启用长路径支持或缩短项目路径 |

---

## 9. 架构说明

### 9.1 系统架构图

```
┌─────────────────────────────────────────────────────┐
│                     客户端层                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │ Web UI   │  │  CLI     │  │  MCP Server      │  │
│  │ (Next.js)│  │ (Python) │  │  (SSE/HTTP)      │  │
│  │ :3000    │  │          │  │  :8001            │  │
│  └────┬─────┘  └────┬─────┘  └────────┬─────────┘  │
│       │              │                  │            │
│       └──────────────┼──────────────────┘            │
│                      ▼                               │
│  ┌───────────────────────────────────────────────┐  │
│  │             FastAPI 后端  (:8000)              │  │
│  │                                               │  │
│  │  /api/v1/add      - 数据添加                   │  │
│  │  /api/v1/cognify  - 知识图谱生成               │  │
│  │  /api/v1/search   - 搜索检索                   │  │
│  │  /api/v1/auth     - 认证授权                   │  │
│  │  /health          - 健康检查                    │  │
│  └───────────────────────────────────────────────┘  │
│                      │                               │
│       ┌──────────────┼──────────────┐               │
│       ▼              ▼              ▼               │
│  ┌─────────┐  ┌───────────┐  ┌──────────┐         │
│  │PostgreSQL│  │ Kuzu      │  │ LanceDB  │         │
│  │(关系型)  │  │ (图数据库) │  │(向量数据库)│         │
│  │ :5432    │  │ (文件型)   │  │ (文件型)  │         │
│  └─────────┘  └───────────┘  └──────────┘         │
│                                                     │
│                      │                               │
│                      ▼                               │
│  ┌───────────────────────────────────────────────┐  │
│  │           外部 LLM API                        │  │
│  │  DashScope/Qwen (Chat + Embedding)            │  │
│  │  https://dashscope.aliyuncs.com               │  │
│  └───────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

### 9.2 数据流

```
用户输入文本/文件
    │
    ▼
数据摄入 (add) ──────► 文档解析 ──────► 文本分块
                                            │
                                            ▼
                                    向量嵌入 (Embedding API)
                                            │
                                            ▼
                                    存入向量数据库 (LanceDB)
    │
    ▼
知识图谱生成 (cognify) ──► LLM 实体抽取 ──► 关系构建
                                                │
                                                ▼
                                         存入图数据库 (Kuzu)
    │
    ▼
搜索检索 (search)
    ├── 向量相似度搜索 (LanceDB)
    ├── 图谱遍历 (Kuzu)
    └── LLM 生成回答 (Qwen)
            │
            ▼
        返回结果给用户
```

### 9.3 端口汇总

| 服务 | 端口 | 协议 |
|------|------|------|
| 后端 API | 8000 | HTTP |
| 前端 UI | 3000 | HTTP |
| MCP 服务器 | 8001 | HTTP/SSE |
| PostgreSQL | 5432 | TCP |
| Qdrant（可选）| 6333 | HTTP |
| Neo4j（可选）| 7687 | Bolt |

---

## 附录: 部署检查清单

部署完成后，请逐项确认：

- [ ] **环境变量**: `.env` 文件已正确配置
- [ ] **PostgreSQL**: 数据库已创建，迁移已执行 (`alembic upgrade head`)
- [ ] **LLM API**: 密钥有效，API 端点可达
- [ ] **后端**: http://localhost:8000/health 返回 `healthy`
- [ ] **前端**: http://localhost:3000 页面正常加载
- [ ] **CORS**: 前后端跨域配置正确
- [ ] **添加数据**: 通过 API 或 UI 添加文本成功
- [ ] **Cognify**: 知识图谱生成成功
- [ ] **搜索**: 搜索查询返回相关结果
- [ ] **日志**: 无异常错误日志

---

*文档版本: 2026-02-24 | 测试环境: Windows 11 + Python 3.13 + PostgreSQL + Kuzu + LanceDB + Qwen*
