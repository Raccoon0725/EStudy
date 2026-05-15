"""
Tavily 联网搜索工具
当 RAG 中找不到相关内容时，回退到联网搜索
"""
from typing import Type
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
from tavily import TavilyClient
from config import TAVILY_API_KEY


class WebSearchInput(BaseModel):
    query: str = Field(description="搜索查询文本")
    max_results: int = Field(default=5, description="最大返回结果数")
    include_raw_content: bool = Field(default=False, description="是否包含原始内容")


class WebSearchTool(BaseTool):
    """使用 Tavily API 进行联网搜索"""
    name: str = "web_search"
    description: str = (
        "通过 Tavily API 联网搜索最新信息。"
        "当 RAG 知识库中找不到相关内容时使用。"
        "适用于：查找课本外的知识、获取最新考试大纲、搜索补充学习资料。"
    )
    args_schema: Type[BaseModel] = WebSearchInput

    def _run(self, query: str, max_results: int = 5, include_raw_content: bool = False) -> str:
        if not TAVILY_API_KEY:
            return "[WebSearch 不可用] 未配置 TAVILY_API_KEY，跳过联网搜索。"

        client = TavilyClient(api_key=TAVILY_API_KEY)
        try:
            response = client.search(
                query=query,
                max_results=max_results,
                include_raw_content=include_raw_content,
                search_depth="advanced",
            )
        except Exception as e:
            return f"[WebSearch 失败] {str(e)}"

        results = response.get("results", [])
        if not results:
            return "[WebSearch] 未找到相关结果。"

        parts = []
        for i, r in enumerate(results, 1):
            title = r.get("title", "无标题")
            url = r.get("url", "")
            content = r.get("content", "")
            parts.append(f"[搜索结果 {i}] {title}\nURL: {url}\n{content}")

        return "\n\n---\n\n".join(parts)


def get_web_search_tool() -> WebSearchTool:
    return WebSearchTool()
