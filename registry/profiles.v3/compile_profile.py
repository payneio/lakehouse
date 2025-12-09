#!/usr/bin/env python3
"""V3 Profile Compiler

Compiles v3 profile definitions into mount plans for the Amplifier system.

Usage:
    python compile_profile.py <profile.yaml> <config.yaml> <SOURCES.txt> <output.json>

Example:
    python compile_profile.py software-developer.yaml config.yaml SOURCES.txt output.json
"""

import json
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

# Add parent directories to path to import from amplifierd
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "amplifierd"))

from amplifierd.services.ref_resolution import RefResolutionService

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class ComponentRef:
    """Reference to a component with its type and optional behavior context"""

    id: str
    type: str  # 'orchestrator', 'context', 'provider', 'tool', 'agent', 'hook'
    behavior_id: str | None = None


class ProfileCompilationError(Exception):
    """Raised when profile compilation fails"""


def load_behavior_definitions(
    behavior_ids: list[str], sources: dict[str, str], resolver: RefResolutionService
) -> dict[str, Any]:
    """Load behavior definition files, recursively loading dependencies.

    Args:
        behavior_ids: List of behavior IDs from profile
        sources: Dictionary mapping component IDs to source references
        resolver: RefResolutionService for downloading assets

    Returns:
        Dictionary mapping behavior ID to its parsed definition

    Raises:
        ProfileCompilationError: If behavior definition not found or invalid
    """
    behavior_defs = {}
    to_process = list(behavior_ids)
    processed = set()

    while to_process:
        behavior_id = to_process.pop(0)

        if behavior_id in processed:
            continue

        processed.add(behavior_id)

        source_ref = None
        if behavior_id in sources:
            source_ref = sources[behavior_id]
        elif f"behaviors.{behavior_id}" in sources:
            source_ref = sources[f"behaviors.{behavior_id}"]

        if not source_ref:
            raise ProfileCompilationError(
                f"Behavior '{behavior_id}' not found in SOURCES.txt. "
                f"Please add an entry like: behaviors.{behavior_id} <path>"
            )

        try:
            logger.info(f"Loading behavior definition for '{behavior_id}' from {source_ref}")
            resolved_path = resolver.resolve_ref(source_ref)

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
                for required_behavior in requires:
                    if required_behavior not in processed and required_behavior not in to_process:
                        logger.debug(f"  Queueing required behavior: {required_behavior}")
                        to_process.append(required_behavior)

        except Exception as e:
            raise ProfileCompilationError(f"Failed to load behavior '{behavior_id}' from '{source_ref}': {e}") from e

    return behavior_defs


def topological_sort_behaviors(behaviors: list[str], behavior_defs: dict[str, Any]) -> list[str]:
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
        graph[behavior_id] = requires if isinstance(requires, list) else [requires] if requires else []
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
            f"Circular dependency detected in behaviors: {', '.join(remaining)}. " f"Check the 'requires' fields."
        )

    return sorted_ids


def collect_components(profile: dict, behavior_defs: dict[str, Any]) -> list[ComponentRef]:
    """Extract all component IDs from profile in dependency order.

    Args:
        profile: Profile YAML dictionary
        behavior_defs: Dictionary of loaded behavior definitions

    Returns:
        List of ComponentRef objects in dependency order
    """
    refs = []

    if orch := profile.get("orchestrator"):
        refs.append(ComponentRef(orch, "orchestrator"))
    if ctx := profile.get("context"):
        refs.append(ComponentRef(ctx, "context"))
    if provs := profile.get("providers"):
        refs.extend(ComponentRef(p, "providers") for p in provs)
    if ctxs := profile.get("contexts"):
        refs.extend(ComponentRef(c, "contexts") for c in ctxs)

    all_behavior_ids = list(behavior_defs.keys())
    if all_behavior_ids:
        sorted_behaviors = topological_sort_behaviors(all_behavior_ids, behavior_defs)

        for behavior_id in sorted_behaviors:
            behavior_def = behavior_defs.get(behavior_id, {})

            for hook in behavior_def.get("hooks", []):
                refs.append(ComponentRef(hook, "hooks", behavior_id))
            for agent in behavior_def.get("agents", []):
                refs.append(ComponentRef(agent, "agents", behavior_id))
            for ctx in behavior_def.get("contexts", []):
                refs.append(ComponentRef(ctx, "contexts", behavior_id))
            for tool in behavior_def.get("tools", []):
                refs.append(ComponentRef(tool, "tools", behavior_id))

    return refs


def parse_sources(sources_file: Path) -> dict[str, str]:
    """Parse SOURCES.txt into {component_id: source_ref}.

    Args:
        sources_file: Path to SOURCES.txt

    Returns:
        Dictionary mapping component IDs to source references
    """
    sources = {}
    for line in sources_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        if " " in line:
            parts = line.split(" ", 1)
        elif ":" in line and not line.startswith("http"):
            parts = line.split(":", 1)
        else:
            logger.warning(f"Skipping malformed line in SOURCES.txt: {line}")
            continue

        if len(parts) == 2:
            component_id, source = parts
            sources[component_id.strip()] = source.strip()

    return sources


def resolve_assets(refs: list[ComponentRef], sources: dict[str, str], resolver: RefResolutionService) -> dict[str, Path]:
    """Download/cache all assets and return local paths.

    Args:
        refs: List of component references
        sources: Dictionary mapping component IDs to source references
        resolver: RefResolutionService for downloading assets

    Returns:
        Dictionary mapping component IDs to local file paths

    Raises:
        ProfileCompilationError: If component not found in sources or download fails
    """
    asset_map = {}

    for ref in refs:
        source_ref = None

        if ref.id in sources:
            source_ref = sources[ref.id]
        else:
            prefixed_id = f"{ref.type}.{ref.id}"
            if prefixed_id in sources:
                source_ref = sources[prefixed_id]

        if not source_ref:
            raise ProfileCompilationError(
                f"Component '{ref.id}' (type: {ref.type}) not found in SOURCES.txt. "
                f"Tried: {ref.id}, {ref.type}.{ref.id}. "
                f"Please add a source entry for this component."
            )

        try:
            logger.info(f"Resolving {ref.type} '{ref.id}' from {source_ref}")
            resolved_path = resolver.resolve_ref(source_ref)
            asset_map[ref.id] = resolved_path
            logger.debug(f"  → {resolved_path}")
        except Exception as e:
            raise ProfileCompilationError(
                f"Failed to resolve component '{ref.id}' from source '{source_ref}': {e}"
            ) from e

    return asset_map


def deep_merge(base: dict, override: dict) -> dict:
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
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def merge_configs(root_config: dict, behavior_configs: dict[str, Any], sorted_behavior_ids: list[str]) -> dict:
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
            merged = deep_merge(merged, behavior_config["config"])

    return merged


def generate_mount_plan(
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
        asset_map: Dictionary mapping component IDs to local paths
        behavior_defs: Dictionary of loaded behavior definitions
        sorted_behavior_ids: Behavior IDs in dependency order

    Returns:
        Mount plan dictionary ready for JSON serialization
    """
    mount_plan: dict[str, Any] = {}
    working_dir = config.get("session", {}).get("working_dir")

    session: dict[str, Any] = {}
    session_config = config.get("session", {})

    if orch_id := profile.get("orchestrator"):
        session["orchestrator"] = {
            "module": orch_id,
            "source": profile["profile"]["name"],
            "config": session_config.get("orchestrator", {}),
        }

    if ctx_id := profile.get("context"):
        session["context"] = {
            "module": ctx_id,
            "source": profile["profile"]["name"],
            "config": session_config.get("context", {}),
        }

    settings = {k: v for k, v in session_config.items() if k not in ["orchestrator", "context"]}
    if settings:
        session["settings"] = settings

    mount_plan["session"] = session

    if provs := profile.get("providers"):
        providers = []
        providers_config = config.get("providers", [])

        provider_config_map = {}
        if isinstance(providers_config, list):
            for prov_conf in providers_config:
                if isinstance(prov_conf, dict):
                    for prov_id, prov_settings in prov_conf.items():
                        provider_config_map[prov_id] = prov_settings

        for prov_id in provs:
            providers.append(
                {
                    "module": prov_id,
                    "source": profile["profile"]["name"],
                    "config": provider_config_map.get(prov_id, {}),
                }
            )
        mount_plan["providers"] = providers

    seen_tools = set()
    all_tools = []
    for behavior_id in sorted_behavior_ids:
        behavior_def = behavior_defs.get(behavior_id, {})
        for tool_id in behavior_def.get("tools", []):
            if tool_id in seen_tools:
                continue
            seen_tools.add(tool_id)

            tool_config = {"working_dir": working_dir} if working_dir else {}
            for key, value in config.items():
                if key.startswith(f"{tool_id}."):
                    tool_config[key.split(".", 1)[1]] = value

            all_tools.append(
                {
                    "module": tool_id,
                    "source": profile["profile"]["name"],
                    "config": tool_config,
                }
            )

    if all_tools:
        mount_plan["tools"] = all_tools

    seen_hooks = set()
    all_hooks = []
    for behavior_id in sorted_behavior_ids:
        behavior_def = behavior_defs.get(behavior_id, {})
        for hook_id in behavior_def.get("hooks", []):
            if hook_id in seen_hooks:
                continue
            seen_hooks.add(hook_id)

            hook_config = {}
            for key, value in config.items():
                if key.startswith(f"hook.{hook_id}."):
                    hook_config[key.split(".", 2)[2]] = value

            all_hooks.append(
                {
                    "module": hook_id,
                    "source": profile["profile"]["name"],
                    "config": hook_config,
                }
            )

    if all_hooks:
        mount_plan["hooks"] = all_hooks

    agents_obj = {}
    for behavior_id in sorted_behavior_ids:
        behavior_def = behavior_defs.get(behavior_id, {})
        for agent_id in behavior_def.get("agents", []):
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


def compile_profile(
    profile_file: Path,
    config_file: Path,
    sources_file: Path,
    output_file: Path,
) -> None:
    """Compile v3 profile into mount plan.

    Args:
        profile_file: Path to profile YAML file (e.g., software-developer.yaml)
        config_file: Path to config YAML file (e.g., config.yaml)
        sources_file: Path to sources file (e.g., SOURCES.txt)
        output_file: Path to output JSON file

    Raises:
        ProfileCompilationError: If compilation fails
    """
    try:
        # Load inputs
        logger.info(f"Loading profile from {profile_file}")
        profile = yaml.safe_load(profile_file.read_text())

        logger.info(f"Loading config from {config_file}")
        full_config = yaml.safe_load(config_file.read_text())

        logger.info(f"Loading sources from {sources_file}")
        sources = parse_sources(sources_file)

        # Setup resolver
        cache_dir = Path.home() / ".cache" / "amplifier"
        resolver = RefResolutionService(state_dir=cache_dir)

        # Stage 0: Load behavior definitions
        behavior_ids = profile.get("behaviors", [])
        behavior_defs = {}
        if behavior_ids:
            logger.info(f"Loading {len(behavior_ids)} behavior definitions...")
            behavior_defs = load_behavior_definitions(behavior_ids, sources, resolver)

        # Extract behavior-specific configs from config.yaml
        behavior_configs = full_config.get("behaviors", {})
        if not isinstance(behavior_configs, dict):
            behavior_configs = {}

        # Stage 1: Collect components
        logger.info("Collecting components...")
        refs = collect_components(profile, behavior_defs)
        logger.info(f"Found {len(refs)} components")

        # Stage 2: Resolve assets
        logger.info("Resolving assets...")
        asset_map = resolve_assets(refs, sources, resolver)

        # Stage 3: Merge configs
        logger.info("Merging configurations...")
        # Use all loaded behaviors (including recursive dependencies) for topo sort
        all_behavior_ids = list(behavior_defs.keys())
        sorted_behavior_ids = topological_sort_behaviors(all_behavior_ids, behavior_defs) if all_behavior_ids else []
        merged_config = merge_configs(full_config, behavior_configs, sorted_behavior_ids)

        # Stage 4: Generate mount plan
        logger.info("Generating mount plan...")
        mount_plan = generate_mount_plan(profile, merged_config, asset_map, behavior_defs, sorted_behavior_ids)

        # Write output
        logger.info(f"Writing mount plan to {output_file}")
        output_file.write_text(json.dumps(mount_plan, indent=2))

        logger.info("✓ Profile compilation complete!")

    except ProfileCompilationError:
        raise
    except Exception as e:
        raise ProfileCompilationError(f"Compilation failed: {e}") from e


def main() -> None:
    """Main entry point for command-line usage."""
    if len(sys.argv) != 5:
        print("Usage: python compile_profile.py <profile.yaml> <config.yaml> <SOURCES.txt> <output.json>")
        print()
        print("Example:")
        print("  python compile_profile.py software-developer.yaml config.yaml SOURCES.txt output.json")
        sys.exit(1)

    try:
        profile_file = Path(sys.argv[1])
        config_file = Path(sys.argv[2])
        sources_file = Path(sys.argv[3])
        output_file = Path(sys.argv[4])

        # Validate inputs exist
        for f in [profile_file, config_file, sources_file]:
            if not f.exists():
                logger.error(f"File not found: {f}")
                sys.exit(1)

        compile_profile(profile_file, config_file, sources_file, output_file)

    except ProfileCompilationError as e:
        logger.error(f"Compilation error: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
