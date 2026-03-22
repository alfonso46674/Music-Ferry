# tests/test_tagger.py
from pathlib import Path
from unittest.mock import MagicMock, patch

from mutagen.id3 import ID3NoHeaderError
from mutagen.mp3 import MP3

from music_ferry.spotify_api import Track
from music_ferry.tagger import tag_mp3


def create_valid_mp3(path: Path) -> None:
    """Create a minimal valid MP3 file with enough frames for mutagen."""
    # MP3 frame header: 0xFF 0xFB = sync word + MPEG1 Layer3
    # 0x90 = 128kbps, 44100Hz, stereo
    # 0x00 = no padding, private bit off
    # Frame size for 128kbps @ 44100Hz = 417 bytes
    frame_header = bytes([0xFF, 0xFB, 0x90, 0x00])
    frame_data = bytes([0x00] * 413)  # Remaining frame bytes (417 - 4 header)
    single_frame = frame_header + frame_data

    # Write multiple frames to satisfy mutagen's frame detection
    with open(path, "wb") as f:
        for _ in range(4):
            f.write(single_frame)


class FakeTags(dict[str, object]):
    def __init__(self) -> None:
        super().__init__()
        self.save = MagicMock()


class TestTagger:
    @patch("music_ferry.tagger.ID3")
    def test_tag_mp3_creates_new_id3_tags_when_missing(self, mock_id3, tmp_path: Path):
        mp3_path = tmp_path / "test.mp3"
        create_valid_mp3(mp3_path)

        created_tags = FakeTags()
        mock_id3.side_effect = [
            ID3NoHeaderError("missing header"),
            created_tags,
        ]

        track = Track(
            id="abc123",
            name="Test Song",
            artists=["Artist 1", "Artist 2"],
            album="Test Album",
            duration_ms=180000,
            album_art_url=None,
        )

        tag_mp3(mp3_path, track)

        assert mock_id3.call_args_list[0].args == (mp3_path,)
        assert mock_id3.call_args_list[1].args == ()
        assert created_tags["TIT2"].text[0] == "Test Song"
        assert created_tags["TPE1"].text[0] == "Artist 1, Artist 2"
        assert created_tags["TALB"].text[0] == "Test Album"
        created_tags.save.assert_called_once_with(mp3_path)

    def test_tag_mp3_basic(self, tmp_path: Path):
        mp3_path = tmp_path / "test.mp3"
        create_valid_mp3(mp3_path)

        track = Track(
            id="abc123",
            name="Test Song",
            artists=["Artist 1", "Artist 2"],
            album="Test Album",
            duration_ms=180000,
            album_art_url=None,
        )

        tag_mp3(mp3_path, track)

        # Verify tags were written
        audio = MP3(mp3_path)
        assert audio.tags["TIT2"].text[0] == "Test Song"
        assert audio.tags["TPE1"].text[0] == "Artist 1, Artist 2"
        assert audio.tags["TALB"].text[0] == "Test Album"

    @patch("music_ferry.tagger.requests.get")
    def test_tag_mp3_with_album_art(self, mock_get, tmp_path: Path):
        mp3_path = tmp_path / "test.mp3"
        create_valid_mp3(mp3_path)

        # Mock album art download
        mock_response = MagicMock()
        mock_response.content = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100  # Fake PNG
        mock_response.headers = {"Content-Type": "image/png"}
        mock_response.ok = True
        mock_get.return_value = mock_response

        track = Track(
            id="abc123",
            name="Test Song",
            artists=["Artist 1"],
            album="Test Album",
            duration_ms=180000,
            album_art_url="https://example.com/art.jpg",
        )

        tag_mp3(mp3_path, track)

        # Verify album art was embedded
        audio = MP3(mp3_path)
        apic_frames = [f for f in audio.tags.values() if f.FrameID == "APIC"]
        assert len(apic_frames) == 1
