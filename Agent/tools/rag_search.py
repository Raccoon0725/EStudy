"""
RAG 搜索工具
封装为 LangChain Tool，供 Agent 在推理过程中调用
"""
from typing import Optional, Type
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
from rag.retriever import get_retriever


class RAGSearchInput(BaseModel):
    query: str = Field(description="搜索查询文本（建议用完整的问题或知识点描述）")
    user_id: str = Field(description="用户 ID，用于过滤个人资料")
    top_k: int = Field(default=5, description="返回结果数量")
    subject: Optional[str] = Field(default=None, description="可选的科目过滤")


class RAGSearchTool(BaseTool):
    """在用户已导入的学习资料中进行语义搜索"""
    name: str = "rag_search"
    description: str = (
        "在用户已导入的学习资料中进行语义搜索。"
        "适用于：查找知识点定义、搜索相关例题、检索概念解释。"
        "返回相关资料片段及其来源文件名。"
    )
    args_schema: Type[BaseModel] = RAGSearchInput

    def _run(self, query: str, user_id: str, top_k: int = 5, subject: Optional[str] = None) -> str:
        retriever = get_retriever()
        docs = retriever.retrieve(query, user_id, top_k, subject_filter=subject)
        return retriever.format_retrieved_context(docs)


def get_rag_tool() -> RAGSearchTool:
    return RAGSearchTool()
