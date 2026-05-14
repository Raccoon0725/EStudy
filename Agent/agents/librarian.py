"""
Librarian（资料智能体）

职责：接收用户上传的文件/图片/PDF，进行多模态识别、分类和向量化入库。
处理管道：
  文件 → 类型判断 → OCR/文本提取 → LLM 自动分类 → 文本切块 → Embedding → Qdrant + MySQL
"""
import uuid
from pathlib import Path
from typing import List, Dict, Any
from agents.base import BaseAgent
from tools.ocr import extract_text_from_file, classify_material, chunk_text
from rag.qdrant_store import get_qdrant_store
from rag.retriever import get_retriever
from database.repository import insert_material, insert_material_chunks
from utils.file_storage import save_uploaded_file
from config import RAG_CHUNK_SIZE, RAG_CHUNK_OVERLAP


class LibrarianAgent(BaseAgent):
    """资料智能体：文件 → OCR → 分类 → 向量化 → 入库"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.store = get_qdrant_store()
        self.retriever = get_retriever()

    def process_files(
        self,
        user_id: str,
        file_paths: List[str] = None,
        file_urls: List[str] = None,
        context: str = None,
    ) -> Dict[str, Any]:
        """
        处理上传文件的主入口

        参数:
            user_id: 用户标识
            file_paths: 本地文件路径列表
            file_urls: 文件 URL 列表（暂不处理下载，MVP 简化）
            context: 用户上传文件时的备注

        返回:
            LibrarianOutput 的字典形式
        """
        file_paths = file_paths or []
        materials = []
        errors = []
        total_chunks = 0

        for fp in file_paths:
            try:
                material = self._process_single_file(user_id, fp, context)
                materials.append(material)
                total_chunks += material.get("chunk_count", 0)
            except Exception as e:
                self.log(f"处理失败: {fp} - {str(e)}", "ERROR")
                errors.append(f"{fp}: {str(e)}")

        return {
            "materials": materials,
            "total_chunks": total_chunks,
            "errors": errors,
            "context": context or "",
        }

    def _process_single_file(self, user_id: str, file_path: str, context: str = None) -> Dict[str, Any]:
        """
        处理单个文件的完整管道
        """
        path = Path(file_path)
        filename = path.name

        self.log(f"处理文件: {filename}")
        if context:
            self.log(f"上下文: {context[:100]}")

        # Step 1: 保存文件到本地
        saved_path = save_uploaded_file(file_path, user_id)

        # Step 2: 文本提取 / OCR
        file_type, extracted_text = extract_text_from_file(saved_path)
        self.log(f"文本提取完成 ({file_type}), 长度: {len(extracted_text)} 字符")
        # Step 3: LLM 自动分类
        classification = classify_material(extracted_text)
        self.log(f"分类结果: {classification}")

        # Step 4: 文本切块
        chunks = chunk_text(
            extracted_text,
            chunk_size=RAG_CHUNK_SIZE,
            overlap=RAG_CHUNK_OVERLAP,
        )
        self.log(f"切块完成: {len(chunks)} 块")

        # Step 5: Embedding + Qdrant 写入
        material_id = f"mat_{uuid.uuid4().hex[:12]}"
        chunk_records = []
        qdrant_indexed = True

        for i, chunk in enumerate(chunks):
            try:
                vec = self.retriever.embed_query(chunk)
                point_id = str(uuid.uuid4())

                self.store.upsert_points(
                    vectors=[vec],
                    payloads=[{
                        "user_id": user_id,
                        "material_id": material_id,
                        "filename": filename,
                        "subject": classification.get("subject", ""),
                        "chapter": classification.get("chapter", ""),
                        "knowledge_point": classification.get("knowledge_point", ""),
                        "chunk_index": i,
                        "content": chunk,
                    }],
                    point_ids=[point_id],
                )

                chunk_id = f"chk_{uuid.uuid4().hex[:12]}"
                chunk_records.append({
                    "id": chunk_id,
                    "material_id": material_id,
                    "chunk_index": i,
                    "content": chunk,
                    "qdrant_point_id": point_id,
                    "embedding_model": "Doubao-Seed-2.0-pro",
                })
            except Exception as e:
                self.log(f"向量化失败 (chunk {i}): {str(e)}", "ERROR")
                qdrant_indexed = False

        # Step 6: 写入 MySQL
        insert_material({
            "id": material_id,
            "user_id": user_id,
            "filename": filename,
            "file_type": file_type,
            "file_path": saved_path,
            "subject": classification.get("subject", ""),
            "chapter": classification.get("chapter", ""),
            "knowledge_point": classification.get("knowledge_point", ""),
            "ocr_text": extracted_text,
            "chunk_count": len(chunks),
            "qdrant_indexed": qdrant_indexed,
        })

        if chunk_records:
            insert_material_chunks(chunk_records)

        return {
            "material_id": material_id,
            "filename": filename,
            "file_type": file_type,
            "subject": classification.get("subject", ""),
            "chapter": classification.get("chapter", ""),
            "knowledge_point": classification.get("knowledge_point", ""),
            "ocr_text_preview": extracted_text[:200],
            "chunk_count": len(chunks),
            "qdrant_indexed": qdrant_indexed,
        }

    def recall_materials(
        self, user_id: str, knowledge_points: List[str]
    ) -> List[Dict[str, Any]]:
        """
        资料召回：根据薄弱知识点从 Qdrant 检索相关 chunk
        供 Reviewer 调用
        """
        all_docs = []
        for kp in knowledge_points:
            docs = self.retriever.retrieve(kp, user_id, top_k=3)
            all_docs.extend(docs)

        # 去重（按 material_id）
        seen = set()
        unique = []
        for d in all_docs:
            mid = d.get("material_id", "")
            if mid and mid not in seen:
                seen.add(mid)
                unique.append(d)

        return unique
