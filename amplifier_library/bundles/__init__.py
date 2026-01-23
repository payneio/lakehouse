"""Bundle management for Lakehouse.

Provides LakehouseBundleManager that wraps Foundation's BundleRegistry
to integrate bundle loading with Lakehouse's session management.
"""

from amplifier_library.bundles.manager import LakehouseBundleManager

__all__ = ["LakehouseBundleManager"]
