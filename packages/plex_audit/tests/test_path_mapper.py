from pathlib import PurePosixPath, PureWindowsPath

from plex_audit.path_mapper import PathMapper, PathMapping


def _mapper(mappings: list[tuple[str, str]]) -> PathMapper:
    return PathMapper([PathMapping(plex=plex, local=local) for plex, local in mappings])


def test_returns_none_when_no_mapping_matches():
    mapper = _mapper([("/media/tv", "D:/Media/TV")])
    assert mapper.to_local("/media/movies/x.mkv") is None


def test_translates_posix_plex_path_to_windows_local():
    mapper = _mapper([("/media/tv", "D:/Media/TV")])
    assert mapper.to_local("/media/tv/Breaking Bad/S01/e01.mkv") == PureWindowsPath(
        "D:/Media/TV/Breaking Bad/S01/e01.mkv"
    )


def test_trailing_slash_insensitive():
    mapper = _mapper([("/media/tv/", "D:/Media/TV/")])
    assert mapper.to_local("/media/tv/a.mkv") == PureWindowsPath("D:/Media/TV/a.mkv")


def test_longest_prefix_wins():
    mapper = _mapper([
        ("/media", "D:/Media"),
        ("/media/tv", "E:/TV"),
    ])
    assert mapper.to_local("/media/tv/show.mkv") == PureWindowsPath("E:/TV/show.mkv")
    assert mapper.to_local("/media/movies/film.mkv") == PureWindowsPath("D:/Media/movies/film.mkv")


def test_posix_local_target():
    mapper = _mapper([("/media", "/mnt/media")])
    result = mapper.to_local("/media/movies/film.mkv")
    assert result == PurePosixPath("/mnt/media/movies/film.mkv")


def test_has_mappings_flag():
    assert PathMapper([]).has_mappings is False
    assert _mapper([("/a", "/b")]).has_mappings is True
