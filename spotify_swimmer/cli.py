# spotify_swimmer/cli.py
import argparse
import asyncio
import logging
import sys
from pathlib import Path

from spotify_swimmer.config import load_config


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download Spotify playlists to MP3 for offline swimming"
    )

    # Global arguments
    parser.add_argument(
        "-c", "--config",
        type=Path,
        default=Path.home() / ".spotify-swimmer" / "config.yaml",
        help="Path to config file (default: ~/.spotify-swimmer/config.yaml)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    # Subcommands
    subparsers = parser.add_subparsers(dest="command", required=True)

    # sync command
    subparsers.add_parser(
        "sync",
        help="Download new tracks and clean up orphans (no transfer)",
    )

    # transfer command
    subparsers.add_parser(
        "transfer",
        help="Interactive transfer to headphones",
    )

    return parser.parse_args(args)


def cmd_sync(config, verbose: bool) -> int:
    """Run sync command - download new tracks, cleanup orphans."""
    from spotify_swimmer.orchestrator import Orchestrator

    logger = logging.getLogger(__name__)
    orchestrator = Orchestrator(config)

    try:
        result = asyncio.run(orchestrator.run())
        if result.is_success:
            logger.info(f"Sync complete: {result.total_tracks} tracks")
            return 0
        elif result.has_errors:
            logger.warning(f"Sync completed with errors: {result.total_tracks} tracks")
            return 0
        else:
            logger.error("Sync failed")
            return 1
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        return 130
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        return 1


def cmd_transfer(config, verbose: bool) -> int:
    """Run transfer command - interactive headphones transfer."""
    from spotify_swimmer.transfer import InteractiveTransfer

    logger = logging.getLogger(__name__)

    try:
        transfer = InteractiveTransfer(config)
        return transfer.run()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        return 130
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        return 1


def main() -> int:
    args = parse_args()
    setup_logging(args.verbose)

    logger = logging.getLogger(__name__)

    try:
        config = load_config(args.config)
    except FileNotFoundError:
        logger.error(f"Config file not found: {args.config}")
        return 1
    except ValueError as e:
        logger.error(f"Invalid config: {e}")
        return 1

    if args.command == "sync":
        return cmd_sync(config, args.verbose)
    elif args.command == "transfer":
        return cmd_transfer(config, args.verbose)
    else:
        logger.error(f"Unknown command: {args.command}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
