from music_ferry.filenames import build_track_filename
from music_ferry.spotify_api import Track


def test_build_track_filename_uses_artist_and_title():
    track = Track(
        id="abc123",
        name="Never Gonna Give You Up",
        artists=["Rick Astley"],
        album="Whenever You Need Somebody",
        duration_ms=213000,
        album_art_url=None,
    )

    assert build_track_filename(track, max_chars=100) == (
        "Rick Astley - Never Gonna Give You Up.mp3"
    )


def test_build_track_filename_sanitizes_path_unsafe_characters():
    track = Track(
        id="abc123",
        name='Thunder/Struck: "Live"?',
        artists=["AC/DC", "Guest|Singer"],
        album="Album",
        duration_ms=292000,
        album_art_url=None,
    )

    assert build_track_filename(track, max_chars=100) == (
        "AC DC, Guest Singer - Thunder Struck Live.mp3"
    )


def test_build_track_filename_truncates_to_configured_length_preserving_extension():
    track = Track(
        id="abc123",
        name="A" * 120,
        artists=["Artist"],
        album="Album",
        duration_ms=292000,
        album_art_url=None,
    )

    filename = build_track_filename(track, max_chars=40)

    assert len(filename) == 40
    assert filename.endswith(".mp3")
    assert filename == "Artist - AAAAAAAAAAAAAAAAAAAAAAAAAAA.mp3"
