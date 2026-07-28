"""
依赖图与运行时调用守卫

负责：
1. RuntimeCallGuard — 运行时调用栈深度 + 循环检测
2. DependencyGraph — Skill 间依赖关系的静态环检测
"""

from utils.exceptions import CyclicDependencyError


class RuntimeCallGuard:
    def __init__(self, max_depth: int = 10):
        self.stack: list[str] = []
        self.max_depth = max_depth

    def enter(self, skill_id: str) -> None:
        if len(self.stack) >= self.max_depth:
            raise RecursionError(f"调用深度超过 {self.max_depth}")
        if skill_id in self.stack:
            cycle_start = self.stack.index(skill_id)
            cycle = self.stack[cycle_start:] + [skill_id]
            raise CyclicDependencyError(f"循环: {' → '.join(cycle)}")
        self.stack.append(skill_id)

    def exit(self) -> None:
        if self.stack:
            self.stack.pop()

    def reset(self) -> None:
        self.stack.clear()

    def is_cyclic(self, skill_id: str) -> bool:
        return skill_id in self.stack


class DependencyGraph:
    def __init__(self):
        self._graph: dict[str, list[str]] = {}

    def add_edge(self, from_id: str, to_id: str):
        if from_id not in self._graph:
            self._graph[from_id] = []
        if to_id not in self._graph:
            self._graph[to_id] = []
        if to_id not in self._graph[from_id]:
            self._graph[from_id].append(to_id)

    def detect_cycles(self) -> list[list[str]]:
        cycles: list[list[str]] = []
        visited: set[str] = set()
        rec_stack: list[str] = []

        def dfs(node: str):
            visited.add(node)
            rec_stack.append(node)
            for neighbor in self._graph.get(node, []):
                if neighbor not in visited:
                    dfs(neighbor)
                elif neighbor in rec_stack:
                    cycle_start = rec_stack.index(neighbor)
                    cycle = rec_stack[cycle_start:] + [neighbor]
                    cycles.append(cycle)
            rec_stack.pop()

        for node in self._graph:
            if node not in visited:
                dfs(node)

        return cycles
