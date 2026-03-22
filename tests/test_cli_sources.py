# tests/test_cli_sources.py
from music_ferry.cli import parse_args


class TestCLISourceFlags:
    def test_sync_no_flags_defaults_false(self):
        args = parse_args(["sync"])
        assert args.command == "sync"
        assert args.spotify is False
        assert args.youtube is False

    def test_sync_spotify_only(self):
        args = parse_args(["sync", "--spotify"])
        assert args.spotify is True
        assert args.youtube is False

    def test_sync_youtube_only(self):
        args = parse_args(["sync", "--youtube"])
        assert args.spotify is False
        assert args.youtube is True

    def test_sync_both_flags(self):
        args = parse_args(["sync", "--spotify", "--youtube"])
        assert args.spotify is True
        assert args.youtube is True

    def test_transfer_no_flags_defaults_false(self):
        args = parse_args(["transfer"])
        assert args.command == "transfer"
        assert args.spotify is False
        assert args.youtube is False

    def test_transfer_spotify_only(self):
        args = parse_args(["transfer", "--spotify"])
        assert args.spotify is True
        assert args.youtube is False

    def test_transfer_youtube_only(self):
        args = parse_args(["transfer", "--youtube"])
        assert args.spotify is False
        assert args.youtube is True

    def test_global_flags_still_work(self):
        args = parse_args(["-v", "-c", "/custom/path.yaml", "sync", "--youtube"])
        assert args.verbose is True
        assert str(args.config) == "/custom/path.yaml"
        assert args.youtube is True
