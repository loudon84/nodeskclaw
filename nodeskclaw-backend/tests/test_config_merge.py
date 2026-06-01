"""Tests for deep_merge_config and ensure_channel_plugin_integrity."""

from __future__ import annotations

import copy

import pytest

from app.utils.jsonc import (
    _CHANNEL_PLUGIN_PATHS,
    deep_merge_config,
    ensure_channel_plugin_integrity,
)


# ── deep_merge_config ────────────────────────────


class TestDeepMergeConfig:

    def test_nested_dicts_preserve_siblings(self):
        base = {
            "plugins": {
                "load": {"paths": ["/a"]},
                "entries": {"nodeskclaw": {"enabled": True}, "other": {"enabled": False}},
            }
        }
        patch = {
            "plugins": {
                "entries": {"new-plugin": {"enabled": True}},
            }
        }
        result = deep_merge_config(base, patch)

        assert result["plugins"]["load"] == {"paths": ["/a"]}
        assert result["plugins"]["entries"]["nodeskclaw"] == {"enabled": True}
        assert result["plugins"]["entries"]["other"] == {"enabled": False}
        assert result["plugins"]["entries"]["new-plugin"] == {"enabled": True}

    def test_list_replaces(self):
        base = {"tools": {"allow": ["a", "b"]}}
        patch = {"tools": {"allow": ["x"]}}
        result = deep_merge_config(base, patch)

        assert result["tools"]["allow"] == ["x"]

    def test_scalar_replaces(self):
        base = {"gateway": {"port": 8080}}
        patch = {"gateway": {"port": 9090}}
        result = deep_merge_config(base, patch)

        assert result["gateway"]["port"] == 9090

    def test_empty_patch_noop(self):
        base = {
            "plugins": {
                "entries": {"nodeskclaw": {"enabled": True}},
                "load": {"paths": ["/a"]},
            }
        }
        original = copy.deepcopy(base)
        deep_merge_config(base, {"plugins": {}})

        assert base == original

    def test_new_top_level_key(self):
        base = {"existing": 1}
        deep_merge_config(base, {"new_key": {"nested": True}})

        assert base["existing"] == 1
        assert base["new_key"] == {"nested": True}

    def test_patch_dict_over_scalar(self):
        base = {"key": "string_value"}
        deep_merge_config(base, {"key": {"nested": True}})

        assert base["key"] == {"nested": True}

    def test_patch_scalar_over_dict(self):
        base = {"key": {"nested": True}}
        deep_merge_config(base, {"key": "replaced"})

        assert base["key"] == "replaced"


# ── ensure_channel_plugin_integrity ──────────────


class TestEnsureChannelPluginIntegrity:

    def test_adds_missing_path_and_entry(self):
        config = {
            "channels": {"nodeskclaw": {"accounts": {}}},
            "plugins": {"load": {"paths": []}, "entries": {}},
        }
        ensure_channel_plugin_integrity(config)

        assert _CHANNEL_PLUGIN_PATHS["nodeskclaw"] in config["plugins"]["load"]["paths"]
        assert config["plugins"]["entries"]["nodeskclaw"] == {"enabled": True}

    def test_noop_without_channel(self):
        config = {
            "plugins": {"load": {"paths": []}, "entries": {}},
        }
        original = copy.deepcopy(config)
        ensure_channel_plugin_integrity(config)

        assert config == original

    def test_covers_learning_channel(self):
        config = {
            "channels": {"learning": {"webhookUrl": "http://example.com"}},
            "plugins": {"load": {"paths": []}, "entries": {}},
        }
        ensure_channel_plugin_integrity(config)

        assert _CHANNEL_PLUGIN_PATHS["learning"] in config["plugins"]["load"]["paths"]
        assert config["plugins"]["entries"]["learning"] == {"enabled": True}

    def test_no_duplicate_when_already_present(self):
        nodeskclaw_path = _CHANNEL_PLUGIN_PATHS["nodeskclaw"]
        config = {
            "channels": {"nodeskclaw": {}},
            "plugins": {
                "load": {"paths": [nodeskclaw_path]},
                "entries": {"nodeskclaw": {"enabled": True}},
            },
        }
        ensure_channel_plugin_integrity(config)

        assert config["plugins"]["load"]["paths"].count(nodeskclaw_path) == 1

    def test_creates_plugins_section_if_missing(self):
        config = {"channels": {"nodeskclaw": {}}}
        ensure_channel_plugin_integrity(config)

        assert "plugins" in config
        assert _CHANNEL_PLUGIN_PATHS["nodeskclaw"] in config["plugins"]["load"]["paths"]
        assert config["plugins"]["entries"]["nodeskclaw"] == {"enabled": True}


# ── End-to-end: apply_config scenario ────────────


class TestApplyConfigPreservesNodeskclaw:

    def test_gene_patch_with_plugin_entries_preserves_nodeskclaw(self):
        """Simulate a Gene runtime_config that adds a plugin entry.

        Before the fix, this would wipe plugins.entries.nodeskclaw via
        shallow dict.update.  With deep_merge_config the sibling key survives.
        """
        existing_config = {
            "channels": {"nodeskclaw": {"accounts": {"default": {}}}},
            "plugins": {
                "load": {"paths": [_CHANNEL_PLUGIN_PATHS["nodeskclaw"]]},
                "entries": {"nodeskclaw": {"enabled": True}},
            },
            "tools": {"allow": ["tool_a"]},
        }

        gene_patch = {
            "plugins": {
                "entries": {"some-gene-plugin": {"enabled": True}},
            },
        }

        deep_merge_config(existing_config, gene_patch)
        ensure_channel_plugin_integrity(existing_config)

        assert existing_config["plugins"]["entries"]["nodeskclaw"] == {"enabled": True}
        assert existing_config["plugins"]["entries"]["some-gene-plugin"] == {"enabled": True}
        assert _CHANNEL_PLUGIN_PATHS["nodeskclaw"] in existing_config["plugins"]["load"]["paths"]

    def test_gene_patch_replacing_load_paths_gets_repaired(self):
        """Even if a Gene patch replaces plugins.load.paths (list -> list),
        the integrity guard re-adds the channel plugin path."""
        existing_config = {
            "channels": {"nodeskclaw": {"accounts": {}}},
            "plugins": {
                "load": {"paths": [_CHANNEL_PLUGIN_PATHS["nodeskclaw"]]},
                "entries": {"nodeskclaw": {"enabled": True}},
            },
        }

        gene_patch = {
            "plugins": {
                "load": {"paths": ["/some/other/plugin"]},
            },
        }

        deep_merge_config(existing_config, gene_patch)
        ensure_channel_plugin_integrity(existing_config)

        paths = existing_config["plugins"]["load"]["paths"]
        assert "/some/other/plugin" in paths
        assert _CHANNEL_PLUGIN_PATHS["nodeskclaw"] in paths
