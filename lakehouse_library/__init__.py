"""Amplifier library layer.

This is the business logic layer that sits between amplifierd (transport)
and amplifier-core (execution engine).

Public Interface:
    Modules:
    - storage: JSON-based persistence
    - config: Configuration loading
    - models: Shared data structures
    - sessions: Session management
    - bridge: Bridge to amplifier-core
    - execution: Execution management
    - modules: Module management
"""

# Re-export key types for convenience
from .models import Session
from .models import SessionMetadata

__all__ = [
    "Session",
    "SessionMetadata",
]
