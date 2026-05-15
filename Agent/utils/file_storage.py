"""
文件存储工具
本地文件读写 + 任务文件（JSONL + T*.md）备份
"""
import json
import re
import uuid
import shutil
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime
from config import UPLOAD_DIR, TASK_DIR, MAX_FILE_SIZE_MB, ALLOWED_EXTENSIONS, MAX_FILENAME_LENGTH

# user_id 允许的字符：字母、数字、下划线、连字符，长度 1-64
_USER_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


def _validate_user_id(user_id: str) -> None:
    """校验 user_id，防止路径遍历"""
    if not user_id or not _USER_ID_RE.match(user_id):
        raise ValueError(f"无效的 user_id: {user_id!r}，仅允许字母数字下划线连字符，最长64字符")


def _validate_path_within(target_path: Path, allowed_base: Path) -> None:
    """
    确保解析后的路径在 allowed_base 目录内（防路径遍历）。
    若路径存在则用 resolve() 消除符号链接后检查；不存在则用 parent.resolve()。
    """
    try:
        resolved = target_path.resolve(strict=False)
    except (OSError, ValueError):
        raise ValueError(f"路径解析失败: {target_path}")

    allowed = allowed_base.resolve(strict=False)
    try:
        resolved.relative_to(allowed)
    except ValueError:
        raise ValueError(f"路径遍历检测: {target_path} 不在 {allowed_base} 内")


def _validate_source_file(source_path: Path) -> None:
    """校验源文件：必须存在、必须是文件、大小不超限"""
    if not source_path.exists():
        raise FileNotFoundError(f"源文件不存在: {source_path}")
    if not source_path.is_file():
        raise ValueError(f"源路径不是文件: {source_path}")

    size_mb = source_path.stat().st_size / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        raise ValueError(
            f"文件过大: {source_path.name} ({size_mb:.1f}MB)，最大允许 {MAX_FILE_SIZE_MB}MB"
        )


def _validate_extension(filename: str) -> None:
    """校验文件扩展名"""
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"不支持的文件类型: {ext}，允许: {sorted(ALLOWED_EXTENSIONS)}")


def save_uploaded_file(source_path: str, user_id: str) -> str:
    """
    保存上传文件到本地存储。

    安全措施：
      - 校验 user_id 不含路径遍历字符
      - 校验源文件路径合法且存在
      - 校验文件大小在限制内
      - 校验文件扩展名在允许列表中
      - 目标路径确保在 UPLOAD_DIR 内
    """
    _validate_user_id(user_id)

    src = Path(source_path).resolve(strict=True)
    _validate_source_file(src)
    _validate_extension(src.name)

    if len(src.name) > MAX_FILENAME_LENGTH:
        raise ValueError(f"文件名过长: {len(src.name)} 字符，最大 {MAX_FILENAME_LENGTH}")

    dest_dir = (UPLOAD_DIR / user_id).resolve()
    _validate_path_within(dest_dir, UPLOAD_DIR)
    dest_dir.mkdir(parents=True, exist_ok=True)

    dest = dest_dir / f"{uuid.uuid4().hex[:8]}_{src.name}"
    shutil.copy2(src, dest)
    return str(dest)


def save_planner_json(user_id: str, session_id: str, data: dict) -> str:
    """保存 Planner 输出的关卡 JSON 到本地文件"""
    _validate_user_id(user_id)
    dest_dir = UPLOAD_DIR / user_id / "plans"
    dest_dir.mkdir(parents=True, exist_ok=True)

    filepath = dest_dir / f"{session_id}_plan.json"
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return str(filepath)


def save_report_json(user_id: str, report_id: str, data: dict) -> str:
    """保存复盘报告 JSON 到本地文件"""
    _validate_user_id(user_id)
    dest_dir = UPLOAD_DIR / user_id / "reports"
    dest_dir.mkdir(parents=True, exist_ok=True)

    filepath = dest_dir / f"{report_id}.json"
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return str(filepath)


# ============================================================
# 任务文件备份（参考 Agent 设计模式 第四章）
# ============================================================
def save_task_index(tasks: List[Dict[str, Any]]) -> str:
    """将任务列表写入 _index.jsonl"""
    TASK_DIR.mkdir(parents=True, exist_ok=True)
    index_path = TASK_DIR / "_index.jsonl"

    with open(index_path, "w", encoding="utf-8") as f:
        for t in tasks:
            record = {
                "id": t.get("id", ""),
                "subject": t.get("subject", t.get("title", "")),
                "status": t.get("status", "pending"),
                "parent": t.get("parent_id"),
                "blocked_by": t.get("blocked_by", []),
                "blocks": t.get("blocks", []),
                "created_at": t.get("created_at", datetime.now().isoformat()),
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return str(index_path)


def save_task_file(task: Dict[str, Any]) -> str:
    """保存单个任务为 T*.md 文件（YAML frontmatter + Markdown body）"""
    TASK_DIR.mkdir(parents=True, exist_ok=True)

    tid = task.get("id", f"task_{uuid.uuid4().hex[:12]}")
    filepath = TASK_DIR / f"{tid}.md"

    frontmatter = {
        "id": tid,
        "subject": task.get("subject", task.get("title", "")),
        "status": task.get("status", "pending"),
        "parent": task.get("parent_id"),
        "blocked_by": task.get("blocked_by", []),
        "blocks": task.get("blocks", []),
        "created_at": task.get("created_at", datetime.now().isoformat()),
        "updated_at": datetime.now().isoformat(),
    }

    import yaml
    content = f"""---
{yaml.dump(frontmatter, allow_unicode=True, default_flow_style=False)}---

## 描述
{task.get('description', task.get('title', ''))}

## 关卡信息
- **科目**: {task.get('subject', '')}
- **类型**: {task.get('task_type', '')}
- **预估时长**: {task.get('estimated_minutes', 0)} 分钟
- **优先级**: {task.get('priority', 1)}

## 关联资料
{chr(10).join(f'- {m}' for m in task.get('material_ids', []))}
"""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    return str(filepath)
