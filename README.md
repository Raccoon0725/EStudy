# EStudy：基于 AIGC 的多智能体闯关式学习助手

基于 AIGC 的闯关式学习助手：AI 将学习目标拆解为关卡，并在执行过程中提供专注监督、多模态答疑和复盘推荐。本项目专为中学生、大学生及备考人群设计，通过闭环的“规划-执行-答疑-复盘”流程，解决学习规划难、易分心、资料杂乱及缺乏针对性反馈的痛点。

---

## ✨ 核心特性 (Features)

- **🗺️ AI 任务规划**：输入学习目标，AI 自动将其拆解为包含合理时长（20-50分钟）、休息机制和难度排序的可执行闯关地图。
    
- **⏳ 闯关式专注模式**：结合番茄钟机制进行软约束防打扰，关卡绑定计时，离开即记录中断，提升执行力。
    
- **📚 多模态资料归类**：支持 PDF、图片（OCR）、Word 等多种格式导入，利用 AI 自动提取文本并按“科目-章节-知识点”结构化归类建库。
    
- **💬 RAG 场景化智能答疑**：在专注学习时，结合当前关卡上下文与用户专属向量知识库，提供“提示”、“讲解”或“复盘”三种模式的精准辅导，并标注资料来源。
    
- **📊 智能复盘与推荐**：基于学习日志与历史提问，生成单关复盘报告与薄弱点（Top 3）追踪，自动召回相关资料生成下一轮学习清单。
    

## 🤖 多智能体架构 (Multi-Agent Architecture)

本项目放弃了臃肿的单体大模型方案，采用 **LangGraph** 编排了由 1 个调度中心和 4 个专职 Agent 组成的协作网络，通过共享 `StateGraph` 实现高效运转：

- **Supervisor (调度智能体)**：作为中枢大脑，分析用户意图，将自然语言请求精准路由至对应的执行 Agent，并支持复合意图的串行/并行调度。
    
- **Planner (规划智能体)**：结合规则引擎与 LLM，将大目标拆解为带类型标签的子关卡，并注入记忆系统（MEMORY）中的历史薄弱点。
    
- **Coach (答疑智能体)**：执行“观察-思考-行动”循环，利用 Qdrant 检索多模态资料块，提供带引用溯源的 RAG 增强辅导。
    
- **Librarian (资料智能体)**：处理文件解析与 PaddleOCR 识别，完成文本清洗、大模型结构化分类、分块及 Embedding 向量化入库。
    
- **Reviewer (复盘智能体)**：分析学习日志与频繁提问的知识点，更新用户的长期学习画像（Persistent Memory），并召回弱项资料。
    

## 🛠️ 技术栈 (Tech Stack)

### 前端与客户端 (Frontend & Client)

- **核心框架**：Vue3 + Vant UI
    
- **移动端打包**：Capacitor (直接将 Vue3 封装为调用原生 API 的 Android APK)
    

### 后端服务 (Backend & Gateway)

- **核心框架**：Flask API (提供 HTTP REST + SSE 流式响应)
    
- **关系型数据库**：MySQL (存储用户、任务、会话记录及系统报告)
    

### 人工智能与数据检索 (AI & Search)

- **大语言模型**：Anthropic Claude API (用于任务规划、答疑推理与报告生成)
    
- **智能体编排**：LangGraph (状态图与多智能体协调)
    
- **向量数据库**：Qdrant (Docker 部署，支持 Payload 过滤与全文混合检索)
    
- **Embedding 模型**：bge-small-zh / text-embedding-3-small
    
- **多模态 OCR**：PaddleOCR (支持中文与手写体高精度识别)
    

## 🚀 快速上手 (Getting Started)

### 1. 环境依赖 (Prerequisites)

请确保本地已安装 Python 3.10+、Node.js 18+ 以及 Docker（用于运行向量数据库）。

### 2. 后端部署 (Backend Setup)

```

```

### 3. 前端部署 (Frontend Setup)


```

```

## 📂 目录结构 (Project Structure)

Plaintext

```
StudyQuest/
├── backend/                  # Flask 后端服务
│   ├── agents/               # LangGraph 核心逻辑
│   │   ├── supervisor.py     # 调度节点
│   │   ├── planner.py        # 规划智能体
│   │   ├── coach.py          # 答疑智能体
│   │   ├── librarian.py      # 资料智能体
│   │   └── reviewer.py       # 复盘智能体
│   ├── core/                 # Qdrant 检索与 MySQL 模型
│   ├── routes/               # API 路由网关
│   └── utils/                # 多模态解析与 OCR 工具
├── frontend/                 # Vue3 前端应用
│   ├── src/
│   │   ├── views/            # 关卡、专注计时、答疑、报告页面
│   │   └── components/       # UI 组件库
│   └── capacitor.config.ts   # 移动端打包配置
└── docs/                     # 架构图与 API 文档
```