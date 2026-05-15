"""
RAG 检索器
封装"问题 Embedding → Qdrant 检索 → 结果组装"的完整链路
"""
import json
from typing import List, Dict, Any, Optional
from langchain_core.documents import Document
from config import get_embeddings, RAG_TOP_K
from rag.qdrant_store import get_qdrant_store


class RAGRetriever:
    """RAG 检索器：语义搜索用户已导入的资料"""

    def __init__(self):
        self.embeddings = get_embeddings()
        self.store = get_qdrant_store()

    def embed_query(self, query: str) -> List[float]:
        """文本 → 向量"""
        return self.embeddings.embed_query(query)

    def retrieve(
        self,
        query: str,
        user_id: str,
        top_k: int = None,
        subject_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        检索相关文档片段
        返回: [{content, filename, subject, chapter, knowledge_point, similarity, chunk_index, point_id}, ...]
        """
        if top_k is None:
            top_k = RAG_TOP_K

        query_vec = self.embed_query(query)
        results = self.store.search(
            query_vector=query_vec,
            user_id=user_id,
            top_k=top_k,
            subject_filter=subject_filter,
        )

        docs = []
        for r in results:
            payload = r.payload or {}
            docs.append({
                "content": payload.get("content", ""),
                "filename": payload.get("filename", ""),
                "subject": payload.get("subject", ""),
                "chapter": payload.get("chapter", ""),
                "knowledge_point": payload.get("knowledge_point", ""),
                "similarity": round(r.score, 4),
                "chunk_index": payload.get("chunk_index", 0),
                "point_id": r.id,
                "material_id": payload.get("material_id", ""),
            })
        return docs

    def retrieve_as_documents(
        self,
        query: str,
        user_id: str,
        top_k: int = None,
    ) -> List[Document]:
        """以 LangChain Document 格式返回"""
        docs = self.retrieve(query, user_id, top_k)
        return [
            Document(
                page_content=d["content"],
                metadata={
                    "source": d["filename"],
                    "subject": d["subject"],
                    "chapter": d["chapter"],
                    "knowledge_point": d["knowledge_point"],
                    "similarity": d["similarity"],
                    "chunk_index": d["chunk_index"],
                }
            )
            for d in docs
        ]

    def format_retrieved_context(self, docs: List[Dict[str, Any]]) -> str:
        """将检索结果格式化为 prompt 可用的上下文字符串"""
        if not docs:
            return "（未在已导入资料中找到相关内容）"

        parts = []
        for i, d in enumerate(docs, 1):
            parts.append(
                f"[资料片段 {i}] 来源: {d['filename']} | "
                f"科目: {d['subject']} | 知识点: {d['knowledge_point']} | "
                f"相关度: {d['similarity']}\n{d['content']}"
            )
        return "\n\n---\n\n".join(parts)


# 全局单例
_retriever: Optional[RAGRetriever] = None


def get_retriever() -> RAGRetriever:
    global _retriever
    if _retriever is None:
        _retriever = RAGRetriever()
    return _retriever
