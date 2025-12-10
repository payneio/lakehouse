"""Storage module for amplifier_library.

Provides JSON-based persistence with atomic writes and retry logic.

Public Interface:
    - save_json: Save data with atomic write
    - load_json: Load data with error recovery
    - list_stored: List stored items
    - delete_stored: Delete stored item
    - exists: Check if item exists
    - get_root_dir: Get AMPLIFIERD_HOME
    - get_config_dir: Get config directory
    - get_share_dir: Get data directory
    - get_state_dir: Get state/cache directory
    - get_log_dir: Get log directory
"""

from .paths import get_config_dir
from .paths import get_home_dir
from .paths import get_log_dir
from .paths import get_share_dir
from .paths import get_state_dir

__all__ = [
    "get_home_dir",
    "get_config_dir",
    "get_share_dir",
    "get_state_dir",
    "get_log_dir",
]
