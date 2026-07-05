"""Automation management module.

Provides automation scheduling, execution tracking, and storage management.

Public Interface:
    - AutomationManager: Manages automation lifecycle and persistence
"""

from .manager import AutomationManager

__all__ = ["AutomationManager"]
