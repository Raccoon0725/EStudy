# StudyQuest 功能与结构文档

> 生成日期：2026-05-14 | 项目路径：`C:\Users\64247\Desktop\AICG\StudyQuest`

---

## 目录

1. [项目概述](#1-项目概述)
2. [目录结构](#2-目录结构)
3. [系统架构](#3-系统架构)
4. [模块详解](#4-模块详解)
   - 4.1 [config — 配置管理](#41-config--配置管理)
   - 4.2 [schemas — 数据模型](#42-schemas--数据模型)
   - 4.3 [database — 数据库层](#43-database--数据库层)
   - 4.4 [graph — LangGraph 编排](#44-graph--langgraph-编排)
   - 4.5 [agents — 智能体层](#45-agents--智能体层)
   - 4.6 [rag — 向量检索](#46-rag--向量检索)
   - 4.7 [tools — 工具集](#47-tools--工具集)
   - 4.8 [utils — 工具函数](#48-utils--工具函数)
   - 4.9 [middleware — 已废弃路由](#49-middleware--已废弃路由)
   - 4.10 [app.py / main.py — 双入口](#410-apppy--mainpy--双入口)
5. [数据流](#5-数据流)
6. [数据库 Schema](#6-数据库-schema)
7. [外部服务依赖](#7-外部服务依赖)
8. [API 接口](#8-api-接口)
9. [安全分析](#9-安全分析)
10. [配置参考](#10-配置参考)

---

## 1. 项目概述

**StudyQuest** 是一个基于多智能体架构的 AI 学习助手系统。用户通过自然语言描述学习目标，系统自动：

- **规划学习关卡**（Planner Agent）—— 将目标拆解为可执行的 20-50 分钟任务块
- **上传学习资料**（Librarian Agent）—— PDF/图片/Word/PPT 的 OCR 识别 → 向量化入库
- **AI 答疑**（Coach Agent）—— RAG 增强 + 三种应答模式（提示/讲解/复盘）
- **学习复盘**（Reviewer Agent）—— 薄弱点分析 + 明日学习建议
- **自然语言路由**（Classifier Agent）—— 自由输入，自动分类到上述四种功能

### 技术栈

| 层 | 技术选型 |
|---|---|
| 编排框架 | **LangGraph** (StateGraph + Conditional Edges) |
| LLM 网关 | **LangChain** (ChatAnthropic / ChatOpenAI 兼容) |
| 向量数据库 | **Qdrant** (1536 维余弦相似度) |
| 关系数据库 | **MySQL** (SQLAlchemy + PyMySQL, 7 表) |
| 嵌入模型 | text-embedding-3-small |
| OCR 模型 | Doubao-Seed-2.0-pro (GPT-4o 兼容视觉) |
| 联网搜索 | Tavily API |
| Web 框架 | Flask + flask-cors |
| CLI | Python argparse + Rich 终端美化 |
| 文件处理 | PyPDF2 / python-docx / python-pptx / Pillow |
| 数据校验 | Pydantic v2 |

---

## 2. 目录结构

```
StudyQuest/
├── .env                          # 环境变量（含 API Key，不入库）
├── .env.example                  # 环境变量模板
├── requirements.txt              # 依赖清单（25 个包）
├── app.py                        # Flask REST API 入口
├── main.py                       # CLI 交互入口
├── test_env.py                   # 6 项服务连通性测试
├── test_plan.json                # 测试用规划输出样例
├── API接口文档.md                 # 对外接口文档
├── 测试文档.md                    # 14 个测试用例及结果
│
├── config/
│   └── __init__.py               # 全局配置（env 加载 + 常量 + LLM 工厂）
│
├── schemas/
│   └── __init__.py               # Pydantic v2 数据模型（请求/响应/枚举）
│
├── graph/
│   ├── __init__.py
│   ├── state.py                  # GraphState TypedDict 定义
│   └── workflow.py               # LangGraph 图构建 + 7 个节点函数
│
├── agents/
│   ├── __init__.py
│   ├── base.py                   # BaseAgent 抽象基类
│   ├── classifier.py             # ClassifierAgent — 意图分类（chat → plan/qa/review）
│   ├── planner.py                # PlannerAgent — 学习规划
│   ├── librarian.py              # LibrarianAgent — 资料处理
│   ├── coach.py                  # CoachAgent — RAG 答疑
│   └── reviewer.py               # ReviewerAgent — 学习复盘
│
├── rag/
│   ├── __init__.py
│   ├── qdrant_store.py           # Qdrant 向量数据库封装
│   └── retriever.py              # RAG 检索器（Embedding → Qdrant → 格式化）
│
├── tools/
│   ├── __init__.py
│   ├── ocr.py                    # 多模态 OCR + 文件类型路由
│   ├── rag_search.py             # RAG 搜索 LangChain Tool
│   └── web_search.py             # Tavily 联网搜索 LangChain Tool
│
├── database/
│   ├── __init__.py
│   ├── connection.py             # MySQL 连接池 + 建库建表 DDL
│   └── repository.py             # CRUD 操作层（7 个实体）
│
├── utils/
│   ├── __init__.py
│   ├── file_storage.py           # 本地文件存储（含安全校验）
│   └── logger.py                 # 结构化日志
│
├── middleware/
│   ├── __init__.py
│   └── router.py                 # [已废弃] RequestRouter
│
└── workspace/                    # 运行时数据目录（不入库）
    ├── uploads/                  # 用户上传文件
    ├── .agent/tasks/             # 任务 YAML 文件
    └── .checkpoint.db            # LangGraph checkpointer
```

---

## 3. 系统架构

### 3.1 LangGraph 工作流图

```
__start__
    │
    ▼
classifier (chat 预处理：LLM 分类改写 request_type)
    │
    ├── error? ──→ format_response ──→ END
    │
    ▼
supervisor (读取 request_type，条件路由)
    │
    ├── plan    → planner_node   (PlannerAgent)
    ├── upload  → librarian_node (LibrarianAgent)
    ├── qa      → coach_node     (CoachAgent)
    ├── review  → reviewer_node  (ReviewerAgent)
    │
    └── 全部 ──→ format_response_node
                    │
                    ▼
                  END
```

### 3.2 请求生命周期

```
HTTP POST /api/studyquest
  → Flask 解析 JSON → StudyQuestRequest (Pydantic 校验)
    → build_state_from_request() → GraphState
      → graph.invoke(state)
        → classifier_node (chat 分类 / 其他透传)
        → supervisor_node (写 next_agent)
        → route_by_request_type → Agent 节点
        → format_response_node (组装统一响应)
      → final_state
    → Flask jsonify() 返回
```

### 3.3 设计模式来源

项目遵循 `Agent系统通用设计模式.md` 中的 **A2A 编排模式（第 7 章）**：

- 每个 Agent 是一个 **Node**，Agent 之间的交接是 **Edge**
- 共享上下文通过 **State**（`GraphState` TypedDict）在图中流转
- 路由决策由 **Conditional Edge** 实现（`route_by_request_type`）
- 任务持久化采用 **文件系统方案**（`_index.jsonl` + `T*.md`，第 4 章）

---

## 4. 模块详解

### 4.1 config — 配置管理

**文件**: `config/__init__.py` (99 行 → 133 行含安全配置)

**职责**: 加载 `.env` → 提供全局配置常量 → LLM/Embedding 工厂函数

```
dotenv 加载 → 环境变量读取（含默认值，共 29 个常量）
  ├─ LLM 配置 (ANTHROPIC_API_KEY, ANTHROPIC_MODEL, LLM_PROVIDER)
  ├─ OpenAI 配置 (OPENAI_API_KEY, OPENAI_BASE_URL)
  ├─ Embedding 配置 (EMBEDDING_API_KEY, EMBEDDING_BASE_URL, EMBEDDING_MODEL)
  ├─ Tavily (TAVILY_API_KEY)
  ├─ Qdrant (QDRANT_URL, QDRANT_HOST, QDRANT_PORT, QDRANT_COLLECTION)
  ├─ MySQL (MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE, MYSQL_URL)
  ├─ Flask (FLASK_HOST, FLASK_PORT, FLASK_DEBUG)
  ├─ 文件存储 (UPLOAD_DIR, TASK_DIR)
  ├─ RAG (RAG_TOP_K, RAG_CHUNK_SIZE, RAG_CHUNK_OVERLAP, RAG_SIMILARITY_THRESHOLD)
  ├─ 文件上传安全 (MAX_FILE_SIZE_MB=50, ALLOWED_EXTENSIONS, MAX_FILENAME_LENGTH=255)
  └─ 学习规则 (TASK_MIN/MAX_MINUTES, SAME_SUBJECT_MAX_MINUTES, BREAK_MINUTES, WEAK_POINT_DAYS)

工厂函数:
  get_llm()        → ChatAnthropic 或 ChatOpenAI（根据 LLM_PROVIDER）
  get_embeddings() → OpenAIEmbeddings（走独立 EMBEDDING 配置）
  ensure_directories() → 创建 UPLOAD_DIR + TASK_DIR
```

**关键设计**: LLM 和 Embedding 走**不同的 API 端点**（LLM 可走 DeepSeek，Embedding 走独立代理）。

---

### 4.2 schemas — 数据模型

**文件**: `schemas/__init__.py` (198 行)

**枚举类型** (5 个):
| 枚举 | 值 | 用途 |
|---|---|---|
| `RequestType` | plan/upload/qa/review/chat | 请求路由 |
| `AnswerMode` | hint/explain/review/auto | Coach 应答模式 |
| `TaskType` | understand/practice/memorize/correct/review/break | 关卡类型 |
| `TaskStatus` | pending/in_progress/completed/cancelled | 关卡状态 |

**请求模型** (1 个):
- `StudyQuestRequest` — 统一请求体，按 `request_type` 路由，`user_id` 含正则校验防路径遍历

**响应/业务模型** (8 个):
- `QuestTask` — 单个关卡
- `PlannerOutput` — 规划结果
- `MaterialInfo` — 资料信息
- `LibrarianOutput` — 资料处理结果
- `CoachOutput` — 答疑结果
- `SourceCitation` — RAG 引用来源
- `WeakPoint` — 薄弱知识点
- `ReviewReport` — 学习报告
- `StudyQuestResponse` — 统一 API 响应

---

### 4.3 database — 数据库层

#### connection.py (203 行)

**职责**: MySQL 连接池管理 + 自动建库建表

```
Connection Pool: SQLAlchemy engine (pool_size=10, max_overflow=20, pool_recycle=3600)
  ├─ ensure_database()  → CREATE DATABASE IF NOT EXISTS
  ├─ ensure_tables()    → CREATE TABLE IF NOT EXISTS × 7
  └─ get_session()      → 上下文管理器（自动 commit/rollback/close）
```

#### repository.py (253 行)

**职责**: 7 个实体的 CRUD 封装

| 函数 | 操作 | SQL 安全 |
|---|---|---|
| `ensure_user()` | INSERT IF NOT EXISTS | ✅ 参数化 |
| `create_session()` | INSERT | ✅ 参数化 |
| `get_session_info()` | SELECT | ✅ 参数化 |
| `insert_task()` | INSERT | ✅ 参数化 |
| `insert_tasks_batch()` | 循环 INSERT | ✅ 参数化 |
| `update_task_status()` | UPDATE | ✅ 参数化 (动态列名无注入) |
| `get_tasks_by_session()` | SELECT | ✅ 参数化 |
| `get_task()` | SELECT | ✅ 参数化 |
| `insert_qa_log()` | INSERT | ✅ 参数化 |
| `get_recent_qa_logs()` | SELECT | ✅ 参数化 |
| `insert_material()` | INSERT | ✅ 参数化 |
| `insert_material_chunks()` | 循环 INSERT | ✅ 参数化 |
| `get_material()` | SELECT | ✅ 参数化 |
| `get_materials_by_ids()` | SELECT IN | ✅ 参数化 |
| `insert_report()` | INSERT | ✅ 参数化 |

全部使用 SQLAlchemy `text()` + 绑定参数，**无 SQL 注入风险**。

---

### 4.4 graph — LangGraph 编排

#### state.py (148 行)

**GraphState** — LangGraph 的共享状态 TypedDict（30 个字段）：

| 分组 | 字段 | 类型 |
|---|---|---|
| 消息 | `messages` | `Annotated[List[BaseMessage], add_messages]` |
| 会话 | `user_id`, `session_id` | str / Optional[str] |
| 路由 | `request_type`, `next_agent` | str |
| Planner 输入 | `goal_text`, `available_hours`, `constraints` | str/float/dict |
| Coach 输入 | `question_text`, `current_answer_mode` | str |
| Librarian 输入 | `uploaded_files`, `uploaded_urls`, `context` | List[str] |
| Reviewer 输入 | `review_session_id`, `review_task_id`, `review_time_range` | str |
| Agent 输出 | `planner_output`, `coach_output`, `librarian_output`, `reviewer_output` | Optional[dict] |
| 最终输出 | `final_response`, `response_message` | dict/str |
| 错误 | `error` | Optional[str] |

两个工厂函数：
- `create_initial_state()` — 参数化创建初始 State
- `build_state_from_request(req)` — Pydantic 模型 → GraphState

#### workflow.py (377 行)

**7 个节点函数 + 2 个条件路由 + 图构建**：

| 节点 | 函数 | 职责 |
|---|---|---|
| `classifier` | `classifier_node()` | chat 分类改写 / 其他透传 |
| `supervisor` | `supervisor_node()` | 写 next_agent |
| `planner` | `planner_node()` | 调用 PlannerAgent |
| `librarian` | `librarian_node()` | 调用 LibrarianAgent |
| `coach` | `coach_node()` | 调用 CoachAgent |
| `reviewer` | `reviewer_node()` | 调用 ReviewerAgent |
| `format_response` | `format_response_node()` | 组装统一响应 dict |

**条件路由**：
- `route_after_classify(state)` → error? → format_response : supervisor
- `route_by_request_type(state)` → plan→planner / upload→librarian / qa→coach / review→reviewer

**图编译**：
- `compile_graph(with_checkpointer=False)` → 默认无 checkpointer
- `get_graph()` → 全局单例（惰性编译）

---

### 4.5 agents — 智能体层

#### base.py (20 行)

```python
class BaseAgent(ABC):
    def __init__(self, llm=None):
        self.llm = llm or get_llm()    # 从 config 工厂获取
        self.name = self.__class__.__name__
    def log(self, message, level="INFO"):  # 统一日志
```

所有 Agent 继承 `BaseAgent`，获得 `self.llm` 和 `self.log()`。

---

#### classifier.py (111 行)

**ClassifierAgent** — 意图分类器

```
输入: 自然语言消息
输出: {request_type, goal_text, available_hours, question, answer_mode, has_files, review_time_range}

LLM prompt:
  - 系统指令: 四类详细定义 + 关键词 + 规则（无文件不归 upload / 闲聊归 qa）
  - 用户消息: 原始文本
  - JSON 解析: 支持 ```json 代码块提取，解析失败回退 qa
  - request_type 白名单校验（plan/upload/qa/review）
```

**关键规则**：
- "upload" 仅在用户已附加文件时使用，否则降级为 qa
- 闲聊/空白 → qa + 引导性回复
- 失败回退链: JSON 解析 → 代码块提取 → qa 兜底

---

#### planner.py (264 行)

**PlannerAgent** — 学习规划

```
管道流程:
  Step 1: RAG 检索 (Qdrant, top_k=5)
  Step 2: RAG 无结果 → Tavily 联网搜索回退
  Step 3: LLM 生成关卡列表（JSON Schema 约束）
  Step 4: 规则引擎后处理
          ├─ 规则 1: 单关时长 ∈ [20, 50]min，超限拆分
          ├─ 规则 2: 同科目连续 ≤ 90min，插入休息关
          └─ 规则 3: 高难度后插入休息
  Step 5: 双写 (MySQL + 本地文件)
          ├─ create_session() → insert_tasks_batch()
          └─ save_planner_json() + save_task_index() + save_task_file()
```

**LLM prompt 设计**：
- 系统指令: 角色定义 + 5 种 task_type + JSON 格式约束
- 用户 prompt: 目标 + 时长 + 知识上下文 + 约束

**三级降级链路**：
```
RAG 检索 → 命中? → knowledge_context = RAG片段
         → 未命中? → Tavily 搜索 → 成功? → knowledge_context = 搜索结果
                                 → 失败/未配置? → "[不可用]" 标记
```

---

#### librarian.py (185 行)

**LibrarianAgent** — 资料处理（文件 → OCR → 向量化 → 入库）

```
单文件处理管道:
  Step 1: save_uploaded_file()    → 安全校验 + 复制到 UPLOAD_DIR
  Step 2: extract_text_from_file() → OCR/文本提取
  Step 3: classify_material()     → LLM 自动分类（科目/章节/知识点）
  Step 4: chunk_text()            → 文本切块（500 字/块，50 字重叠）
  Step 5: Qdrant upsert           → 每块 embedding + 向量写入
  Step 6: MySQL 双写              → insert_material() + insert_material_chunks()
```

**容错设计**：
- 每个文件独立 try/except，一个失败不影响其他
- 单块 embedding 失败 → `qdrant_indexed = False`，其他块继续
- 返回 `errors[]` 列表供前端展示

**资料召回**：`recall_materials(user_id, knowledge_points)` → 按知识点检索 Qdrant → 去重

---

#### coach.py (203 行)

**CoachAgent** — RAG 增强答疑

```
答疑流程:
  Step 1: 获取关卡上下文 (get_task)
  Step 2: RAG 检索 (top_k=5)
  Step 3: auto_detect 判定模式（关键词 + 关卡类型加权）
  Step 4: 组装 System Prompt（模式指令 + RAG 上下文 + 关卡上下文）
  Step 5: LLM 生成回答
  Step 6: 置信度评估（high≥0.8 / medium≥0.65 / low=无资料）
  Step 7: 写入提问日志 (insert_qa_log)
```

**三种应答模式**：
| 模式 | 策略 | 触发条件 |
|---|---|---|
| `hint` | 只引导不剧透，反问式教学 | 作业/练习题关键词 |
| `explain` | 分步详解 + 举例 + 公式推导 | 概念/定义/原理关键词 |
| `review` | 总结通用方法 + 易错点 + 知识图谱 | 错题/总结关键词 |

**auto_detect 算法**：
```
hint_keywords × 1     + (task_type == practice → +2)
review_keywords × 1   + (task_type == correct → +2, review → +2)
explain_keywords × 1
→ 最高分模式; 同分优先级: review > hint > explain
```

---

#### reviewer.py (305 行)

**ReviewerAgent** — 学习报告 + 薄弱点分析

```
报告生成流程:
  Step 1: 收集数据
          ├─ 关卡完成情况 (get_tasks_by_session / get_task)
          └─ 提问记录 (get_recent_qa_logs, 默认 7 天)
  Step 2: 薄弱点分析
          ├─ 关键词频率统计（Counter, 错题加权 ×1.5）
          ├─ LLM 提炼（≥3 条日志时）
          └─ Top 3 输出
  Step 3: 资料召回 → LibrarianAgent.recall_materials()
  Step 4: LLM 生成明日建议（≤200 字，鼓励性语气）
  Step 5: 双写 (MySQL insert_report + save_report_json)
```

**薄弱点分析双策略**：
- 数据充足（≥3 条日志）→ LLM 从提问记录提炼知识点名称
- 数据不足 → 直接用提问前 30 字作为标识

---

### 4.6 rag — 向量检索

#### qdrant_store.py (132 行)

**QdrantStore** — Qdrant 向量数据库封装

```
特性:
  ├─ 双模式连接: URL (云服务) / Host+Port (本地)
  ├─ 自动建库: collection 不存在时创建（1536 维 COSINE）
  ├─ Payload 索引: user_id 关键词索引（filter 查询必需）
  ├─ upsert_points(): 批量写入向量 + payload
  ├─ search(): 语义搜索 + user_id 过滤 + subject 可选过滤 + score_threshold
  ├─ delete_by_user(): 删除用户全部向量
  ├─ delete_points(): 删除指定向量
  └─ count(): 获取总向量数
```

全局单例 `get_qdrant_store()` 惰性初始化。

#### retriever.py (108 行)

**RAGRetriever** — 检索器

```
完整链路:
  query_text → embed_query() → QdrantStore.search() → 格式化

方法:
  ├─ embed_query()           → 文本 → 1536 维向量
  ├─ retrieve()              → 返回 [{content, filename, subject, similarity, ...}]
  ├─ retrieve_as_documents() → 返回 LangChain Document 列表
  └─ format_retrieved_context() → 格式化为 prompt 可用的上下文字符串
```

全局单例 `get_retriever()` 惰性初始化。

---

### 4.7 tools — 工具集

#### ocr.py (211 行)

**文件类型路由器** — `extract_text_from_file(file_path) → (file_type, text)`

| 扩展名 | 处理器 | 底层库 |
|---|---|---|
| .jpg/.jpeg/.png/.gif/.bmp/.webp | `ocr_image()` | GPT-4o Vision API (base64) |
| .pdf | `extract_pdf_text()` | PyPDF2 (文字型) |
| .docx/.doc | `extract_docx_text()` | python-docx |
| .pptx/.ppt | `extract_pptx_text()` | python-pptx |
| .txt/.md/.markdown | 直接读取 | open() |

**扫描型 PDF 处理**: 文字 < 50 字符 → 返回 `"pdf_scanned"` 类型标记（MVP 未进一步处理）

**OCR prompt**：5 条指令（保留段落结构、数学公式 LaTeX、表格 Markdown、模糊标注、禁止开场白）

**classify_material()**：取文本前 500 字 → LLM 分类为 `{subject, chapter, knowledge_point}` JSON

**chunk_text()**：自然段落分割 → 超长段按句子切分 → 500 字/块 + 50 字重叠

#### rag_search.py (36 行)

**RAGSearchTool** — LangChain Tool 封装，供 Agent 调用

```
name: "rag_search"
input: {query, user_id, top_k?, subject?}
output: 格式化的上下文字符串
```

#### web_search.py (59 行)

**WebSearchTool** — Tavily 联网搜索 LangChain Tool

```
name: "web_search"
input: {query, max_results?, include_raw_content?}
output: "[搜索结果 N] title\nURL\ncontent"
失败模式: "[WebSearch 不可用]" / "[WebSearch 失败] ..."
```

---

### 4.8 utils — 工具函数

#### file_storage.py (165 行)

**本地文件存储 + 安全校验**

| 函数 | 功能 | 安全措施 |
|---|---|---|
| `save_uploaded_file(src, user_id)` | 复制文件到上传目录 | 四层校验（详见第 9 章） |
| `save_planner_json(user_id, sid, data)` | 保存规划 JSON | user_id 校验 |
| `save_report_json(user_id, rid, data)` | 保存报告 JSON | user_id 校验 |
| `save_task_index(tasks)` | 写 `_index.jsonl` | 无外部输入 |
| `save_task_file(task)` | 写 `T*.md` (YAML frontmatter) | 无外部输入 |

**安全校验函数**（内部）：
- `_validate_user_id()` — 正则 `^[a-zA-Z0-9_-]{1,64}$`
- `_validate_path_within()` — resolve() + relative_to() 防路径遍历
- `_validate_source_file()` — 存在性 + 类型 + 大小（≤50MB）
- `_validate_extension()` — 14 种白名单扩展名

#### logger.py (46 行)

**结构化日志**：控制台（INFO+）+ 文件（DEBUG+，JSON 格式，按日滚动）

---

### 4.9 middleware — 已废弃路由

**router.py** (179 行) — `[DEPRECATED]`

旧的 `RequestRouter` 类已被 `graph/workflow.py` (LangGraph) 完全替代。文件保留用于回退对比。所有 `app.py` / `main.py` 的 import 已移除。

---

### 4.10 app.py / main.py — 双入口

#### app.py (155 行)

**Flask REST API**

```
端点:
  GET  /api/health    → Qdrant 状态 + 向量数
  POST /api/studyquest → 统一入口 → LangGraph 工作流

生命周期:
  before_request → 请求日志
  studyquest()   → JSON 解析 → Pydantic 校验 → build_state_from_request()
                   → graph.invoke() → 组装响应 JSON
  init()         → ensure_directories() + ensure_database() + ensure_tables()
                   + Qdrant 预热 + LangGraph 编译
```

错误处理：
- 请求体为空 → 400
- 业务异常 → 路径相关脱敏 → 400
- 未知异常 → 500

#### main.py (259 行)

**CLI 交互入口**

```
python main.py <command> --user <user_id> [options]

命令:
  plan    --goal "..." --hours 3.0 [--constraints '{}']
  upload  --files "./a.pdf,./b.jpg"
  qa      --question "..." [--mode explain] [--task-id ...]
  review  --session sess_xxx [--time-range 7d]
  chat    --message "自然语言输入"

选项:
  --json-output  → JSON 格式输出（默认 Rich 美化输出）
```

所有命令走统一的 `_invoke_graph(req)` → LangGraph 工作流。

#### test_env.py (157 行)

**6 项连通性测试**：Anthropic LLM / Embedding / GPT-4o Chat / Qdrant / MySQL / Tavily

Rich Table 美化输出，PASS/FAIL/SKIP 三态。

---

## 5. 数据流

### 5.1 Plan 数据流

```
用户输入 (goal_text, available_hours)
  → PlannerAgent.plan()
    → RAGRetriever.retrieve(goal_text, user_id)
      → embeddings.embed_query()
      → QdrantStore.search()
    → [RAG 为空 → WebSearchTool._run()]
    → PlannerAgent._generate_tasks()
      → llm.invoke(system_prompt + user_prompt)
    → PlannerAgent._apply_rules() (时长约束 + 休息插入)
    → create_session() → MySQL sessions 表
    → insert_tasks_batch() → MySQL tasks 表
    → save_planner_json() → 本地 JSON
    → save_task_index() → _index.jsonl
    → save_task_file() → T*.md × N
  → 返回 PlannerOutput
```

### 5.2 Upload 数据流

```
用户输入 (file_paths[])
  → LibrarianAgent.process_files()
    → for each file:
      → save_uploaded_file()
        → _validate_user_id()
        → _validate_source_file() (存在/类型/大小)
        → _validate_extension() (14 种白名单)
        → shutil.copy2() → UPLOAD_DIR/user_id/
      → extract_text_from_file()
        → .jpg/.png → ocr_image() → GPT-4o Vision (base64)
        → .pdf → PyPDF2
        → .docx → python-docx
        → .pptx → python-pptx
        → .txt/.md → open()
      → classify_material() → LLM → {subject, chapter, knowledge_point}
      → chunk_text() → 段落分割 → 500 字/块
      → for each chunk:
        → retriever.embed_query(chunk)
        → QdrantStore.upsert_points()
      → insert_material() → MySQL materials 表
      → insert_material_chunks() → MySQL material_chunks 表
  → 返回 LibrarianOutput
```

### 5.3 QA 数据流

```
用户输入 (question, answer_mode, active_task_id)
  → CoachAgent.answer()
    → get_task(active_task_id) → 关卡上下文
    → RAGRetriever.retrieve(question, user_id)
      → embed_query() → QdrantStore.search()
    → _auto_detect_mode() (关键词 + task_type 加权)
    → System Prompt 组装 (模式指令 + RAG 上下文 + 关卡上下文)
    → llm.invoke()
    → _assess_confidence() (平均相似度 → high/medium/low)
    → insert_qa_log() → MySQL qa_logs 表
  → 返回 CoachOutput
```

### 5.4 Review 数据流

```
用户输入 (review_session_id / review_task_id)
  → ReviewerAgent.review()
    → _collect_completion_data() (从 MySQL tasks/sessions)
    → _collect_qa_logs() → get_recent_qa_logs()
    → _analyze_weak_points()
      → Counter 关键词统计 + LLM 提炼
    → LibrarianAgent.recall_materials()
      → Qdrant 按知识点检索 + 去重
    → _generate_suggestion() → LLM 生成明日建议
    → insert_report() → MySQL reports 表
    → save_report_json() → 本地 JSON
  → 返回 ReviewReport
```

### 5.5 Chat 数据流

```
用户输入 (goal_text 自由文本)
  → classifier_node(state)
    → ClassifierAgent.classify(message)
      → llm.invoke(CLASSIFIER_SYSTEM_PROMPT + message)
      → JSON 解析 + request_type 白名单校验
    → 改写 state.request_type → plan/qa/review
    → [若 upload 无文件 → 降级为 qa]
  → supervisor_node → route_by_request_type
  → 对应 Agent 节点（走上述 5.1-5.4 之一）
```

---

## 6. 数据库 Schema

### ER 图（7 表）

```
users (1) ──< sessions (N)
users (1) ──< tasks (N)
users (1) ──< qa_logs (N)
users (1) ──< materials (N)
users (1) ──< reports (N)
sessions (1) ──< tasks (N)
tasks (1) ──< qa_logs (N)
materials (1) ──< material_chunks (N)
```

### 表详情

| 表名 | 主键 | 核心字段 | 索引 | 外键 |
|---|---|---|---|---|
| `users` | id VARCHAR(64) | username, password_hash, avatar | idx_username | — |
| `sessions` | id VARCHAR(64) | user_id, goal_text, date, total_minutes, status, planner_json | idx_user_date | users(id) CASCADE |
| `tasks` | id VARCHAR(64) | user_id, session_id, parent_id, subject, title, description, task_type, estimated_minutes, actual_minutes, status, priority, sort_order, material_ids (JSON) | idx_user, idx_session, idx_status | users(id) CASCADE, sessions(id) SET NULL |
| `qa_logs` | id VARCHAR(64) | user_id, task_id, question, answer, answer_mode, source_docs (JSON), confidence | idx_user, idx_task, idx_created | users(id) CASCADE, tasks(id) SET NULL |
| `materials` | id VARCHAR(64) | user_id, filename, file_type, file_path, subject, chapter, knowledge_point, ocr_text (LONGTEXT), chunk_count, qdrant_indexed, uploaded_at | idx_user, idx_subject, idx_knowledge | users(id) CASCADE |
| `material_chunks` | id VARCHAR(64) | material_id, chunk_index, content, qdrant_point_id, embedding_model | idx_material | materials(id) CASCADE |
| `reports` | id VARCHAR(64) | user_id, session_id, task_id, completion (JSON), weak_points (JSON), recommended_material_ids (JSON), next_tasks_suggestion | idx_user, idx_session, idx_task | users(id) CASCADE, sessions(id) SET NULL, tasks(id) SET NULL |

---

## 7. 外部服务依赖

| 服务 | 用途 | 配置环境变量 | 必需 |
|---|---|---|---|
| **Anthropic / DeepSeek API** | LLM 推理（Planner/Coach/Reviewer/Classifier） | `ANTHROPIC_API_KEY`, `ANTHROPIC_BASE_URL`, `LLM_PROVIDER` | ✅ |
| **OpenAI 兼容端点 (Doubao)** | 多模态 OCR（GPT-4o Vision） | `OPENAI_API_KEY`, `OPENAI_BASE_URL` | ✅ (上传图片时) |
| **OpenAI 兼容端点 (Jeniya)** | Text Embedding (text-embedding-3-small) | `EMBEDDING_API_KEY`, `EMBEDDING_BASE_URL` | ✅ |
| **Qdrant Cloud** | 向量存储 + 语义检索 | `QDRANT_URL`, `QDRANT_API_KEY` | ✅ |
| **MySQL** | 结构化数据持久化 | `MYSQL_HOST/PORT/USER/PASSWORD/DATABASE` | ✅ |
| **Tavily** | 联网搜索回退（RAG 无结果时） | `TAVILY_API_KEY` | 🟡 可选 |

---

## 8. API 接口

详见 `API接口文档.md`，此处仅列概要。

### 端点

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/health` | 健康检查（Qdrant 状态 + 向量数） |
| `POST` | `/api/studyquest` | 统一业务入口 |

### 统一请求格式

```json
{
  "request_type": "plan|upload|qa|review|chat",
  "user_id": "user_001",
  // ... 按 request_type 提供对应字段
}
```

### 统一响应格式

```json
{
  "success": true,
  "request_type": "plan",
  "data": { /* 业务数据 */ },
  "message": "学习关卡规划完成",
  "error": null
}
```

### request_type  → Agent 映射

| request_type | Agent | data 内容 |
|---|---|---|
| `plan` | Planner | `{session_id, tasks[], total_estimated_minutes, knowledge_summary, web_search_used}` |
| `upload` | Librarian | `{materials[], total_chunks, errors[]}` |
| `qa` | Coach | `{answer, answer_mode, sources[], confidence, qa_log_id}` |
| `review` | Reviewer | `{report_id, tasks_completed, completion_rate, weak_points[], next_tasks_suggestion}` |
| `chat` | Classifier → 上述之一 | 同分类后的 request_type |

---

## 9. 安全分析

### 已实施的安全措施

| 措施 | 位置 | 说明 |
|---|---|---|
| **user_id 正则校验** | `schemas/__init__.py:47` + `utils/file_storage.py:17` | `^[a-zA-Z0-9_-]{1,64}$`，双重拦截 |
| **路径遍历防护** | `utils/file_storage.py:22` | `Path.resolve()` + `relative_to()` 边界检查 |
| **文件大小限制** | `utils/file_storage.py:37` | 默认 50MB，环境变量 `MAX_FILE_SIZE_MB` 可控 |
| **扩展名白名单** | `utils/file_storage.py:45` | 14 种文档/图片类型，非白即拒 |
| **文件名长度限制** | `utils/file_storage.py:73` | 最长 255 字符 |
| **SQL 注入防护** | 全部 `database/repository.py` | 100% 参数化查询 |
| **错误信息脱敏** | `app.py:103-109` | 路径相关异常返回通用消息 |
| **源文件存在性检查** | `utils/file_storage.py:34` | `resolve(strict=True)` |

### 已知风险

| 风险 | 级别 | 说明 |
|---|---|---|
| 无用户认证 | 🟡 MEDIUM | `user_id` 是纯字符串参数，可被冒充 |
| 无速率限制 | 🟡 MEDIUM | 上传/API 端点无限流 |
| 扩展名可伪造 | 🟡 MEDIUM | 仅检查扩展名而非 magic bytes |
| `file_urls` 未实现 | 🟡 MEDIUM | Schema 接受但 Librarian 不处理 |
| 嵌入失败无回滚 | 🔵 LOW | MySQL 写入后若 Qdrant 失败，孤记录残留 |
| 大文件 OOM | 🔵 LOW | 整个文件加载到内存做 OCR/切块 |

---

## 10. 配置参考

### 环境变量完整列表

| 变量 | 默认值 | 说明 |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | LLM API Key (必填) |
| `ANTHROPIC_MODEL` | claude-sonnet-4-5-20250929 | LLM 模型名 |
| `LLM_PROVIDER` | anthropic | anthropic 或 openai |
| `ANTHROPIC_BASE_URL` | — | LLM API 端点（DeepSeek 等兼容代理） |
| `OPENAI_API_KEY` | — | OCR 视觉模型 Key |
| `OPENAI_BASE_URL` | — | OCR 端点 |
| `EMBEDDING_API_KEY` | OPENAI_API_KEY | Embedding Key |
| `EMBEDDING_BASE_URL` | OPENAI_BASE_URL | Embedding 端点 |
| `EMBEDDING_MODEL` | text-embedding-3-small | Embedding 模型 |
| `TAVILY_API_KEY` | — | Tavily 搜索 Key |
| `QDRANT_URL` | — | Qdrant 云服务 URL |
| `QDRANT_HOST` | localhost | Qdrant 主机 |
| `QDRANT_PORT` | 6333 | Qdrant 端口 |
| `QDRANT_COLLECTION` | studyquest_knowledge | Collection 名称 |
| `MYSQL_HOST/PORT/USER/PASSWORD/DATABASE` | localhost/3306/root/—/studyquest | MySQL 连接 |
| `FLASK_HOST/PORT/DEBUG` | 0.0.0.0/5000/false | Flask 配置 |
| `UPLOAD_DIR` | ./workspace/uploads | 上传文件存储 |
| `TASK_DIR` | ./workspace/.agent/tasks | 任务文件存储 |
| `MAX_FILE_SIZE_MB` | 50 | 上传文件大小限制 |
| `RAG_TOP_K` | 5 | RAG 检索返回数 |
| `RAG_CHUNK_SIZE` | 500 | 文本分块大小 |
| `RAG_CHUNK_OVERLAP` | 50 | 分块重叠大小 |
| `RAG_SIMILARITY_THRESHOLD` | 0.65 | 向量相似度阈值 |
| `TASK_MIN_MINUTES` | 20 | 单关最短时长 |
| `TASK_MAX_MINUTES` | 50 | 单关最长时长 |
| `SAME_SUBJECT_MAX_MINUTES` | 90 | 同科目连续上限 |
| `BREAK_MINUTES` | 10 | 休息时长 |
| `WEAK_POINT_DAYS` | 7 | 薄弱点追溯天数 |
| `WEAK_POINT_TOP_N` | 3 | 薄弱点 Top N |

---

## 附录 A：代码统计

| 指标 | 数值 |
|---|---|
| Python 源文件 | 22 个 |
| 总代码行数 | ~3,200 行 |
| Agent 数量 | 5 个（Classifier + Planner + Librarian + Coach + Reviewer） |
| LangGraph 节点 | 7 个 |
| 数据库表 | 7 张 |
| Pydantic 模型 | 12 个 |
| 文件处理类型 | 14 种扩展名 |
| 外部依赖 | 25 个 PyPI 包 |

## 附录 B：启动命令

```bash
# 安装依赖
pip install -r requirements.txt

# 配置环境
cp .env.example .env
# 编辑 .env 填入 API Key

# 测试连通性
python test_env.py

# 启动 Flask API
python app.py

# 或 CLI 模式
python main.py plan --user test --goal "复习数学函数" --hours 2
python main.py upload --user test --files "./notes.pdf,./photo.jpg"
python main.py qa --user test --question "二次函数单调性怎么判断？"
python main.py chat --user test --message "帮我规划3小时复习英语"
```
