"""Tests for the configuration registry and loading system."""

import json
import os
from unittest.mock import patch

import pytest

from config import (
    CONFIG_REGISTRY,
    _convert,
    _load_config_file,
    get_config_metadata,
    load_config,
    save_config_file,
)


class TestConvert:
    """Tests for the _convert helper."""

    def test_str(self):
        assert _convert("hello", "str") == "hello"

    def test_int(self):
        assert _convert("42", "int") == 42

    def test_float(self):
        assert _convert("3.14", "float") == pytest.approx(3.14)

    def test_bool_true(self):
        assert _convert("true", "bool") is True

    def test_bool_false(self):
        assert _convert("false", "bool") is False

    def test_bool_case_insensitive(self):
        assert _convert("True", "bool") is True
        assert _convert("FALSE", "bool") is False

    def test_none_returns_none(self):
        assert _convert(None, "str") is None
        assert _convert(None, "int") is None

    def test_empty_string_int(self):
        assert _convert("", "int") is None

    def test_empty_string_float(self):
        assert _convert("", "float") is None

    def test_empty_string_str(self):
        assert _convert("", "str") == ""


class TestRegistry:
    """Tests for the CONFIG_REGISTRY definition."""

    def test_no_duplicate_keys(self):
        keys = [p.key for p in CONFIG_REGISTRY]
        assert len(keys) == len(set(keys)), "Duplicate keys in registry"

    def test_no_duplicate_env_vars(self):
        env_vars = [p.env_var for p in CONFIG_REGISTRY]
        assert len(env_vars) == len(set(env_vars)), "Duplicate env vars"

    def test_all_types_valid(self):
        valid = {"str", "int", "float", "bool"}
        for p in CONFIG_REGISTRY:
            assert p.type in valid, f"{p.key} has invalid type {p.type}"

    def test_all_groups_non_empty(self):
        for p in CONFIG_REGISTRY:
            assert p.group, f"{p.key} has empty group"

    def test_all_descriptions_non_empty(self):
        for p in CONFIG_REGISTRY:
            assert p.description, f"{p.key} has empty description"

    def test_sensitive_keys_exist(self):
        sensitive = [p for p in CONFIG_REGISTRY if p.sensitive]
        assert len(sensitive) >= 7  # api keys, passwords, tokens


class TestLoadConfig:
    """Tests for load_config()."""

    def test_returns_all_registry_keys(self):
        config = load_config()
        for p in CONFIG_REGISTRY:
            assert p.key in config, f"Missing key: {p.key}"

    def test_default_values(self):
        config = load_config()
        assert config["display_mode"] == "mock"
        assert config["audio_sample_rate"] == 16000
        assert config["voice_enabled"] is True

    def test_env_var_override(self):
        with patch.dict(os.environ, {"HUD_DISPLAY_MODE": "eink"}):
            config = load_config()
            assert config["display_mode"] == "eink"

    def test_config_file_overrides_env(self, tmp_path, monkeypatch):
        cfg_file = tmp_path / "config.json"
        cfg_file.write_text(json.dumps({"display_mode": "from_file"}))
        monkeypatch.setattr("config.CONFIG_FILE", cfg_file)

        with patch.dict(os.environ, {"HUD_DISPLAY_MODE": "from_env"}):
            config = load_config()
            assert config["display_mode"] == "from_file"

    def test_audio_device_none_default(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("HUD_AUDIO_DEVICE", None)
            config = load_config()
            assert config["audio_device"] is None


class TestConfigFile:
    """Tests for config file loading and saving."""

    def test_load_missing_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "config.CONFIG_FILE", tmp_path / "nonexistent.json",
        )
        assert _load_config_file() == {}

    def test_load_valid_file(self, tmp_path, monkeypatch):
        cfg = tmp_path / "config.json"
        cfg.write_text(json.dumps({"foo": "bar"}))
        monkeypatch.setattr("config.CONFIG_FILE", cfg)
        assert _load_config_file() == {"foo": "bar"}

    def test_load_invalid_json(self, tmp_path, monkeypatch):
        cfg = tmp_path / "config.json"
        cfg.write_text("not json!")
        monkeypatch.setattr("config.CONFIG_FILE", cfg)
        assert _load_config_file() == {}

    def test_load_non_dict_json(self, tmp_path, monkeypatch):
        cfg = tmp_path / "config.json"
        cfg.write_text(json.dumps([1, 2, 3]))
        monkeypatch.setattr("config.CONFIG_FILE", cfg)
        assert _load_config_file() == {}

    def test_save_creates_file(self, tmp_path, monkeypatch):
        cfg = tmp_path / "data" / "config.json"
        monkeypatch.setattr("config.CONFIG_FILE", cfg)
        save_config_file({"key": "value"})
        assert cfg.is_file()
        data = json.loads(cfg.read_text())
        assert data == {"key": "value"}

    def test_save_merges_with_existing(self, tmp_path, monkeypatch):
        cfg = tmp_path / "config.json"
        cfg.write_text(json.dumps({"a": "1", "b": "2"}))
        monkeypatch.setattr("config.CONFIG_FILE", cfg)
        save_config_file({"b": "updated", "c": "3"})
        data = json.loads(cfg.read_text())
        assert data == {"a": "1", "b": "updated", "c": "3"}


class TestConfigMetadata:
    """Tests for get_config_metadata()."""

    def test_returns_params_and_groups(self):
        config = load_config()
        meta = get_config_metadata(config)
        assert "params" in meta
        assert "groups" in meta
        assert len(meta["params"]) == len(CONFIG_REGISTRY)

    def test_sensitive_values_masked(self):
        config = load_config()
        meta = get_config_metadata(config)
        for p in meta["params"]:
            if p["sensitive"]:
                assert p["value"] == "********"
                assert p["default"] == "********"

    def test_non_sensitive_values_exposed(self):
        config = load_config()
        meta = get_config_metadata(config)
        params_by_key = {p["key"]: p for p in meta["params"]}
        assert params_by_key["display_mode"]["value"] == "mock"

    def test_source_default(self):
        config = load_config()
        meta = get_config_metadata(config)
        params_by_key = {p["key"]: p for p in meta["params"]}
        # display_mode should be "default" unless env var is set
        dm = params_by_key["display_mode"]
        if os.getenv("HUD_DISPLAY_MODE") is None:
            assert dm["source"] == "default"

    def test_source_file(self, tmp_path, monkeypatch):
        cfg = tmp_path / "config.json"
        cfg.write_text(json.dumps({"display_mode": "eink"}))
        monkeypatch.setattr("config.CONFIG_FILE", cfg)
        config = load_config()
        meta = get_config_metadata(config)
        params_by_key = {p["key"]: p for p in meta["params"]}
        assert params_by_key["display_mode"]["source"] == "file"

    def test_groups_ordered(self):
        config = load_config()
        meta = get_config_metadata(config)
        # Groups should preserve registry order
        expected = list(dict.fromkeys(p.group for p in CONFIG_REGISTRY))
        assert meta["groups"] == expected

    def test_param_has_required_fields(self):
        config = load_config()
        meta = get_config_metadata(config)
        required = {
            "key", "value", "type", "group", "description",
            "default", "env_var", "source", "sensitive",
        }
        for p in meta["params"]:
            assert required.issubset(p.keys()), (
                f"Missing fields in {p['key']}"
            )
