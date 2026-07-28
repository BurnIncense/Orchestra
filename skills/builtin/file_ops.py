# skills/builtin/file_ops.py
"""
文件操作 Skill
"""

import os
import logging
from pathlib import Path
from skills.base import BaseSkill, SkillMetadata, SkillCategory, SkillParameter

logger = logging.getLogger("orchestra.skills.builtin.file_ops")

ALLOWED_BASE_DIRS = ["./data", "./workspace", "./tmp"]


def _is_path_allowed(target_path: str) -> bool:
    abs_target = os.path.abspath(target_path)
    for base_dir in ALLOWED_BASE_DIRS:
        abs_base = os.path.abspath(base_dir)
        if abs_target.startswith(abs_base + os.sep) or abs_target == abs_base:
            return True
    return False


class FileOperationsSkill(BaseSkill):
    def __init__(self):
        super().__init__(SkillMetadata(
            id="file_operations",
            name="文件操作",
            version="1.0.0",
            category=SkillCategory.BUILTIN,
            description="文件读写操作",
            triggers={
                "keywords": ["文件", "读文件", "写文件", "file", "read", "write"],
                "intent_types": [],
            },
            parameters=[
                SkillParameter("operation", "string", True, description="操作类型: read/write/list/delete"),
                SkillParameter("path", "string", True, description="文件路径"),
                SkillParameter("content", "string", False, description="写入内容"),
            ],
            permissions=[],
        ))

    async def execute(self, params: dict, context: dict = None) -> dict:
        operation = params.get("operation", "").lower()
        path = params.get("path", "")
        content = params.get("content", "")

        if not operation or not path:
            return {"success": False, "outputs": {}, "error": "缺少 operation 或 path 参数"}

        if not _is_path_allowed(path):
            return {"success": False, "outputs": {}, "error": f"路径不在允许范围内: {path}"}

        try:
            if operation == "read":
                data = self._read_file(path)
                return {"success": True, "outputs": {"content": data}}
            elif operation == "write":
                self._write_file(path, content)
                return {"success": True, "outputs": {"path": path, "size": len(content)}}
            elif operation == "list":
                files = self._list_dir(path)
                return {"success": True, "outputs": {"files": files}}
            elif operation == "delete":
                self._delete_file(path)
                return {"success": True, "outputs": {"path": path}}
            else:
                return {"success": False, "outputs": {}, "error": f"不支持的操作: {operation}"}
        except Exception as e:
            logger.error(f"文件操作失败: {e}")
            return {"success": False, "outputs": {}, "error": str(e)}

    def _read_file(self, path: str) -> str:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    def _write_file(self, path: str, content: str) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    def _list_dir(self, path: str) -> list:
        if not os.path.isdir(path):
            return []
        entries = []
        for entry in os.listdir(path):
            full_path = os.path.join(path, entry)
            entries.append({
                "name": entry,
                "type": "dir" if os.path.isdir(full_path) else "file",
                "size": os.path.getsize(full_path) if os.path.isfile(full_path) else 0,
            })
        return entries

    def _delete_file(self, path: str) -> None:
        if os.path.isdir(path):
            import shutil
            shutil.rmtree(path)
        else:
            os.remove(path)
