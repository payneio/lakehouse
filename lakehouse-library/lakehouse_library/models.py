"""Shared data models for amplifier_library.

This module defines data structures used across the library layer.

Contract:
- Inputs: Raw data for model construction
- Outputs: Validated model instances
- Side Effects: None (pure data structures)
"""

from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from typing import Any


@dataclass
class Session:
    """Session data model.

    Represents an active conversation session with context and history.

    Attributes:
        id: Unique session identifier
        profile: Profile name this session belongs to
        context: Session-specific context data
        created_at: Session creation timestamp
        updated_at: Last update timestamp
        message_count: Number of messages in session

    Example:
        >>> session = Session(
        ...     id="test-123",
        ...     profile="default",
        ...     context={},
        ...     created_at=datetime.now(),
        ...     updated_at=datetime.now(),
        ...     message_count=0
        ... )
        >>> assert session.id == "test-123"
    """

    id: str
    profile: str
    context: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    message_count: int = 0


@dataclass
class SessionInfo:
    """Session metadata for listing.

    Lightweight version of Session for listing operations.

    Attributes:
        id: Unique session identifier
        profile: Profile name
        created_at: Creation timestamp
        updated_at: Last update timestamp
        message_count: Number of messages

    Example:
        >>> info = SessionInfo(
        ...     id="test-123",
        ...     profile="default",
        ...     created_at=datetime.now(),
        ...     updated_at=datetime.now(),
        ...     message_count=5
        ... )
        >>> assert info.message_count == 5
    """

    id: str
    profile: str
    created_at: datetime
    updated_at: datetime
    message_count: int


@dataclass
class Message:
    """Message in a session.

    Attributes:
        role: Message role (user, assistant, system)
        content: Message content
        timestamp: Message timestamp
        metadata: Optional message metadata

    Example:
        >>> msg = Message(
        ...     role="user",
        ...     content="Hello",
        ...     timestamp=datetime.now()
        ... )
        >>> assert msg.role == "user"
    """

    role: str
    content: str
    timestamp: datetime
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Profile:
    """User profile configuration.

    Attributes:
        name: Profile name (unique identifier)
        display_name: Human-readable display name
        config: Profile-specific configuration
        created_at: Profile creation timestamp
        updated_at: Last update timestamp

    Example:
        >>> profile = Profile(
        ...     name="default",
        ...     display_name="Default Profile",
        ...     config={},
        ...     created_at=datetime.now(),
        ...     updated_at=datetime.now()
        ... )
        >>> assert profile.name == "default"
    """

    name: str
    display_name: str
    config: dict[str, Any]
    created_at: datetime
    updated_at: datetime
