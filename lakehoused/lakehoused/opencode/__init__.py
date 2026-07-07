"""opencode backend for lakehoused.

Replaces the Amplifier (amplifier-core / amplifier-foundation) chat backend with
opencode (sst/opencode) driven over its HTTP server API. See CONTRACT.md in this
package for the webapp SSE contract the event translator must reproduce.

Modules:
- client: thin async httpx wrapper over the opencode HTTP API
- server_manager: pooled `opencode serve` process lifecycle (one server per manifest)
- events: opencode /event -> EventQueueEmitter translation
- runner: OpencodeRunner (replaces execution.runner.ExecutionRunner)
"""

from .assistants import AssistantInfo
from .assistants import LakehouseOpencodeManager
from .assistants import ResolvedManifest
from .client import OpencodeClient
from .client import OpencodeError
from .runner import OpencodeRunner
from .server_manager import ManifestSpec
from .server_manager import OpencodeServer
from .server_manager import OpencodeServerRegistry
from .server_manager import extract_env_var_names

__all__ = [
    "AssistantInfo",
    "LakehouseOpencodeManager",
    "ManifestSpec",
    "OpencodeClient",
    "OpencodeError",
    "OpencodeRunner",
    "OpencodeServer",
    "OpencodeServerRegistry",
    "ResolvedManifest",
    "extract_env_var_names",
]
