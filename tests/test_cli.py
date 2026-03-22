# tests/test_cli.py

import pytest

from music_ferry.cli import parse_args


class TestCLI:
    def test_parse_sync_command(self):
        args = parse_args(["sync"])
        assert args.command == "sync"

    def test_parse_sync_with_verbose(self):
        args = parse_args(["-v", "sync"])
        assert args.command == "sync"
        assert args.verbose is True

    def test_parse_sync_with_config(self):
        args = parse_args(["-c", "/path/to/config.yaml", "sync"])
        assert args.command == "sync"
        assert str(args.config) == "/path/to/config.yaml"

    def test_parse_transfer_command(self):
        args = parse_args(["transfer"])
        assert args.command == "transfer"

    def test_parse_transfer_with_verbose(self):
        args = parse_args(["-v", "transfer"])
        assert args.command == "transfer"
        assert args.verbose is True

    def test_no_command_shows_help(self):
        with pytest.raises(SystemExit):
            parse_args([])

    def test_global_args_before_subcommand(self):
        args = parse_args(["-v", "-c", "/custom/config.yaml", "sync"])
        assert args.command == "sync"
        assert args.verbose is True
        assert str(args.config) == "/custom/config.yaml"
