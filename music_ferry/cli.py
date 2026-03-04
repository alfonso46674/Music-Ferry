# music_ferry/cli.py
import argparse
import asyncio
import logging
import sys
from pathlib import Path

from music_ferry import __version__
from music_ferry.config import load_config


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def _add_source_flags(parser: argparse.ArgumentParser) -> None:
    """Add --spotify and --youtube flags to a subparser."""
    parser.add_argument(
        "--spotify",
        action="store_true",
        help="Only process Spotify playlists",
    )
    parser.add_argument(
        "--youtube",
        action="store_true",
        help="Only process YouTube playlists",
    )


def _resolve_sources(args: argparse.Namespace, config) -> tuple[bool, bool]:
    """Resolve which sources to process based on flags and config.
    Returns (sync_spotify, sync_youtube) booleans.
    """
    if not args.spotify and not args.youtube:
        return config.spotify.enabled, config.youtube.enabled
    return args.spotify, args.youtube


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ferry Spotify and YouTube playlists to MP3 for offline listening"
    )

    # Global arguments
    parser.add_argument(
        "-c",
        "--config",
        type=Path,
        default=Path.home() / ".music-ferry" / "config.yaml",
        help="Path to config file (default: ~/.music-ferry/config.yaml)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="Show version and exit",
    )

    # Subcommands
    subparsers = parser.add_subparsers(dest="command", required=True)

    # sync command
    sync_parser = subparsers.add_parser(
        "sync",
        help="Download new tracks and clean up orphans (no transfer)",
    )
    _add_source_flags(sync_parser)

    # transfer command
    transfer_parser = subparsers.add_parser(
        "transfer",
        help="Interactive transfer to headphones",
    )
    _add_source_flags(transfer_parser)
    transfer_parser.add_argument(
        "--auto",
        action="store_true",
        help="Run transfer without prompts (auto-select to fit size limits)",
    )

    # serve command (web UI)
    serve_parser = subparsers.add_parser(
        "serve",
        help="Start the web UI server",
    )
    serve_parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host to bind to (default: 127.0.0.1)",
    )
    serve_parser.add_argument(
        "--port",
        type=int,
        default=4444,
        help="Port to listen on (default: 4444)",
    )
    serve_parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development",
    )

    return parser.parse_args(args)


def cmd_sync(config, verbose: bool) -> int:
    """Run sync command - download new tracks, cleanup orphans."""
    from music_ferry.orchestrator import Orchestrator

    logger = logging.getLogger(__name__)
    orchestrator = Orchestrator(config)

    try:
        result = asyncio.run(orchestrator.run())
        if result.is_success:
            if result.total_tracks == 0:
                logger.info("Already up to date. No new tracks to sync.")
            else:
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


def cmd_transfer(config, verbose: bool, auto: bool) -> int:
    """Run transfer command - interactive headphones transfer."""
    from music_ferry.transfer import InteractiveTransfer

    logger = logging.getLogger(__name__)

    try:
        transfer = InteractiveTransfer(config, auto=auto)
        return transfer.run()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        return 130
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        return 1


def cmd_serve(config, host: str, port: int, reload: bool) -> int:
    """Run serve command - start the web UI server."""
    import uvicorn

    from music_ferry.web import create_app

    logger = logging.getLogger(__name__)
    logger.info(f"Starting Music Ferry web UI on http://{host}:{port}")

    try:
        app = create_app(config)
        uvicorn.run(
            app,
            host=host,
            port=port,
            reload=reload,
            log_level="info" if not reload else "debug",
        )
        return 0
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
        return 130
    except Exception as e:
        logger.exception(f"Server error: {e}")
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
        return cmd_transfer(config, args.verbose, args.auto)
    elif args.command == "serve":
        return cmd_serve(config, args.host, args.port, args.reload)
    else:
        logger.error(f"Unknown command: {args.command}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
