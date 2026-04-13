from plex_audit.path_mapper import PathMapping
from plex_audit.plex_client import MediaFile

from .conftest import PlexFake, make_ctx


def test_plex_fake_yields_movies():
    fake = PlexFake()
    fake.add_movie(title="Inception", year=2010, files=["/media/movies/Inception (2010)/Inception.mkv"])
    plex = fake.build()
    libraries = list(plex.iter_libraries())
    assert any(lib.kind == "movie" for lib in libraries)
    movie_library = next(lib for lib in libraries if lib.kind == "movie")
    items = list(movie_library.raw.all())
    assert items[0].title == "Inception"
    assert items[0].year == 2010
    files = list(plex.get_media_files(items[0]))
    assert files == [MediaFile(plex_path="/media/movies/Inception (2010)/Inception.mkv", rating_key=items[0].ratingKey)]


def test_plex_fake_yields_shows_with_seasons_and_episodes():
    fake = PlexFake()
    show = fake.add_show(title="Breaking Bad")
    show.add_season(number=1, episodes=[(1, ["/media/tv/BB/S01E01.mkv"]), (2, ["/media/tv/BB/S01E02.mkv"])])
    plex = fake.build()
    show_library = next(lib for lib in plex.iter_libraries() if lib.kind == "show")
    shows = list(show_library.raw.all())
    assert shows[0].title == "Breaking Bad"
    seasons = list(shows[0].seasons())
    assert seasons[0].index == 1
    episodes = list(seasons[0].episodes())
    assert [ep.index for ep in episodes] == [1, 2]


def test_make_ctx_wires_path_mapper_and_flags():
    fake = PlexFake()
    ctx = make_ctx(fake, mappings=[PathMapping(plex="/media", local="/local")])
    assert ctx.filesystem_available is True
    assert ctx.path_mapper.to_local("/media/x.mkv") is not None
