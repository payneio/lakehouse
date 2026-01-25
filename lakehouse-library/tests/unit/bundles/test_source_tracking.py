"""Tests for bundle source tracking in get_resolved_bundle.

This tests that when bundles are composed via includes, the UI can show
which bundle actually contributed each component.
"""

from pathlib import Path

import pytest
from lakehouse_library.bundles import LakehouseBundleManager


class TestBundleSourceTracking:
    """Tests for tracking which bundle provides each component."""

    @pytest.mark.asyncio
    async def test_tracks_components_from_included_bundles(self, tmp_path: Path) -> None:
        """Components from included bundles show correct source."""
        bundles_dir = tmp_path / "bundles"
        bundles_dir.mkdir(parents=True)

        # Create a base bundle with a provider
        (bundles_dir / "base.md").write_text(
            """---
bundle:
  name: base
  version: 1.0.0

providers:
  - module: provider-anthropic
    source: git+https://github.com/microsoft/amplifier-provider-anthropic
---
# Base Bundle
"""
        )

        # Create an app bundle that includes base
        (bundles_dir / "my-app.md").write_text(
            """---
bundle:
  name: my-app
  version: 1.0.0

includes:
  - base

tools:
  - module: tool-bash
    source: git+https://github.com/microsoft/amplifier-tool-bash
---
# My App
"""
        )

        manager = LakehouseBundleManager(home_dir=tmp_path)
        resolved = await manager.get_resolved_bundle("my-app")

        # The provider came from base, not my-app
        provider = next((p for p in resolved["providers"] if p["module"] == "provider-anthropic"), None)
        assert provider is not None, "provider-anthropic should be in resolved bundle"
        assert provider["defined_in"] == "base", f"Expected 'base', got '{provider['defined_in']}'"

        # The tool came from my-app directly
        tool = next((t for t in resolved["tools"] if t["module"] == "tool-bash"), None)
        assert tool is not None, "tool-bash should be in resolved bundle"
        assert tool["defined_in"] == "my-app", f"Expected 'my-app', got '{tool['defined_in']}'"

    @pytest.mark.asyncio
    async def test_tracks_deep_includes_chain(self, tmp_path: Path) -> None:
        """Components are tracked through multiple levels of includes."""
        bundles_dir = tmp_path / "bundles"
        bundles_dir.mkdir(parents=True)

        # Create a chain: foundation -> python-dev -> my-app
        (bundles_dir / "foundation.md").write_text(
            """---
bundle:
  name: foundation
  version: 1.0.0

providers:
  - module: provider-anthropic
---
# Foundation
"""
        )

        (bundles_dir / "python-dev.md").write_text(
            """---
bundle:
  name: python-dev
  version: 1.0.0

includes:
  - foundation

tools:
  - module: tool-python-check
---
# Python Dev
"""
        )

        (bundles_dir / "my-app.md").write_text(
            """---
bundle:
  name: my-app
  version: 1.0.0

includes:
  - python-dev

hooks:
  - module: hooks-logging
---
# My App
"""
        )

        manager = LakehouseBundleManager(home_dir=tmp_path)
        resolved = await manager.get_resolved_bundle("my-app")

        # Provider from foundation (deepest level)
        provider = next((p for p in resolved["providers"] if p["module"] == "provider-anthropic"), None)
        assert provider is not None
        assert provider["defined_in"] == "foundation"

        # Tool from python-dev (middle level)
        tool = next((t for t in resolved["tools"] if t["module"] == "tool-python-check"), None)
        assert tool is not None
        assert tool["defined_in"] == "python-dev"

        # Hook from my-app (top level)
        hook = next((h for h in resolved["hooks"] if h["module"] == "hooks-logging"), None)
        assert hook is not None
        assert hook["defined_in"] == "my-app"

    @pytest.mark.asyncio
    async def test_tracks_config_overrides(self, tmp_path: Path) -> None:
        """Tracks when a component config is overridden in a later bundle."""
        bundles_dir = tmp_path / "bundles"
        bundles_dir.mkdir(parents=True)

        # Base defines a tool with default config
        (bundles_dir / "base.md").write_text(
            """---
bundle:
  name: base
  version: 1.0.0

tools:
  - module: tool-test
    config:
      setting: original
---
# Base
"""
        )

        # App overrides the tool config
        (bundles_dir / "app.md").write_text(
            """---
bundle:
  name: app
  version: 1.0.0

includes:
  - base

tools:
  - module: tool-test
    config:
      setting: overridden
---
# App
"""
        )

        manager = LakehouseBundleManager(home_dir=tmp_path)
        resolved = await manager.get_resolved_bundle("app")

        tool = next((t for t in resolved["tools"] if t["module"] == "tool-test"), None)
        assert tool is not None
        assert tool["defined_in"] == "base"
        assert tool["overridden"] is True
        assert tool["override_in"] == "app"
        assert tool["config"]["setting"] == "overridden"
        assert tool["original_config"]["setting"] == "original"
