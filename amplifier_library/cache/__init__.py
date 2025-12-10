"""Cache management for amplifier resources.

This module provides all cache functionality for collections and profiles:
- Metadata storage and retrieval
- Cache status queries
- Change detection
- Cache update operations

Architecture: All business logic in library, daemon provides thin HTTP wrappers.
"""

# Services
from .detection import ChangeDetectionService
from .metadata_store import MetadataStore
from .status import StatusService
from .updates import UpdateService

# Models - Metadata
from .models import CollectionMetadata
from .models import ProfileDependency
from .models import ProfileMetadata

# Models - Change Detection
from .models import ChangeReport
from .models import DependencyChange
from .models import ManifestChange
from .models import SourceChange

# Models - Status and Results (API responses)
from .models import AllCacheStatus
from .models import AllUpdateResult
from .models import CacheTimestamps
from .models import CollectionCacheStatus
from .models import CollectionUpdateResult
from .models import ProfileCacheStatus
from .models import ProfileUpdateResult
from .models import UpdateResult

__all__ = [
    # Services
    "MetadataStore",
    "StatusService",
    "ChangeDetectionService",
    "UpdateService",
    # Metadata models
    "CollectionMetadata",
    "ProfileMetadata",
    "ProfileDependency",
    # Change detection models
    "SourceChange",
    "ManifestChange",
    "DependencyChange",
    "ChangeReport",
    # Status and result models
    "CacheTimestamps",
    "ProfileCacheStatus",
    "CollectionCacheStatus",
    "AllCacheStatus",
    "UpdateResult",
    "ProfileUpdateResult",
    "CollectionUpdateResult",
    "AllUpdateResult",
]
