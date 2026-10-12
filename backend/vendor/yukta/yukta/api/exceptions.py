"""
Custom exceptions for ecosystem module.
"""

class EcosystemError(Exception):
    """Base exception for ecosystem errors."""
    pass


class AgentNotFoundError(EcosystemError):
    """Raised when an agent is not found in ecosystem."""
    pass


class SkillNotFoundError(EcosystemError):
    """Raised when a skill is not found in ecosystem."""
    pass


class ToolNotFoundError(EcosystemError):
    """Raised when a tool is not found in ecosystem."""
    pass


class TeamNotFoundError(EcosystemError):
    """Raised when a team is not found in ecosystem."""
    pass


class ValidationError(EcosystemError):
    """Raised when ecosystem validation fails."""
    pass


__all__ = [
    "EcosystemError",
    "AgentNotFoundError",
    "SkillNotFoundError",
    "ToolNotFoundError",
    "TeamNotFoundError",
    "ValidationError",
]
