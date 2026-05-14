"""
Qdrant 向量数据库客户端
封装 Collection 管理、向量写入、语义检索
"""
import uuid
from typing import List, Optional, Dict, Any
from qdrant_client import QdrantClient
from qdrant_client.models import (
    VectorParams, Distance, PointStruct, Filter, FieldCondition, MatchValue,
    ScoredPoint, PayloadSchemaType,
)
from config import (
    QDRANT_URL, QDRANT_HOST, QDRANT_PORT, QDRANT_API_KEY, QDRANT_COLLECTION,
    RAG_TOP_K, RAG_SIMILARITY_THRESHOLD,
)


class QdrantStore:
    """Qdrant 向量存储封装"""

    def __init__(self):
        if QDRANT_URL:
            self.client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
        else:
            self.client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
        self.collection = QDRANT_COLLECTION
        self._ensure_collection()

    def _ensure_collection(self):
        """确保 Collection 及索引存在"""
        collections = [c.name for c in self.client.get_collections().collections]
        if self.collection not in collections:
            self.client.create_collection(
                collection_name=self.collection,
                vectors_config=VectorParams(
                    size=1536,  # text-embedding-3-small 维度
                    distance=Distance.COSINE,
                ),
            )
            print(f"[Qdrant] Created collection: {self.collection}")

        # 确保 payload 索引（filter 查询必需）
        try:
            self.client.create_payload_index(
                collection_name=self.collection,
                field_name="user_id",
                field_schema=PayloadSchemaType.KEYWORD,
            )
        except Exception:
            pass  # 索引已存在则忽略

    def upsert_points(
        self,
        vectors: List[List[float]],
        payloads: List[Dict[str, Any]],
        point_ids: Optional[List[str]] = None,
    ) -> List[str]:
        """批量写入向量点"""
        if point_ids is None:
            point_ids = [str(uuid.uuid4()) for _ in vectors]

        points = [
            PointStruct(id=pid, vector=vec, payload=pl)
            for pid, vec, pl in zip(point_ids, vectors, payloads)
        ]

        self.client.upsert(collection_name=self.collection, points=points)
        return point_ids

    def search(
        self,
        query_vector: List[float],
        user_id: str,
        top_k: int = None,
        subject_filter: Optional[str] = None,
        similarity_threshold: Optional[float] = None,
    ) -> List[ScoredPoint]:
        """语义搜索 + 用户过滤"""
        if top_k is None:
            top_k = RAG_TOP_K
        if similarity_threshold is None:
            similarity_threshold = RAG_SIMILARITY_THRESHOLD

        must_conditions = [
            FieldCondition(key="user_id", match=MatchValue(value=user_id))
        ]
        if subject_filter:
            must_conditions.append(
                FieldCondition(key="subject", match=MatchValue(value=subject_filter))
            )

        results = self.client.search(
            collection_name=self.collection,
            query_vector=query_vector,
            query_filter=Filter(must=must_conditions),
            limit=top_k,
            score_threshold=similarity_threshold,
        )
        return results

    def delete_by_user(self, user_id: str):
        """删除用户的所有向量"""
        self.client.delete(
            collection_name=self.collection,
            points_selector=Filter(
                must=[FieldCondition(key="user_id", match=MatchValue(value=user_id))]
            ),
        )

    def delete_points(self, point_ids: List[str]):
        """删除指定向量点"""
        self.client.delete(
            collection_name=self.collection,
            points_selector=point_ids,
        )

    def count(self) -> int:
        """获取总向量数"""
        info = self.client.get_collection(self.collection)
        return info.points_count


# 全局单例
_qdrant_store: Optional[QdrantStore] = None


def get_qdrant_store() -> QdrantStore:
    global _qdrant_store
    if _qdrant_store is None:
        _qdrant_store = QdrantStore()
    return _qdrant_store
