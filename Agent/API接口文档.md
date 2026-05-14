# StudyQuest API 接口文档（前端对接）

> Base URL: `http://<host>:5000`
> Content-Type: `application/json`
> 更新日期：2026-05-13

---

## 1. 通用约定

### 1.1 统一响应格式

所有接口返回格式一致：

```json
{
  "success": true,
  "request_type": "plan",
  "data": { /* 具体业务的返回数据 */ },
  "message": "学习关卡规划完成",
  "error": null
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `success` | bool | `true` 成功，`false` 失败 |
| `request_type` | string | 这次请求最终处理类型（plan / upload / qa / review / chat / unknown） |
| `data` | object / null | 成功时放业务数据，失败时为 null |
| `message` | string | 人类可读的消息（成功时描述结果，失败时包含错误原因） |
| `error` | string / null | 失败时的详细错误信息 |

### 1.2 前端统一判断

```javascript
if (response.success) {
  // 根据 response.request_type 渲染对应 UI
  switch (response.request_type) {
    case "plan": renderPlan(response.data); break;
    case "qa": renderAnswer(response.data); break;
    case "upload": renderMaterials(response.data); break;
    case "review": renderReport(response.data); break;
  }
} else {
  // 展示 response.message 或 response.error
  showError(response.message || response.error);
}
```

**注意事项**：
- `request_type` 在响应中反映的是**最终处理类型**（如 chat 请求被分类后，返回的是 `"plan"` 而非 `"chat"`）
- `message` 字段在错误场景下也有值（不再是空字符串）
- `data` 为 null 时不要尝试渲染

### 1.3 HTTP 状态码

| 状态码 | 场景 |
|--------|------|
| 200 | 业务处理成功（Agent 完成工作） |
| 400 | 请求体为空 |
| 500 | 业务处理失败（含 Agent 异常）或系统级异常 |

---

## 2. 统一入口 `/api/studyquest`

**POST** `/api/studyquest`

所有业务共用一个端点，靠 `request_type` 字段区分逻辑。后端通过 LangGraph 工作流自动路由到对应 Agent。

### 通用请求体字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|:---:|------|
| `request_type` | string | ✓ | `plan` / `upload` / `qa` / `review` / `chat` |
| `user_id` | string | ✓ | 用户唯一标识 |
| `session_id` | string | | 学习会话 ID |
| `goal_text` | string | | 学习目标描述 |
| `available_hours` | float | | 可用时间（小时），默认 2.0 |
| `constraints` | object | | 额外约束，预留字段 |
| `question` | string | | 提问内容 |
| `answer_mode` | string | | 应答模式：`hint` / `explain` / `review` / `auto`（默认 `auto`） |
| `active_task_id` | string | | 当前活跃关卡 ID |
| `file_paths` | string[] | | 上传的服务端本地文件路径列表 |
| `file_urls` | string[] | | 远程文件 URL 列表 |
| `review_task_id` | string | | 要复盘的任务 ID |
| `review_session_id` | string | | 要复盘的会话 ID |
| `review_time_range` | string | | 复盘时间范围，默认 `"7d"` |

---

### 2.1 `plan` — 学习规划

**请求示例**：

```json
{
  "request_type": "plan",
  "user_id": "user_001",
  "goal_text": "3小时复习高等数学（下），重点多元函数微积分和无穷级数",
  "available_hours": 3.0,
  "constraints": {}
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|:---:|------|
| `request_type` | string | ✓ | 固定 `"plan"` |
| `user_id` | string | ✓ | 用户唯一标识 |
| `goal_text` | string | ✓ | 学习目标描述（自然语言） |
| `available_hours` | float | | 可用时间（小时），默认 2.0 |
| `constraints` | object | | 额外约束，默认 `{}` |

**data 字段说明**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `session_id` | string | 本次规划创建的学习会话 ID |
| `tasks` | array | 关卡列表 |
| `tasks[].index` | int | 序号 |
| `tasks[].subject` | string | 科目名称 |
| `tasks[].title` | string | 关卡标题 |
| `tasks[].description` | string | 这一关具体要做什么 |
| `tasks[].task_type` | string | `understand` / `practice` / `memorize` / `correct` / `review` / `break` |
| `tasks[].estimated_minutes` | int | 建议时长（分钟） |
| `tasks[].material_ids` | string[] | 关联资料 ID 列表 |
| `tasks[].priority` | int | 优先级 1-5，5 最高 |
| `tasks[].status` | string | `pending` / `in_progress` / `completed` / `cancelled` |
| `total_estimated_minutes` | int | 所有关卡预估总时长 |
| `knowledge_summary` | string | RAG 或联网搜索得到的知识背景 |
| `web_search_used` | bool | 是否触发了联网搜索回退 |
| `created_at` | string | 创建时间 ISO 8601 |

**成功响应**：

```json
{
  "success": true,
  "request_type": "plan",
  "data": {
    "session_id": "sess_a1b2c3d4e5f6",
    "tasks": [
      {
        "index": 0,
        "subject": "高等数学",
        "title": "多元函数偏导数回顾",
        "description": "回顾二元函数偏导数的定义、计算方法和几何意义",
        "task_type": "understand",
        "estimated_minutes": 30,
        "material_ids": ["mat_abc123"],
        "priority": 3,
        "status": "pending"
      },
      {
        "index": 1,
        "subject": "高等数学",
        "title": "链式法则练习题",
        "description": "完成5道多元复合函数求导练习题",
        "task_type": "practice",
        "estimated_minutes": 40,
        "material_ids": [],
        "priority": 4,
        "status": "pending"
      },
      {
        "index": 2,
        "subject": "休息",
        "title": "休息一下",
        "description": "站起来走动，喝水放松眼睛",
        "task_type": "break",
        "estimated_minutes": 10,
        "material_ids": [],
        "priority": 0,
        "status": "pending"
      }
    ],
    "total_estimated_minutes": 80,
    "knowledge_summary": "（RAG检索到的相关知识摘要，或联网搜索结果）",
    "web_search_used": false,
    "created_at": "2026-05-13T14:30:00"
  },
  "message": "学习关卡规划完成",
  "error": null
}
```

**失败响应**：

```json
{
  "success": false,
  "request_type": "plan",
  "data": null,
  "message": "[Planner] LLM 返回格式异常，无法解析关卡列表",
  "error": "[Planner] LLM 返回格式异常，无法解析关卡列表"
}
```

---

### 2.2 `qa` — AI 答疑

**请求示例**：

```json
{
  "request_type": "qa",
  "user_id": "user_001",
  "question": "多元函数求偏导数的链式法则怎么用？请结合例子说明",
  "answer_mode": "explain",
  "active_task_id": "task_a1b2c3d4e5f6"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|:---:|------|
| `request_type` | string | ✓ | 固定 `"qa"` |
| `user_id` | string | ✓ | 用户唯一标识 |
| `question` | string | ✓ | 提问内容 |
| `answer_mode` | string | | `hint` / `explain` / `review` / `auto`（默认 `auto`，后端自动判定） |
| `active_task_id` | string | | 当前活跃关卡 ID，用于获取关卡上下文 + 参与 auto 模式判定 |

**`answer_mode` 说明**：

| 值 | 用途 |
|----|------|
| `hint` | 提示模式 — 只给思路不给答案，回复以问句引导 |
| `explain` | 讲解模式 — 分步详细解释，有举例和推导 |
| `review` | 复盘模式 — 总结方法+易错点，给知识图谱 |
| `auto` | **后端自动判定** — 根据问题关键词 + 当前关卡 task_type 加权计分 |

**auto 模式判定规则（后端实现，前端无需关心）**：

```
问题关键词匹配:
  提示类: "提示/思路/怎么做/不会做/这题/作业"     → hint_score +1 each
  复盘类: "错题/总结/归纳/回顾/为什么错了"       → review_score +1 each
  讲解类: "是什么/为什么/解释/概念/定义/原理"     → explain_score +1 each

关卡类型加权:
  task_type = practice  → hint_score +2
  task_type = correct   → review_score +2
  task_type = review    → review_score +2

取最高分 → 对应模式；同分优先级: review > hint > explain
```

**data 字段说明**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `answer` | string | LLM 生成的回答（支持 Markdown） |
| `answer_mode` | string | 实际使用的应答模式 |
| `sources` | array | RAG 引用的资料来源 |
| `sources[].filename` | string | 来源文件名 |
| `sources[].chunk_index` | int | 文本块序号 |
| `sources[].similarity` | float | 语义相似度 (0-1) |
| `sources[].preview` | string | 引用内容预览（前 150 字） |
| `confidence` | string | 置信度：`high`(≥0.8) / `medium`(≥0.65) / `low`(无资料匹配) |
| `qa_log_id` | string | 提问日志 ID，可用于后续复盘关联 |

**成功响应**：

```json
{
  "success": true,
  "request_type": "qa",
  "data": {
    "answer": "## 多元函数链式法则详解\n\n### 1. 基本形式\n设 z = f(u, v)，其中 u = u(x,y)，v = v(x,y)...\n\n（完整回答内容，支持 Markdown 格式）",
    "answer_mode": "explain",
    "sources": [
      {
        "filename": "工数期末考试试题.pdf",
        "chunk_index": 3,
        "similarity": 0.87,
        "preview": "求函数 z = e^(xy) · sin(x+y) 的全微分..."
      }
    ],
    "confidence": "high",
    "qa_log_id": "qa_x1y2z3w4"
  },
  "message": "答疑完成",
  "error": null
}
```

**失败响应**：

```json
{
  "success": false,
  "request_type": "qa",
  "data": null,
  "message": "[Coach] Anthropic API 请求超时，请稍后重试",
  "error": "[Coach] Anthropic API 请求超时，请稍后重试"
}
```

---

### 2.3 `upload` — 上传资料

**请求示例**：

```json
{
  "request_type": "upload",
  "user_id": "user_001",
  "file_paths": [
    "/var/uploads/数学笔记.pdf",
    "/var/uploads/错题照片.jpg"
  ],
  "context": "knowledge"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|:---:|------|
| `request_type` | string | ✓ | 固定 `"upload"` |
| `user_id` | string | ✓ | 用户唯一标识 |
| `file_paths` | string[] | ✓ | 服务端本地文件路径（前端先上传文件到后端存储后获得的路径） |
| `file_urls` | string[] | | 远程文件 URL（MVP 暂未实现下载逻辑） |
| `context` | string | | 上传用户备注：|

**data 字段说明**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `materials` | array | 每个文件一条处理结果 |
| `materials[].material_id` | string | 资料唯一 ID，后续 plan/qa/review 会用到 |
| `materials[].filename` | string | 原始文件名 |
| `materials[].file_type` | string | `pdf` / `image` / `word` / `ppt` / `text` |
| `materials[].subject` | string | AI 自动分类的科目 |
| `materials[].chapter` | string | AI 自动分类的章节 |
| `materials[].knowledge_point` | string | AI 自动分类的知识点 |
| `materials[].ocr_text_preview` | string | 提取文本的前 200 字 |
| `materials[].chunk_count` | int | 切块数量 |
| `materials[].qdrant_indexed` | bool | 是否成功写入向量库 |
| `materials[].uploaded_at` | string | 上传时间 ISO 8601 |
| `total_chunks` | int | 本次上传的总文本块数 |
| `errors` | string[] | 处理失败的文件列表（含错误原因） |

**成功响应（全部成功）**：

```json
{
  "success": true,
  "request_type": "upload",
  "data": {
    "materials": [
      {
        "material_id": "mat_a1b2c3d4",
        "filename": "数学笔记.pdf",
        "file_type": "pdf",
        "subject": "高等数学",
        "chapter": "多元函数微积分",
        "knowledge_point": "偏导数与链式法则",
        "ocr_text_preview": "第三章 多元函数微分学\n3.1 偏导数的定义...",
        "chunk_count": 12,
        "qdrant_indexed": true,
        "uploaded_at": "2026-05-13T15:00:00"
      }
    ],
    "total_chunks": 12,
    "errors": []
  },
  "message": "资料处理完成",
  "error": null
}
```

**部分失败响应**：

```json
{
  "success": true,
  "request_type": "upload",
  "data": {
    "materials": [
      {
        "material_id": "mat_a1b2c3d4",
        "filename": "数学笔记.pdf",
        "file_type": "pdf",
        "subject": "高等数学",
        "chapter": "多元函数微积分",
        "knowledge_point": "偏导数与链式法则",
        "ocr_text_preview": "第三章 多元函数微分学...",
        "chunk_count": 12,
        "qdrant_indexed": true,
        "uploaded_at": "2026-05-13T15:00:00"
      }
    ],
    "total_chunks": 12,
    "errors": ["错题照片.jpg: 图片 OCR 识别失败 — 图片模糊无法提取文字"]
  },
  "message": "资料处理完成",
  "error": null
}
```

> **注意**：部分文件失败时 `success` 仍为 `true`（成功的文件已入库），前端检查 `data.errors` 数组来判断哪些文件失败。

**完全失败响应**：

```json
{
  "success": false,
  "request_type": "upload",
  "data": null,
  "message": "[Librarian] 不支持的文件类型：video.mp4（仅支持 pdf / image / word / ppt / text）",
  "error": "[Librarian] 不支持的文件类型：video.mp4（仅支持 pdf / image / word / ppt / text）"
}
```

---

### 2.4 `review` — 学习报告

**请求示例**：

```json
{
  "request_type": "review",
  "user_id": "user_001",
  "review_session_id": "sess_a1b2c3d4e5f6",
  "review_time_range": "7d"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|:---:|------|
| `request_type` | string | ✓ | 固定 `"review"` |
| `user_id` | string | ✓ | 用户唯一标识 |
| `review_session_id` | string | | 复盘整个会话（和 review_task_id 二选一） |
| `review_task_id` | string | | 复盘单个关卡（和 review_session_id 二选一） |
| `review_time_range` | string | | 薄弱点追溯天数，默认 `"7d"` |

**data 字段说明**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `report_id` | string | 报告唯一 ID |
| `user_id` | string | 用户 ID |
| `session_id` | string / null | 复盘的学习会话 |
| `task_id` | string / null | 复盘的具体关卡 |
| `tasks_completed` | int | 已完成关卡数 |
| `tasks_total` | int | 总关卡数 |
| `total_minutes` | int | 实际学习总时长（分钟） |
| `interruption_count` | int | 中断次数 |
| `completion_rate` | float | 完成率 (0.0 ~ 1.0) |
| `weak_points` | array | Top 3 薄弱知识点 |
| `weak_points[].knowledge_point` | string | 知识点名称 |
| `weak_points[].frequency` | int | 该知识点被提问/标记的次数 |
| `weak_points[].weight` | float | 加权分数（越大越薄弱） |
| `recommended_material_ids` | string[] | 推荐复习的资料 ID 列表 |
| `next_tasks_suggestion` | string | LLM 生成的明日学习建议 |
| `created_at` | string | 报告生成时间 ISO 8601 |

**成功响应**：

```json
{
  "success": true,
  "request_type": "review",
  "data": {
    "report_id": "rpt_x1y2z3",
    "user_id": "user_001",
    "session_id": "sess_a1b2c3d4e5f6",
    "task_id": null,
    "tasks_completed": 4,
    "tasks_total": 6,
    "total_minutes": 145,
    "interruption_count": 0,
    "completion_rate": 0.667,
    "weak_points": [
      {
        "knowledge_point": "链式法则应用",
        "frequency": 3,
        "weight": 4.5
      },
      {
        "knowledge_point": "无穷级数收敛判定",
        "frequency": 2,
        "weight": 3.0
      }
    ],
    "recommended_material_ids": ["mat_a1b2c3d4", "mat_e5f6g7h8"],
    "next_tasks_suggestion": "明天建议先花20分钟回顾链式法则的典型例题，重点做2道复合函数求导练习题，再花30分钟复习级数的比较判别法。你的完成率在稳步提升，继续保持！",
    "created_at": "2026-05-13T16:00:00"
  },
  "message": "学习报告生成完成",
  "error": null
}
```

**失败响应（无学习记录）**：

```json
{
  "success": false,
  "request_type": "review",
  "data": null,
  "message": "[Reviewer] 未找到该学习会话（session_id 无效或已被删除）",
  "error": "[Reviewer] 未找到该学习会话（session_id 无效或已被删除）"
}
```

---

### 2.5 `chat` — 自然语言输入

用户以自然语言描述需求，后端 Classifier Agent 自动分类为 plan / upload / qa / review 之一，然后按分类后的 request_type 走对应管道。

**请求示例**：

```json
{
  "request_type": "chat",
  "user_id": "user_001",
  "goal_text": "帮我规划3小时复习高等数学下册，重点看无穷级数"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|:---:|------|
| `request_type` | string | ✓ | 固定 `"chat"` |
| `user_id` | string | ✓ | 用户唯一标识 |
| `goal_text` | string | ✓ | 自然语言描述的学习需求（任意内容） |

**分类规则（后端自动执行，前端无需关心）**：

| 用户意图 | 分类结果 | 后续处理 | 响应的 request_type |
|---------|---------|---------|:---:|
| 规划、复习、安排、备考 | `plan` | → Planner 生成关卡列表 | `"plan"` |
| 上传、文件、资料、照片（需有实际文件） | `upload` | → Librarian 处理文件入库 | `"upload"` |
| 提问、解释、怎么做、为什么、讲讲 | `qa` | → Coach 答疑 | `"qa"` |
| 复盘、报告、总结、回顾、薄弱点 | `review` | → Reviewer 出报告 | `"review"` |
| 无文件时说"帮我分析试卷" → 降级 | `qa` | → Coach 提示先上传文件 | `"qa"` |
| 闲聊/空白/完全无关 | `qa`（默认） | → Coach 引导性回复 | `"qa"` |

> **核心要点**：响应的 `request_type` 字段为分类后的结果（如 `"plan"`），而非原始的 `"chat"`。前端根据此字段渲染对应 UI。

**成功响应（分类为 plan）**：

```json
{
  "success": true,
  "request_type": "plan",
  "data": {
    "session_id": "sess_a1b2c3d4e5f6",
    "tasks": [
      {
        "index": 0,
        "subject": "高等数学",
        "title": "无穷级数收敛判定复习",
        "description": "回顾正项级数的比较判别法、比值判别法和根值判别法",
        "task_type": "review",
        "estimated_minutes": 40,
        "material_ids": [],
        "priority": 3,
        "status": "pending"
      }
    ],
    "total_estimated_minutes": 120,
    "knowledge_summary": "无穷级数包括数项级数、幂级数、傅里叶级数...",
    "web_search_used": false,
    "created_at": "2026-05-13T14:30:00"
  },
  "message": "学习关卡规划完成",
  "error": null
}
```

**成功响应（分类为 qa）**：

```json
{
  "success": true,
  "request_type": "qa",
  "data": {
    "answer": "## 链式法则详解\n\n链式法则是多元函数微积分的核心工具...",
    "answer_mode": "explain",
    "sources": [
      {
        "filename": "数学笔记.pdf",
        "chunk_index": 5,
        "similarity": 0.82,
        "preview": "链式法则：若 z = f(u,v)，u = u(x,y)，v = v(x,y)..."
      }
    ],
    "confidence": "high",
    "qa_log_id": "qa_x1y2z3w4"
  },
  "message": "答疑完成",
  "error": null
}
```

**失败响应（消息为空）**：

```json
{
  "success": false,
  "request_type": "chat",
  "data": {
    "chat_processed": false,
    "message": "chat 分类失败，请尝试使用具体功能（plan/qa/upload/review）"
  },
  "message": "[Classifier] chat 请求缺少消息内容",
  "error": "[Classifier] chat 请求缺少消息内容"
}
```

> **注意**：空消息不会触发任何 LLM 调用，后端直接短路返回错误。`message` 字段不再为空，前端可直接展示。

**失败响应（分类异常）**：

```json
{
  "success": false,
  "request_type": "chat",
  "data": {
    "chat_processed": false,
    "message": "chat 分类失败，请尝试使用具体功能（plan/qa/upload/review）"
  },
  "message": "[Classifier] 分类处理异常",
  "error": "[Classifier] 分类处理异常"
}
```

---

## 3. 健康检查 `/api/health`

**GET** `/api/health`

无需认证，用于监控和前端探活。

```json
{
  "status": "ok",
  "service": "StudyQuest",
  "qdrant": "ok",
  "qdrant_points": 1256
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `status` | string | `"ok"` 正常 |
| `service` | string | 服务名 |
| `qdrant` | string | 向量库状态，`"ok"` 或 `"error: ..."` |
| `qdrant_points` | int | 当前向量总数 |

---

## 4. 枚举速查

### 4.1 task_type

| 值 | 含义 | 建议图标 |
|----|------|:---:|
| `understand` | 理解概念 | 📖 |
| `practice` | 练习题 | ✏️ |
| `memorize` | 记忆背诵 | 🧠 |
| `correct` | 纠错订正 | 🔧 |
| `review` | 复盘总结 | 📊 |
| `break` | 休息 | ☕ |

### 4.2 task status

| 值 | 含义 |
|----|------|
| `pending` | 待开始 |
| `in_progress` | 进行中 |
| `completed` | 已完成 |
| `cancelled` | 已取消 |

### 4.3 answer_mode

| 值 | 含义 | 前端展示时机 |
|----|------|------------|
| `hint` | 提示模式 | 用户正在做题，不想被剧透 |
| `explain` | 讲解模式 | 用户想系统学习一个概念 |
| `review` | 复盘模式 | 用户回顾错题、归纳总结 |
| `auto` | 自动判定 | 后端根据问题 + 关卡类型自动选（默认值） |

### 4.4 confidence

| 值 | 含义 | 前端风格建议 |
|----|------|---------|
| `high` | 资料充分，回答可信度高 | 绿色 / 高可信标识 |
| `medium` | 有部分资料支撑 | 黄色 / 中可信标识 |
| `low` | 无相关上传资料，纯 LLM 回答 | 灰色 / 提示用户上传资料 |

---

## 5. 前端对接建议

### 5.1 典型调用流程

```
1. 用户上传资料
   前端将文件提交到后端存储 → 后端返回文件路径
   POST /api/studyquest  { request_type: "upload", file_paths: [...] }
   └→ 获得 material_id 列表

2. 用户说"帮我规划"
   POST /api/studyquest  { request_type: "plan", goal_text: "...", available_hours: 3.0 }
   或
   POST /api/studyquest  { request_type: "chat", goal_text: "帮我规划3小时复习数学" }
   └→ 获得 session_id + tasks 列表

3. 用户自由输入（推荐方式）
   POST /api/studyquest  { request_type: "chat", goal_text: "..." }
   └→ Classifier 自动分类为 plan/qa/upload/review 后走对应管道
   └→ 前端根据响应中的 request_type 渲染对应 UI

4. 用户点击关卡开始学习
   （前端本地状态管理）

5. 用户提问
   POST /api/studyquest  { request_type: "qa", question: "...", answer_mode: "auto", ... }
   └→ 默认传 "auto"，后端自动判定模式
   └→ 也可让用户在 UI 上手选 hint/explain/review

6. 用户完成学习
   POST /api/studyquest  { request_type: "review", review_session_id: "sess_xxx" }
   └→ 获得学习报告 + 薄弱点 + 明日建议
```

### 5.2 chat 使用建议

- **推荐使用 `chat` 作为默认入口**：用户自由输入，后端自动分类路由
- **在 UI 上保留快捷入口**：允许用户直接选择 plan/upload/qa/review，跳过分类步骤
- **处理响应时以 `request_type` 为准**：chat 请求的响应可能是 plan/qa/review 之一
- **文件上传不要走 chat**：chat→upload 仅在有实际文件时生效，无文件会降级为 qa

### 5.3 answer_mode 前端判定参考

前端可以根据这个简单规则给用户默认值，也可以直接传 `auto` 让后端判定：

```
if 问题含 "怎么做/这题/不会做/作业/提示/思路"    → hint
if 问题含 "错题/总结/归纳/回顾/为什么错了"      → review
else                                          → explain
```

建议在 UI 上提供三个按钮让用户显式切换模式，不依赖默认值。

### 5.4 错误处理建议

| 场景 | 前端处理 |
|------|---------|
| `success: false` + 网络错误 | 重试 1 次 |
| `success: false` + error 含 "timeout" | 提示用户后重试 |
| `success: false` + error 含 "API key" | 不重试，联系管理员 |
| `success: true` + data.errors 非空 | 部分文件失败，成功的已入库，展示失败列表 |
| `success: false` + request_type 为 "chat" | 分类失败，引导用户使用具体功能入口 |
| `success: false` + request_type 为 "unknown" | 系统级异常，展示 error 内容 |

---

