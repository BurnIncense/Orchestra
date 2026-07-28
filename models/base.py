from abc import ABC, abstractmethod
from enum import Enum


class ModelState(Enum):
    UNLOADED = "unloaded"
    LOADING = "loading"
    LOADED = "loaded"
    ERROR = "error"


class BaseModel(ABC):
    def __init__(self, name: str):
        self.name = name
        self.state = ModelState.UNLOADED

    @abstractmethod
    def load(self):
        ...

    @abstractmethod
    def unload(self):
        ...

    @abstractmethod
    def is_available(self) -> bool:
        ...
