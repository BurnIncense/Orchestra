import logging
import shutil
from pathlib import Path
from typing import Optional

logger = logging.getLogger("orchestra.skills.versioning")


class SkillVersionManager:
    def __init__(self, versions_dir: str = "./data/skill_versions"):
        self.versions_dir = Path(versions_dir)
        self.versions_dir.mkdir(parents=True, exist_ok=True)

    def _skill_dir(self, skill_id: str) -> Path:
        d = self.versions_dir / skill_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def backup(self, skill_id: str, skill_source: str, version: str) -> str:
        skill_dir = self._skill_dir(skill_id)
        backup_path = skill_dir / f"v{version}.py"
        backup_path.write_text(skill_source, encoding="utf-8")
        logger.info(f"已备份 Skill: {skill_id} v{version}")
        return str(backup_path)

    def rollback(self, skill_id: str, version: str) -> bool:
        skill_dir = self._skill_dir(skill_id)
        backup_path = skill_dir / f"v{version}.py"
        if not backup_path.exists():
            logger.warning(f"找不到备份: {skill_id} v{version}")
            return False
        logger.info(f"已回滚 Skill: {skill_id} 到 v{version}")
        return True

    def list_versions(self, skill_id: str) -> list:
        skill_dir = self.versions_dir / skill_id
        if not skill_dir.exists():
            return []
        versions = []
        for f in skill_dir.glob("v*.py"):
            name = f.stem
            if name.startswith("v"):
                versions.append(name[1:])
        versions.sort()
        return versions
