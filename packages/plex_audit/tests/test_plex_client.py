from unittest.mock import MagicMock, patch

from plex_audit.config import PlexConfig
from plex_audit.plex_client import MediaFile, PlexClient


def _fake_server() -> MagicMock:
    server = MagicMock()
    movie_section = MagicMock()
    movie_section.type = "movie"
    movie_section.title = "Movies"
    show_section = MagicMock()
    show_section.type = "show"
    show_section.title = "TV"
    server.library.sections.return_value = [movie_section, show_section]
    return server


def test_iter_libraries_returns_typed_entries():
    with patch("plex_audit.plex_client.PlexServer", return_value=_fake_server()):
        client = PlexClient(PlexConfig(url="http://x", token="t"))
        libraries = list(client.iter_libraries())
    assert [lib.kind for lib in libraries] == ["movie", "show"]
    assert libraries[0].title == "Movies"


def test_iter_libraries_is_cached():
    server = _fake_server()
    with patch("plex_audit.plex_client.PlexServer", return_value=server):
        client = PlexClient(PlexConfig(url="http://x", token="t"))
        list(client.iter_libraries())
        list(client.iter_libraries())
    assert server.library.sections.call_count == 1


def test_get_media_files_extracts_paths():
    media_part = MagicMock()
    media_part.file = "/media/tv/show/s01e01.mkv"
    media_item = MagicMock()
    media_item.parts = [media_part]
    plex_item = MagicMock()
    plex_item.media = [media_item]
    plex_item.ratingKey = "42"

    with patch("plex_audit.plex_client.PlexServer", return_value=_fake_server()):
        client = PlexClient(PlexConfig(url="http://x", token="t"))
        files = list(client.get_media_files(plex_item))
    assert files == [MediaFile(plex_path="/media/tv/show/s01e01.mkv", rating_key="42")]
