"""ADK entry point used by `adk web` and `adk run`."""
from .agents.manager_agent.agent import root_agent

__all__ = ["root_agent"]
