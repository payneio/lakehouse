"""V3 Profile compilation service.

Compiles v3 profile definitions into mount plans for the Amplifier system.
Uses the same algorithm as compile_profile.py with all stages.
"""

import json
import logging
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from amplifier_library.services.registry_service import RegistryService
from amplifierd.services.ref_resolution import RefResolutionService

logger = logging.getLogger(__name__)


class ProfileCompilationError(Exception):
    """Raised when profile compilation fails."""


@dataclass
class ComponentRefInternal:
    """Internal component reference during compilation."""

    id: str
    type: str
    behavior_id: str | None = None
    source: str | None = None
    config: dict[str, Any] | None = None


class ProfileCompilationService:
    """Service for compiling v3 profiles.

    Compiles profile YAML + config YAML into mount plans following v3 spec.
    Uses behavior-based composition with dependency resolution.
    """

    def __init__(
        self,
        share_dir: Path,
        cache_dir: Path,
        ref_resolution: RefResolutionService,
        registry_service: RegistryService,
    ):
        """Initialize profile compilation service.

        Args:
            share_dir: Share directory (compiled profiles output here)
            cache_dir: Cache directory (for intermediate assets)
            ref_resolution: RefResolutionService for downloading refs
            registry_service: RegistryService for amp:// URI resolution
        """
        self.share_dir = Path(share_dir)
        self.cache_dir = Path(cache_dir)
        self.ref_resolution = ref_resolution
        self.registry_service = registry_service
        self.logger = logging.getLogger(__name__)

    def compile_profile(self, profile_id: str, profile_yaml: dict, config_yaml: dict) -> Path:
        """Compile v3 profile to share/profiles/{profile_id}/.

        Args:
            profile_id: Profile identifier (e.g., "software-developer")
            profile_yaml: Parsed profile YAML dictionary
            config_yaml: Parsed config YAML dictionary

        Returns:
            Path to compiled profile directory

        Raises:
            ProfileCompilationError: If compilation fails
        """
        try:
            self.logger.info(f"Compiling profile '{profile_id}'")

            # Load registries
            registries = self.registry_service.load_registries()

            # Stage 1: Load behavior definitions (recursive)
            behavior_items = profile_yaml.get("behaviors", [])
            behavior_defs = {}
            if behavior_items:
                self.logger.info(f"Loading {len(behavior_items)} behavior definitions...")
                behavior_defs = self._load_behavior_definitions(behavior_items, registries)

            # Stage 2: Topological sort
            all_behavior_ids = list(behavior_defs.keys())
            sorted_behaviors = self._topological_sort_behaviors(all_behavior_ids, behavior_defs)

            # Stage 3: Collect components
            self.logger.info("Collecting components...")
            refs = self._collect_components(profile_yaml, behavior_defs)
            self.logger.info(f"Found {len(refs)} components")

            # Stage 4: Resolve assets
            self.logger.info("Resolving assets...")
            asset_map = self._resolve_assets(refs, registries)

            # Stage 5: Copy to profile cache
            profile_dir = self.share_dir / "profiles" / profile_id
            self.logger.info("Copying components to profile cache...")
            asset_map = self._copy_to_profile_cache(profile_yaml, asset_map, refs, profile_dir)

            # Stage 6: Merge configs
            self.logger.info("Merging configurations...")
            behavior_configs = config_yaml.get("behaviors", {})
            if not isinstance(behavior_configs, dict):
                behavior_configs = {}
            merged_config = self._merge_configs(config_yaml, behavior_configs, sorted_behaviors)

            # Stage 7: Generate mount plan
            self.logger.info("Generating mount plan...")
            mount_plan = self._generate_mount_plan(
                profile_yaml, merged_config, asset_map, behavior_defs, sorted_behaviors
            )

            # Stage 8: Save mount plan
            mount_plan_path = profile_dir / "mount_plan.json"
            mount_plan_path.write_text(json.dumps(mount_plan, indent=2))

            self.logger.info(f"✓ Profile '{profile_id}' compiled successfully")
            return profile_dir

        except Exception as e:
            self.logger.error(f"Profile compilation failed: {e}")
            raise ProfileCompilationError(f"Failed to compile profile '{profile_id}': {e}") from e

    def _load_behavior_definitions(
        self, behavior_items: list[str | dict], registries: dict[str, Any]
    ) -> dict[str, Any]:
        """Load behavior definition files, recursively loading dependencies.

        Args:
            behavior_items: List of behavior items from profile (dict with id/source)
            registries: Dictionary of available registries

        Returns:
            Dictionary mapping behavior ID to its parsed definition

        Raises:
            ProfileCompilationError: If behavior definition not found or invalid
        """
        behavior_defs = {}
        to_process = list(behavior_items)
        processed = set()

        while to_process:
            behavior_item = to_process.pop(0)

            # Parse behavior item (object format only)
            if not isinstance(behavior_item, dict):
                raise ProfileCompilationError(
                    f"Behavior must be dict with 'id' and 'source', got {type(behavior_item)}: {behavior_item}"
                )

            behavior_id = behavior_item.get("id")
            if not behavior_id:
                raise ProfileCompilationError(f"Behavior must have 'id' field: {behavior_item}")

            source_ref = behavior_item.get("source")

            if behavior_id in processed:
                continue

            processed.add(behavior_id)

            # Require explicit source in component
            if not source_ref:
                raise ProfileCompilationError(
                    f"Behavior '{behavior_id}' has no source. Behaviors must include 'source' field in YAML."
                )

            try:
                # Resolve amp:// URIs before fetching
                resolved_uri = self.registry_service.resolve_amp_uri(source_ref)
                self.logger.info(f"Loading behavior definition for '{behavior_id}' from {resolved_uri}")
                resolved_path = self.ref_resolution.resolve_ref(resolved_uri)

                if resolved_path.is_file():
                    behavior_content = resolved_path.read_text()
                elif resolved_path.is_dir():
                    possible_files = [
                        resolved_path / f"{behavior_id}.yaml",
                        resolved_path / "behavior.yaml",
                    ]
                    behavior_file = next((f for f in possible_files if f.exists()), None)
                    if not behavior_file:
                        raise ProfileCompilationError(
                            f"Could not find behavior YAML for '{behavior_id}' in directory: {resolved_path}"
                        )
                    behavior_content = behavior_file.read_text()
                else:
                    raise ProfileCompilationError(f"Unexpected path type for behavior '{behavior_id}': {resolved_path}")

                behavior_def = yaml.safe_load(behavior_content)

                if "behavior" in behavior_def:
                    behavior_metadata = behavior_def["behavior"]
                    behavior_defs[behavior_id] = {
                        **behavior_def,
                        "behavior": behavior_metadata,
                        "requires": behavior_metadata.get("requires", []),
                    }
                else:
                    behavior_defs[behavior_id] = behavior_def

                requires = behavior_defs[behavior_id].get("requires", [])
                if isinstance(requires, list):
                    for required_item in requires:
                        # Expect object format with id/source
                        if not isinstance(required_item, dict):
                            raise ProfileCompilationError(
                                f"Behavior dependency must be dict with 'id' and 'source', got: {required_item}"
                            )

                        req_behavior_id = required_item.get("id")
                        if not req_behavior_id:
                            raise ProfileCompilationError(f"Behavior dependency must have 'id' field: {required_item}")

                        req_obj = required_item

                        if req_behavior_id not in processed and req_behavior_id not in [
                            b.get("id") for b in to_process if isinstance(b, dict)
                        ]:
                            self.logger.debug(f"  Queueing required behavior: {req_behavior_id}")
                            to_process.append(req_obj)

            except Exception as e:
                raise ProfileCompilationError(
                    f"Failed to load behavior '{behavior_id}' from '{source_ref}': {e}"
                ) from e

        return behavior_defs

    def _parse_component_ref(
        self, item: dict | str, component_type: str, behavior_id: str | None = None
    ) -> ComponentRefInternal:
        """Parse a component reference from YAML (object or string format).

        Args:
            item: Component dict with id/source/config, OR plain string URI
            component_type: Type of component (tools, agents, hooks, etc.)
            behavior_id: Behavior this component belongs to (if any)

        Returns:
            ComponentRefInternal object

        Raises:
            ProfileCompilationError: If component format is invalid
        """
        # Handle string format (backward compatible)
        if isinstance(item, str):
            # Extract ID from URI (e.g., "amp://microsoft/tools/tool-bash" -> "tool-bash")
            filename = item.split("/")[-1]
            component_id = filename.removesuffix(".yaml").removesuffix(".md")
            return ComponentRefInternal(
                id=component_id,
                type=component_type,
                behavior_id=behavior_id,
                source=item,
                config=None,
            )

        # Handle dict format
        if not isinstance(item, dict):
            raise ProfileCompilationError(f"Component must be dict or string, got {type(item)}: {item}")

        component_id = item.get("id")
        component_source = item.get("source")

        if not component_id and component_source:
            # Extract ID from source (e.g., "amp://microsoft/tools/tool-bash" -> "tool-bash")
            filename = component_source.split("/")[-1]
            component_id = filename.removesuffix(".yaml").removesuffix(".md")

        if not component_id:
            raise ProfileCompilationError(f"Component must have 'id' field or 'source' to extract ID from: {item}")

        return ComponentRefInternal(
            id=component_id,
            type=component_type,
            behavior_id=behavior_id,
            source=component_source,
            config=item.get("config"),
        )

    def _topological_sort_behaviors(self, behaviors: list[str], behavior_defs: dict[str, Any]) -> list[str]:
        """Sort behaviors by dependency order using Kahn's algorithm.

        Args:
            behaviors: List of behavior IDs from the profile
            behavior_defs: Dictionary mapping behavior ID to its definition (including requires)

        Returns:
            List of behavior IDs in dependency order

        Raises:
            ProfileCompilationError: If circular dependency detected
        """
        if not behaviors:
            return []

        graph = {}
        in_degree = {}

        for behavior_id in behaviors:
            behavior_def = behavior_defs.get(behavior_id, {})
            requires = behavior_def.get("requires", [])
            raw_deps = requires if isinstance(requires, list) else [requires] if requires else []

            # Normalize dependencies (extract IDs from objects or URIs)
            normalized_deps = []
            for dep in raw_deps:
                if isinstance(dep, dict):
                    # Extract ID from dict object
                    dep_id = dep.get("id")
                    if dep_id:
                        normalized_deps.append(dep_id)
                elif isinstance(dep, str) and dep.startswith("amp://"):
                    # Extract behavior ID from URI
                    filename = dep.split("/")[-1]
                    dep_id = filename.removesuffix(".yaml")
                    normalized_deps.append(dep_id)
                elif isinstance(dep, str):
                    normalized_deps.append(dep)

            graph[behavior_id] = normalized_deps
            in_degree[behavior_id] = 0

        for behavior_id in behaviors:
            for dep in graph[behavior_id]:
                if dep not in in_degree:
                    raise ProfileCompilationError(
                        f"Behavior '{behavior_id}' requires unknown behavior '{dep}'. "
                        f"Available behaviors: {', '.join(behaviors)}"
                    )
                in_degree[behavior_id] += 1

        queue = [bid for bid in behaviors if in_degree[bid] == 0]
        sorted_ids = []

        while queue:
            bid = queue.pop(0)
            sorted_ids.append(bid)

            for other_bid in behaviors:
                if bid in graph[other_bid]:
                    in_degree[other_bid] -= 1
                    if in_degree[other_bid] == 0:
                        queue.append(other_bid)

        if len(sorted_ids) != len(behaviors):
            remaining = set(behaviors) - set(sorted_ids)
            raise ProfileCompilationError(
                f"Circular dependency detected in behaviors: {', '.join(remaining)}. Check the 'requires' fields."
            )

        return sorted_ids

    def _collect_components(self, profile: dict, behavior_defs: dict[str, Any]) -> list[ComponentRefInternal]:
        """Extract all component IDs from profile in dependency order.

        Args:
            profile: Profile YAML dictionary
            behavior_defs: Dictionary of loaded behavior definitions

        Returns:
            List of ComponentRefInternal objects in dependency order
        """
        refs = []

        # Profile-level components (use new parser)
        if orch := profile.get("orchestrator"):
            refs.append(self._parse_component_ref(orch, "orchestrator"))
        if ctx := profile.get("context"):
            refs.append(self._parse_component_ref(ctx, "context"))
        if provs := profile.get("providers"):
            for prov in provs:
                # Providers are lists of objects with 'id' and 'source'
                refs.append(self._parse_component_ref(prov, "providers"))
        if ctxs := profile.get("contexts"):
            for ctx in ctxs:
                refs.append(self._parse_component_ref(ctx, "contexts"))

        # Behavior components (use new parser with behavior_id)
        all_behavior_ids = list(behavior_defs.keys())
        if all_behavior_ids:
            sorted_behaviors = self._topological_sort_behaviors(all_behavior_ids, behavior_defs)

            for behavior_id in sorted_behaviors:
                behavior_def = behavior_defs.get(behavior_id, {})

                for hook in behavior_def.get("hooks", []):
                    refs.append(self._parse_component_ref(hook, "hooks", behavior_id))
                for agent in behavior_def.get("agents", []):
                    refs.append(self._parse_component_ref(agent, "agents", behavior_id))
                for ctx in behavior_def.get("contexts", []):
                    refs.append(self._parse_component_ref(ctx, "contexts", behavior_id))
                for tool in behavior_def.get("tools", []):
                    refs.append(self._parse_component_ref(tool, "tools", behavior_id))

        return refs

    def _resolve_assets(self, refs: list[ComponentRefInternal], registries: dict[str, Any]) -> dict[str, Path]:
        """Download/cache all assets and return local paths.

        All component sources are inline in ComponentRefInternal objects.

        Args:
            refs: List of component references (each has inline source)
            registries: Dictionary of available registries

        Returns:
            Dictionary mapping component IDs to local file paths

        Raises:
            ProfileCompilationError: If component has no source or download fails
        """
        asset_map = {}

        for ref in refs:
            if not ref.source:
                raise ProfileCompilationError(
                    f"Component '{ref.id}' (type: {ref.type}) has no source. Components must include 'source' field."
                )

            try:
                # Resolve amp:// URIs before fetching
                resolved_uri = self.registry_service.resolve_amp_uri(ref.source)

                self.logger.info(f"Resolving {ref.type} '{ref.id}' from {resolved_uri}")
                resolved_path = self.ref_resolution.resolve_ref(resolved_uri)
                asset_map[ref.id] = resolved_path
                self.logger.debug(f"  → {resolved_path}")
            except Exception as e:
                raise ProfileCompilationError(
                    f"Failed to resolve component '{ref.id}' from source '{ref.source}': {e}"
                ) from e

        return asset_map

    def _copy_to_profile_cache(
        self, profile: dict, asset_map: dict[str, Path], refs: list[ComponentRefInternal], cache_dir: Path
    ) -> dict[str, Path]:
        """Copy all components to profile-specific cache for self-contained profiles.

        Args:
            profile: Profile YAML dictionary
            asset_map: Mapping of component IDs to their cached locations
            refs: List of all component references
            cache_dir: Profile output directory (not .cache/)

        Returns:
            Updated asset_map with profile cache paths
        """
        self.logger.info(f"Creating self-contained profile cache at {cache_dir}")
        cache_dir.mkdir(parents=True, exist_ok=True)

        profile_asset_map = {}

        for ref in refs:
            if ref.id not in asset_map:
                self.logger.warning(f"Component '{ref.id}' not in asset map, skipping")
                continue

            source_path = asset_map[ref.id]

            # Determine destination based on behavior_id
            if ref.behavior_id:
                # Behavior component: profiles/{name}/behaviors/{behavior-id}/{type}/{id}/
                dest_path = cache_dir / "behaviors" / ref.behavior_id / ref.type / ref.id
            else:
                # Session component: profiles/{name}/session/{type}/{id}/
                dest_path = cache_dir / "session" / ref.type / ref.id

            # Copy component to profile cache
            try:
                if dest_path.exists():
                    self.logger.debug(f"Profile cache path exists, skipping: {dest_path}")
                else:
                    dest_path.parent.mkdir(parents=True, exist_ok=True)

                    if source_path.is_dir():
                        shutil.copytree(source_path, dest_path)
                        self.logger.debug(f"Copied directory: {ref.id} -> {dest_path}")
                    else:
                        dest_path.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(source_path, dest_path / source_path.name)
                        self.logger.debug(f"Copied file: {ref.id} -> {dest_path}")

                profile_asset_map[ref.id] = dest_path

            except Exception as e:
                self.logger.error(f"Failed to copy component '{ref.id}' to profile cache: {e}")
                # Fall back to shared cache path
                profile_asset_map[ref.id] = source_path

        self.logger.info(f"Profile cache complete with {len(profile_asset_map)} components")
        return profile_asset_map

    def _deep_merge(self, base: dict, override: dict) -> dict:
        """Recursively merge two dicts (lists are replaced, dicts merged).

        Args:
            base: Base dictionary
            override: Override dictionary

        Returns:
            Merged dictionary
        """
        result = dict(base)
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    def _merge_configs(
        self, root_config: dict, behavior_configs: dict[str, Any], sorted_behavior_ids: list[str]
    ) -> dict:
        """Merge root + behavior configs in dependency order.

        Args:
            root_config: Root configuration from config.yaml
            behavior_configs: Dictionary of behavior configs
            sorted_behavior_ids: Behavior IDs in dependency order

        Returns:
            Merged configuration dictionary
        """
        # Start with root config (excluding behavior-specific section)
        merged = {}
        for key, value in root_config.items():
            if key != "behaviors":  # Skip behavior-specific configs
                merged[key] = value

        # Merge behavior-specific configs in dependency order
        for behavior_id in sorted_behavior_ids:
            behavior_config = behavior_configs.get(behavior_id, {})
            if "config" in behavior_config:
                merged = self._deep_merge(merged, behavior_config["config"])

        return merged

    def _generate_mount_plan(
        self,
        profile: dict,
        config: dict,
        asset_map: dict[str, Path],
        behavior_defs: dict[str, Any],
        sorted_behavior_ids: list[str],
    ) -> dict:
        """Build final mount plan from profile, config, and assets.

        Args:
            profile: Profile YAML dictionary
            config: Merged configuration dictionary
            asset_map: Dictionary mapping component IDs to local paths (profile cache)
            behavior_defs: Dictionary of loaded behavior definitions
            sorted_behavior_ids: Behavior IDs in dependency order

        Returns:
            Mount plan dictionary ready for JSON serialization
        """
        self.logger.debug(f"Generating mount plan with {len(asset_map)} components from profile cache")

        mount_plan: dict[str, Any] = {}

        # Get profile name for source field
        profile_name = profile.get("profile", {}).get("name", "unknown")

        # Get working_dir from config
        working_dir = config.get("session", {}).get("working_dir", "")

        # Session section - orchestrator and context are DICT objects with module/source/config
        session: dict[str, Any] = {}
        session_config = config.get("session", {})

        if orch_ref := profile.get("orchestrator"):
            # Extract ID from ref (could be dict with id/source or just dict with source)
            if isinstance(orch_ref, dict):
                orch_id = orch_ref.get("id")
                if not orch_id and orch_ref.get("source"):
                    # Extract from source
                    filename = orch_ref["source"].split("/")[-1]
                    orch_id = filename.removesuffix(".yaml").removesuffix(".md")
            else:
                orch_id = orch_ref

            session["orchestrator"] = {
                "module": orch_id,
                "source": profile_name,
                "config": session_config.get("orchestrator", {}),
            }

        if ctx_ref := profile.get("context"):
            if isinstance(ctx_ref, dict):
                ctx_id = ctx_ref.get("id")
                if not ctx_id and ctx_ref.get("source"):
                    filename = ctx_ref["source"].split("/")[-1]
                    ctx_id = filename.removesuffix(".yaml").removesuffix(".md")
            else:
                ctx_id = ctx_ref

            session["context"] = {"module": ctx_id, "source": profile_name, "config": session_config.get("context", {})}

        # Session-level settings
        session["injection_size_limit"] = session_config.get("injection_size_limit")
        session["injection_budget_per_turn"] = session_config.get("injection_budget_per_turn")

        session["settings"] = {
            "amplified_dir": working_dir,
            "session_cwd": working_dir,
            "profile_name": profile_name,
        }

        mount_plan["session"] = session

        # Providers section - list of objects with module/source/config
        if provs := profile.get("providers"):
            providers = []
            providers_config = config.get("providers", {})

            # Build config map
            provider_config_map = {}
            if isinstance(providers_config, dict):
                provider_config_map = providers_config
            elif isinstance(providers_config, list):
                for prov_conf in providers_config:
                    if isinstance(prov_conf, dict):
                        for prov_id, prov_settings in prov_conf.items():
                            provider_config_map[prov_id] = prov_settings

            for prov_item in provs:
                if isinstance(prov_item, dict):
                    prov_id = prov_item.get("id")
                else:
                    prov_id = prov_item

                providers.append(
                    {"module": prov_id, "source": profile_name, "config": provider_config_map.get(prov_id, {})}
                )

            mount_plan["providers"] = providers

        # Tools section - list of objects with module/source/config
        seen_tools = set()
        all_tools = []
        for behavior_id in sorted_behavior_ids:
            behavior_def = behavior_defs.get(behavior_id, {})
            for tool_item in behavior_def.get("tools", []):
                # Extract tool ID from dict object or string URI
                if isinstance(tool_item, dict):
                    tool_id = tool_item.get("id")
                elif isinstance(tool_item, str):
                    # Extract from URI
                    filename = tool_item.split("/")[-1]
                    tool_id = filename.removesuffix(".yaml").removesuffix(".md")
                else:
                    continue  # Skip invalid items

                if tool_id in seen_tools:
                    continue
                seen_tools.add(tool_id)

                # Build tool config
                tool_config = {"working_dir": working_dir} if working_dir else {}
                for key, value in config.items():
                    if key.startswith(f"{tool_id}."):
                        tool_config[key.split(".", 1)[1]] = value

                all_tools.append({"module": tool_id, "source": profile_name, "config": tool_config})

        if all_tools:
            mount_plan["tools"] = all_tools

        # Hooks section - list of objects with module/source/config
        seen_hooks = set()
        all_hooks = []
        for behavior_id in sorted_behavior_ids:
            behavior_def = behavior_defs.get(behavior_id, {})
            for hook_item in behavior_def.get("hooks", []):
                # Extract hook ID from dict object or string URI
                if isinstance(hook_item, dict):
                    hook_id = hook_item.get("id")
                elif isinstance(hook_item, str):
                    # Extract from URI
                    filename = hook_item.split("/")[-1]
                    hook_id = filename.removesuffix(".yaml").removesuffix(".md")
                else:
                    continue  # Skip invalid items

                if hook_id in seen_hooks:
                    continue
                seen_hooks.add(hook_id)

                # Build hook config
                hook_config = {}
                for key, value in config.items():
                    if key.startswith(f"hook.{hook_id}."):
                        hook_config[key.split(".", 2)[2]] = value

                all_hooks.append({"module": hook_id, "source": profile_name, "config": hook_config})

        if all_hooks:
            mount_plan["hooks"] = all_hooks

        # Agents section - content/metadata format (already correct)
        agents_obj = {}
        for behavior_id in sorted_behavior_ids:
            behavior_def = behavior_defs.get(behavior_id, {})
            for agent_item in behavior_def.get("agents", []):
                # Extract agent ID from dict object or string URI
                agent_id: str | None = None
                if isinstance(agent_item, dict):
                    agent_id = agent_item.get("id")
                elif isinstance(agent_item, str):
                    # Extract from URI
                    filename = agent_item.split("/")[-1]
                    agent_id = filename.removesuffix(".yaml").removesuffix(".md")
                else:
                    continue  # Skip invalid items

                if not agent_id:
                    continue  # Skip if no ID extracted

                agent_path = asset_map[agent_id]

                if agent_path.is_file():
                    agent_content = agent_path.read_text()
                else:
                    possible_files = [agent_path / f"{agent_id}.md", agent_path / "agent.md", agent_path / "README.md"]
                    agent_file = next((f for f in possible_files if f.exists()), None)
                    if not agent_file:
                        raise ProfileCompilationError(
                            f"Could not find agent file for '{agent_id}' in directory: {agent_path}"
                        )
                    agent_content = agent_file.read_text()

                agents_obj[agent_id] = {
                    "content": agent_content,
                    "metadata": {"source": f"{profile['profile']['name']}:agents/{agent_id}.md"},
                }

        if agents_obj:
            mount_plan["agents"] = agents_obj

        return mount_plan
