import importlib.util
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("orchestra.skills.loader")


class SkillLoader:
    def __init__(self, registry):
        self.registry = registry

    def load_from_directory(self, dir_path: str) -> int:
        count = 0
        dir_path = Path(dir_path)
        if not dir_path.exists():
            logger.warning(f"目录不存在: {dir_path}")
            return 0

        for py_file in dir_path.glob("*.py"):
            if py_file.name.startswith("_"):
                continue
            skill = self.load_from_file(str(py_file))
            if skill:
                count += 1
        return count

    def load_from_file(self, file_path: str):
        file_path = Path(file_path)
        if not file_path.exists():
            logger.warning(f"文件不存在: {file_path}")
            return None

        try:
            module_name = f"skill_{file_path.stem}"
            spec = importlib.util.spec_from_file_location(module_name, str(file_path))
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            if hasattr(module, "create_skill"):
                skill = module.create_skill()
                if skill:
                    self.registry.register(skill)
                    logger.info(f"已加载 Skill: {skill.metadata.id} ({file_path.name})")
                    return skill
            else:
                logger.debug(f"文件缺少 create_skill: {file_path.name}")
        except Exception as e:
            logger.error(f"加载 Skill 失败 {file_path.name}: {e}")
        return None
