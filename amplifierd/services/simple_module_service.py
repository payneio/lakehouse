"""Simple module discovery service.

Scans flat modules directory, detects module types from path structure,
and reads metadata from module.yaml files.
"""

import logging
from dataclasses import dataclass
from pathlib import Path

import yaml

from amplifierd.models.modules import ModuleDetails
from amplifierd.models.modules import ModuleInfo

logger = logging.getLogger(__name__)


@dataclass
class ModuleMetadata:
    """Internal representation of module metadata."""

    name: str
    version: str
    description: str | None = None
    entry_point: str | None = None
    config_schema: dict[str, object] | None = None


class SimpleModuleService:
    """Simple module discovery service.

    Scans flat modules directory for modules organized by collection:
    - modules/{collection}/providers/{name}/
    - modules/{collection}/tools/{name}/
    - modules/{collection}/hooks/{name}/
    - modules/{collection}/orchestrators/{name}/

    Module ID format: {collection}/{type}/{name}
    """

    def __init__(self, share_dir: Path) -> None:
        """Initialize module service.

        Args:
            share_dir: Root share directory containing modules/
        """
        self.share_dir = Path(share_dir)
        self.modules_dir = self.share_dir / "modules"
        logger.info(f"SimpleModuleService initialized with share_dir={self.share_dir}")

    def list_modules(self, type_filter: str | None = None) -> list[ModuleInfo]:
        """List all modules, optionally filtered by type.

        Args:
            type_filter: Optional module type to filter by (provider, tool, hook, orchestrator)

        Returns:
            List of ModuleInfo objects
        """
        modules = []
        valid_types = ["providers", "tools", "hooks", "orchestrators"]

        if not self.modules_dir.exists():
            logger.warning(f"Modules directory does not exist: {self.modules_dir}")
            return modules

        for collection_dir in self.modules_dir.iterdir():
            if not collection_dir.is_dir() or collection_dir.name.startswith("."):
                continue

            collection_name = collection_dir.name

            for type_dir in collection_dir.iterdir():
                if not type_dir.is_dir() or type_dir.name not in valid_types:
                    continue

                module_type = type_dir.name.rstrip("s")
                if type_filter and module_type != type_filter:
                    continue

                for module_dir in type_dir.iterdir():
                    if not module_dir.is_dir() or module_dir.name.startswith("."):
                        continue

                    module_yaml = module_dir / "module.yaml"
                    if not module_yaml.exists():
                        logger.debug(f"Skipping module without module.yaml: {module_dir}")
                        continue

                    try:
                        metadata = self._load_module_metadata(module_yaml)
                        module_id = f"{collection_name}/{module_type}/{module_dir.name}"

                        modules.append(
                            ModuleInfo(
                                id=module_id,
                                type=module_type,
                                name=metadata.name,
                                location=str(module_dir),
                                collection=collection_name,
                            )
                        )
                    except Exception as e:
                        logger.error(f"Error loading module {module_dir}: {e}")

        logger.info(f"Found {len(modules)} modules (type_filter={type_filter})")
        return modules

    def get_module(self, module_id: str) -> ModuleDetails:
        """Get detailed information about a specific module.

        Args:
            module_id: Module identifier in format {collection}/{type}/{name}

        Returns:
            ModuleDetails object

        Raises:
            ValueError: If module_id format is invalid
            FileNotFoundError: If module does not exist
        """
        parts = module_id.split("/")
        if len(parts) != 3:
            raise ValueError(f"Invalid module ID format: {module_id}. Expected: collection/type/name")

        collection, module_type, module_name = parts
        type_plural = f"{module_type}s"
        module_dir = self.modules_dir / collection / type_plural / module_name

        if not module_dir.exists():
            raise FileNotFoundError(f"Module not found: {module_id}")

        module_yaml = module_dir / "module.yaml"
        if not module_yaml.exists():
            raise FileNotFoundError(f"Module metadata not found: {module_yaml}")

        metadata = self._load_module_metadata(module_yaml)

        return ModuleDetails(
            id=module_id,
            type=module_type,
            name=metadata.name,
            location=str(module_dir),
            collection=collection,
            description=metadata.description,
            config_schema=metadata.config_schema,
        )

    def _load_module_metadata(self, yaml_path: Path) -> ModuleMetadata:
        """Load module metadata from module.yaml file.

        Args:
            yaml_path: Path to module.yaml file

        Returns:
            ModuleMetadata object

        Raises:
            ValueError: If YAML is invalid or missing required fields
        """
        try:
            with open(yaml_path) as f:
                data = yaml.safe_load(f)

            if not data or not isinstance(data, dict):
                raise ValueError(f"Invalid module.yaml: {yaml_path}")

            if "name" not in data:
                raise ValueError(f"Missing required field 'name' in {yaml_path}")

            return ModuleMetadata(
                name=data["name"],
                version=data.get("version", "0.0.0"),
                description=data.get("description"),
                entry_point=data.get("entry_point"),
                config_schema=data.get("config_schema"),
            )
        except yaml.YAMLError as e:
            raise ValueError(f"Failed to parse YAML file {yaml_path}: {e}")
