# tests/test_cli_sources.py
from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from music_ferry.cli import main, parse_args


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

    @patch("music_ferry.cli.cmd_sync")
    @patch("music_ferry.cli.configure_file_logging")
    @patch("music_ferry.cli.load_config")
    @patch("music_ferry.cli.setup_logging")
    @patch("music_ferry.cli.parse_args")
    def test_main_passes_source_flags_to_sync(
        self,
        mock_parse_args,
        _mock_setup_logging,
        mock_load_config,
        _mock_configure_file_logging,
        mock_cmd_sync,
    ):
        config = SimpleNamespace(
            spotify=SimpleNamespace(enabled=True),
            youtube=SimpleNamespace(enabled=True),
        )
        mock_parse_args.return_value = Namespace(
            command="sync",
            verbose=False,
            config=Path("/tmp/config.yaml"),
            spotify=False,
            youtube=True,
        )
        mock_load_config.return_value = config
        mock_cmd_sync.return_value = 0

        result = main()

        assert result == 0
        mock_cmd_sync.assert_called_once_with(
            config,
            False,
            sync_spotify=False,
            sync_youtube=True,
        )

    @patch("music_ferry.cli.cmd_transfer")
    @patch("music_ferry.cli.configure_file_logging")
    @patch("music_ferry.cli.load_config")
    @patch("music_ferry.cli.setup_logging")
    @patch("music_ferry.cli.parse_args")
    def test_main_passes_selected_sources_to_transfer(
        self,
        mock_parse_args,
        _mock_setup_logging,
        mock_load_config,
        _mock_configure_file_logging,
        mock_cmd_transfer,
    ):
        config = SimpleNamespace(
            spotify=SimpleNamespace(enabled=False),
            youtube=SimpleNamespace(enabled=True),
        )
        mock_parse_args.return_value = Namespace(
            command="transfer",
            verbose=True,
            config=Path("/tmp/config.yaml"),
            auto=True,
            spotify=False,
            youtube=False,
        )
        mock_load_config.return_value = config
        mock_cmd_transfer.return_value = 0

        result = main()

        assert result == 0
        mock_cmd_transfer.assert_called_once_with(
            config,
            True,
            True,
            sources=["youtube"],
        )
