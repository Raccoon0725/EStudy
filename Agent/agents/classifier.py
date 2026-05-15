"""
Classifier（意图分类智能体）

职责：当 request_type 为 "chat" 时，分析用户自然语言输入，
将其分类为 plan / upload / qa / review 之一，并提取对应参数。

分类后的 request_type 和参数会写回 GraphState，
后续由 supervisor 按改写后的 request_type 正常路由。
"""
import json
from typing import Dict, Any
from langchain_core.messages import HumanMessage, SystemMessage
from agents.base import BaseAgent


CLASSIFIER_SYSTEM_PROMPT = """你是一个意图分类器。用户会用自然语言描述一个学习相关的需求。
你的任务是将需求分类为以下四种类型之一，并提取相关参数。

## 四种类型

1. **plan** — 用户想要制定学习计划、规划学习关卡
   - 关键词：规划、计划、复习、学、安排、备考、帮我安排
   - 提取：goal_text（学习目标）、available_hours（可用小时数，默认2.0）

2. **upload** — 用户提到要上传文件、处理资料
   - 关键词：上传、文件、资料、照片、笔记、试卷、教材
   - 提取：是否有文件引用（has_files，bool）

3. **qa** — 用户想问问题、请求答疑
   - 关键词：怎么、为什么、是什么、解释、这题、不会做、讲讲、帮我看看
   - 提取：question（问题文本）、answer_mode（hint/explain/review/auto，默认auto）

4. **review** — 用户想要复盘、查看学习报告
   - 关键词：复盘、报告、总结、回顾、学了什么、薄弱点、进度
   - 提取：review_time_range（时间范围，默认"7d"）

## 规则

- 如果用户同时表达了多个意图（如"帮我规划复习，顺便看看这道题"），选择最主要的意图
- 如果意图模糊，默认归类为 qa
- **重要**：upload 类型仅在用户确实已附加文件时使用。如果用户提到上传/文件/资料但没有实际附加文件，不要分类为 upload，应分类为 qa 并提示用户先上传文件
- 如果消息是纯闲聊（如"你好"、表情符号）、空白、或与学习完全无关（如"今天天气"），分类为 qa，question 设为"我需要学习方面的帮助，请问你想了解什么？"
- 输出必须是合法的 JSON，不要有任何额外文字

## 输出格式

{
  "request_type": "plan",
  "goal_text": "用户的学习目标（仅 plan）",
  "available_hours": 2.0,
  "question": "用户的问题（仅 qa）",
  "answer_mode": "auto",
  "has_files": false,
  "review_time_range": "7d"
}

只输出 JSON，不要包含 ```json 标记。"""


class ClassifierAgent(BaseAgent):
    """意图分类智能体"""

    def classify(self, message: str) -> Dict[str, Any]:
        """
        对用户自然语言输入进行分类。

        Args:
            message: 用户的自然语言输入

        Returns:
            dict 包含:
                - request_type: "plan" | "upload" | "qa" | "review"
                - goal_text: 提取的学习目标（plan 时）
                - available_hours: 可用小时数（plan 时）
                - question: 提取的问题文本（qa 时）
                - answer_mode: 应答模式（qa 时）
                - has_files: 是否涉及文件（upload 时）
                - review_time_range: 复盘时间范围（review 时）
        """
        self.log(f"开始分类: {message[:100]}...")

        response = self.llm.invoke([
            SystemMessage(content=CLASSIFIER_SYSTEM_PROMPT),
            HumanMessage(content=message),
        ])

        try:
            result = json.loads(response.content)
        except json.JSONDecodeError:
            # 尝试从响应中提取 JSON
            content = response.content
            # 处理可能的 markdown 代码块
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            try:
                result = json.loads(content)
            except json.JSONDecodeError:
                self.log(f"JSON 解析失败，回退为 qa: {response.content[:200]}", "WARN")
                result = {"request_type": "qa", "question": message, "answer_mode": "auto"}

        # 校验 request_type
        valid_types = {"plan", "upload", "qa", "review"}
        if result.get("request_type") not in valid_types:
            self.log(f"无效的 request_type: {result.get('request_type')}，回退为 qa", "WARN")
            result = {"request_type": "qa", "question": message, "answer_mode": "auto"}

        self.log(f"分类结果: {result.get('request_type')}")
        return result
