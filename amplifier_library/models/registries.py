"""Registry models for v3 profile system."""

from pydantic import BaseModel


class Registry(BaseModel):
    """Registry definition.

    A registry is a named collection of components that can be referenced
    using amp:// URIs in profiles.

    Attributes:
        id: Short identifier used in amp:// URIs (e.g., "microsoft", "lakehouse")
        uri: Full URI to registry location (git+, file://, or fsspec-compatible)
        description: Human-readable description of the registry
    """

    id: str
    uri: str
    description: str = ""


class RegistriesConfig(BaseModel):
    """Container for registry definitions loaded from registries.yaml."""

    registries: list[Registry]
