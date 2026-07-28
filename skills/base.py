import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger("orchestra.skills.base")


class SkillCategory(Enum):
    BUILTIN = "builtin"
    COMPOSITE = "composite"
    EXTENSION = "extension"
    LEARNED = "learned"
    MCP = "mcp"


@dataclass
class SkillParameter:
    name: str
    type: str
    required: bool = False
    description: str = ""
    default: Any = None


@dataclass
class SkillMetadata:
    id: str
    name: str
    version: str
    category: SkillCategory
    description: str
    triggers: dict = field(default_factory=lambda: {"keywords": [], "intent_types": []})
    parameters: list = field(default_factory=list)
    permissions: list = field(default_factory=list)


class BaseSkill(ABC):
    def __init__(self, metadata: SkillMetadata):
        self.metadata = metadata

    @abstractmethod
    async def execute(self, params: dict, context: dict = None) -> dict:
        return {"success": False, "outputs": {}, "error": "未实现"}

    def validate_params(self, params: dict) -> tuple:
        return True, ""
