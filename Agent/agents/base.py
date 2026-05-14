"""
Agent 基类
提供公共的 LLM 调用和日志功能
"""
from abc import ABC
from typing import Optional
from langchain_core.language_models import BaseChatModel
from config import get_llm


class BaseAgent(ABC):
    """所有 Agent 的基类"""

    def __init__(self, llm: Optional[BaseChatModel] = None):
        self.llm = llm or get_llm()
        self.name = self.__class__.__name__

    def log(self, message: str, level: str = "INFO"):
        print(f"[{self.name}] [{level}] {message}")
