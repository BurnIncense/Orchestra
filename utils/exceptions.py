class OrchestraError(Exception):
    pass


class SessionError(OrchestraError):
    pass


class SkillError(OrchestraError):
    pass


class SandboxError(OrchestraError):
    pass


class MCPError(OrchestraError):
    pass


class SagaError(OrchestraError):
    pass


class ModelError(OrchestraError):
    pass


class CyclicDependencyError(OrchestraError):
    pass
