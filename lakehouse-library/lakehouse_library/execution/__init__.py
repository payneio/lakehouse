"""Execution management for amplifier_library.

This module provides async execution of user prompts using amplifier-core.

Contract:
- Inputs: Session objects, user prompts, configuration
- Outputs: Async stream of execution results
- Side Effects: Executes LLM calls via amplifier-core
"""

from .runner import ExecutionRunner

__all__ = ["ExecutionRunner"]
