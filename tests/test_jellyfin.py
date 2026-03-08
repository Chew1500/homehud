"""Tests for Jellyfin client — mock shape validation and factory functions."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from jellyfin import get_jellyfin_client  # noqa: E402, I001
from jellyfin.mock_client import MockJellyfinClient  # noqa: E402


# -- MockJellyfinClient --


def test_mock_jellyfin_get_user_id():
    client = MockJellyfinClient({"jellyfin_user_id": "test-user"})
    assert client.get_user_id() == "test-user"


def test_mock_jellyfin_get_library_items():
    client = MockJellyfinClient({})
    items = client.get_library_items()
    assert len(items) >= 1
    item = items[0]
    assert "id" in item
    assert "title" in item
    assert item["media_type"] in ("movie", "series")
    assert "year" in item
    assert "genres" in item and isinstance(item["genres"], list)
    assert "overview" in item


def test_mock_jellyfin_items_have_people():
    client = MockJellyfinClient({})
    items = client.get_library_items()
    items_with_people = [i for i in items if i.get("people")]
    assert len(items_with_people) >= 1
    person = items_with_people[0]["people"][0]
    assert "name" in person
    assert "type" in person
    assert person["type"] in ("Actor", "Director", "Writer")


def test_mock_jellyfin_items_have_watch_history():
    client = MockJellyfinClient({})
    items = client.get_library_items()
    for item in items:
        assert "played" in item and isinstance(item["played"], bool)
        assert "play_count" in item and isinstance(item["play_count"], int)
        assert "is_favorite" in item and isinstance(item["is_favorite"], bool)


def test_mock_jellyfin_items_have_provider_ids():
    client = MockJellyfinClient({})
    items = client.get_library_items()
    for item in items:
        assert "provider_ids" in item and isinstance(item["provider_ids"], dict)


def test_mock_jellyfin_has_both_media_types():
    client = MockJellyfinClient({})
    items = client.get_library_items()
    types = {i["media_type"] for i in items}
    assert "movie" in types
    assert "series" in types


def test_mock_jellyfin_close():
    client = MockJellyfinClient({})
    client.close()  # Should not raise


# -- Factory functions --


def test_jellyfin_factory_empty_mode():
    """Empty mode (default) returns None — opt-in."""
    assert get_jellyfin_client({"jellyfin_mode": ""}) is None
    assert get_jellyfin_client({}) is None


def test_jellyfin_factory_mock():
    client = get_jellyfin_client({"jellyfin_mode": "mock"})
    assert isinstance(client, MockJellyfinClient)
