"""Tests for Jellyfin client — mock shape validation and factory functions."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

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


# -- User ID resolution --

FAKE_USERS = [
    {"Name": "admin", "Id": "c676f76af9944208a4c34a1cc788857f"},
    {"Name": "guest", "Id": "aaaa1111bbbb2222cccc3333dddd4444"},
]


def _make_client_with_mock_httpx(user_id: str, users_response=None):
    """Create a JellyfinClient with a mocked httpx.Client."""
    from jellyfin.client import JellyfinClient

    mock_resp = MagicMock()
    mock_resp.json.return_value = (
        users_response if users_response is not None else FAKE_USERS
    )
    mock_resp.raise_for_status = MagicMock()

    mock_http = MagicMock()
    mock_http.get.return_value = mock_resp

    with patch("httpx.Client", return_value=mock_http):
        client = JellyfinClient(
            {
                "jellyfin_url": "http://fake:8096",
                "jellyfin_api_key": "fake-key",
                "jellyfin_user_id": user_id,
            }
        )
    return client, mock_http


def test_resolve_username_to_uuid():
    """Username 'admin' is resolved to the matching UUID."""
    client, mock_http = _make_client_with_mock_httpx("admin")
    assert client.get_user_id() == "c676f76af9944208a4c34a1cc788857f"
    mock_http.get.assert_called_once_with("/Users")


def test_resolve_username_case_insensitive():
    """Username resolution is case-insensitive."""
    client, _ = _make_client_with_mock_httpx("Admin")
    assert client.get_user_id() == "c676f76af9944208a4c34a1cc788857f"


def test_resolve_empty_picks_first_user():
    """Empty user_id picks the first user from the list."""
    client, mock_http = _make_client_with_mock_httpx("")
    assert client.get_user_id() == "c676f76af9944208a4c34a1cc788857f"
    mock_http.get.assert_called_once_with("/Users")


def test_resolve_uuid_passthrough():
    """A hex UUID skips the API call entirely."""
    client, mock_http = _make_client_with_mock_httpx(
        "c676f76af9944208a4c34a1cc788857f"
    )
    assert client.get_user_id() == "c676f76af9944208a4c34a1cc788857f"
    mock_http.get.assert_not_called()


def test_resolve_unknown_username_keeps_original():
    """Unknown username is kept as-is with a warning."""
    client, _ = _make_client_with_mock_httpx("nobody")
    assert client.get_user_id() == "nobody"


def test_resolve_network_error_keeps_original():
    """Network error during resolution keeps the original value."""
    from jellyfin.client import JellyfinClient

    mock_http = MagicMock()
    mock_http.get.side_effect = Exception("connection refused")

    with patch("httpx.Client", return_value=mock_http):
        client = JellyfinClient(
            {
                "jellyfin_url": "http://fake:8096",
                "jellyfin_api_key": "fake-key",
                "jellyfin_user_id": "admin",
            }
        )
    assert client.get_user_id() == "admin"
