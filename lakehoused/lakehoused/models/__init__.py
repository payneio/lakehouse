"""API models for lakehoused daemon.

This module defines request and response models for the REST API.
"""

from .assistants import AssistantDetails
from .assistants import AssistantListItem
from .assistants import AssistantSource
from .assistants import CopyAssistantRequest
from .assistants import CreateAssistantRequest
from .assistants import ModuleRef
from .assistants import ResolvedAssistant
from .assistants import ResolvedModuleRef
from .assistants import UpdateAssistantRequest
from .errors import ErrorResponse
from .errors import ValidationErrorDetail
from .projects import AgentsContentResponse
from .projects import AgentsContentUpdate
from .projects import Project
from .projects import ProjectCreate
from .projects import ProjectList
from .projects import ProjectUpdate
from .requests import SendMessageRequest
from .requests import UpdateContextRequest
from .responses import MessageResponse
from .responses import StatusResponse
from .responses import TranscriptResponse
from .sessions import SessionIndex
from .sessions import SessionIndexEntry
from .sessions import SessionMessage
from .sessions import SessionMetadata
from .sessions import SessionQuery
from .sessions import SessionStatus

__all__ = [
    # Assistant models
    "AssistantListItem",
    "AssistantDetails",
    "AssistantSource",
    "ResolvedAssistant",
    "ResolvedModuleRef",
    "ModuleRef",
    "CreateAssistantRequest",
    "CopyAssistantRequest",
    "UpdateAssistantRequest",
    # Project models
    "Project",
    "ProjectCreate",
    "ProjectUpdate",
    "ProjectList",
    "AgentsContentUpdate",
    "AgentsContentResponse",
    # Session requests
    "SendMessageRequest",
    "UpdateContextRequest",
    # Errors
    "ErrorResponse",
    "ValidationErrorDetail",
    # Responses
    "MessageResponse",
    "StatusResponse",
    "TranscriptResponse",
    # Sessions
    "SessionStatus",
    "SessionMetadata",
    "SessionMessage",
    "SessionIndexEntry",
    "SessionIndex",
    "SessionQuery",
]
