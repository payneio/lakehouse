"""API models for lakehoused daemon.

This module defines request and response models for the REST API.
"""

from lakehouse_library.models.sessions import SessionIndex
from lakehouse_library.models.sessions import SessionIndexEntry
from lakehouse_library.models.sessions import SessionMessage
from lakehouse_library.models.sessions import SessionMetadata
from lakehouse_library.models.sessions import SessionQuery
from lakehouse_library.models.sessions import SessionStatus

from .bundles import BundleDetails
from .bundles import BundleListItem
from .bundles import BundleSource
from .bundles import CopyBundleRequest
from .bundles import CreateBundleRequest
from .bundles import ModuleRef
from .bundles import ResolvedBundle
from .bundles import ResolvedModuleRef
from .bundles import UpdateBundleRequest
from .errors import ErrorResponse
from .errors import ValidationErrorDetail
from .modules import ModuleDetails
from .modules import ModuleInfo
from .mount_plans import EmbeddedMount
from .mount_plans import MountPlan
from .mount_plans import MountPlanRequest
from .mount_plans import MountPlanSummary
from .mount_plans import MountPoint
from .mount_plans import ReferencedMount
from .mount_plans import SessionConfig
from .profiles import ModuleConfig
from .profiles import ProfileDetails
from .profiles import ProfileInfo
from .projects import AgentsContentResponse
from .projects import AgentsContentUpdate
from .projects import Project
from .projects import ProjectCreate
from .projects import ProjectList
from .projects import ProjectUpdate
from .requests import CreateSessionRequest
from .requests import SendMessageRequest
from .requests import UpdateContextRequest
from .responses import MessageResponse
from .responses import SessionInfoResponse
from .responses import SessionResponse
from .responses import StatusResponse
from .responses import TranscriptResponse

__all__ = [
    # Bundle models
    "BundleListItem",
    "BundleDetails",
    "BundleSource",
    "ResolvedBundle",
    "ResolvedModuleRef",
    "ModuleRef",
    "CreateBundleRequest",
    "CopyBundleRequest",
    "UpdateBundleRequest",
    # Project models
    "Project",
    "ProjectCreate",
    "ProjectUpdate",
    "ProjectList",
    "AgentsContentUpdate",
    "AgentsContentResponse",
    # Session requests
    "CreateSessionRequest",
    "SendMessageRequest",
    "UpdateContextRequest",
    # Errors
    "ErrorResponse",
    "ValidationErrorDetail",
    # Responses
    "MessageResponse",
    "SessionInfoResponse",
    "SessionResponse",
    "StatusResponse",
    "TranscriptResponse",
    # Profiles
    "ProfileInfo",
    "ProfileDetails",
    "ModuleConfig",
    # Modules
    "ModuleInfo",
    "ModuleDetails",
    # Mount plans
    "EmbeddedMount",
    "ReferencedMount",
    "MountPoint",
    "SessionConfig",
    "MountPlan",
    "MountPlanRequest",
    "MountPlanSummary",
    # Sessions
    "SessionStatus",
    "SessionMetadata",
    "SessionMessage",
    "SessionIndexEntry",
    "SessionIndex",
    "SessionQuery",
]
