# music_ferry/cli.py
import argparse
import asyncio
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from music_ferry import __version__
from music_ferry.config import Config, load_config


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def configure_file_logging(config: Config, verbose: bool = False) -> None:
    log_dir = config.paths.music_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "sync.log"

    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        if isinstance(handler, RotatingFileHandler) and getattr(
            handler, "baseFilename", None
        ) == str(log_file):
            return

    level = logging.DEBUG if verbose else logging.INFO
    handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
    )
    handler.setLevel(level)
    handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )
    root_logger.addHandler(handler)


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


def _resolve_sources(args: argparse.Namespace, config: Config) -> tuple[bool, bool]:
    """Resolve which sources to process based on flags and config.
    Returns (sync_spotify, sync_youtube) booleans.
    """
    if not args.spotify and not args.youtube:
        return config.spotify.enabled, config.youtube.enabled
    return args.spotify, args.youtube


def _source_names(sync_spotify: bool, sync_youtube: bool) -> list[str]:
    """Convert source booleans into transfer source names."""
    sources: list[str] = []
    if sync_spotify:
        sources.append("spotify")
    if sync_youtube:
        sources.append("youtube")
    return sources


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


def cmd_sync(
    config: Config,
    verbose: bool,
    sync_spotify: bool = True,
    sync_youtube: bool = True,
) -> int:
    """Run sync command - download new tracks, cleanup orphans."""
    from music_ferry.orchestrator import Orchestrator

    logger = logging.getLogger(__name__)
    orchestrator = Orchestrator(config)

    try:
        result = asyncio.run(
            orchestrator.run(
                sync_spotify=sync_spotify,
                sync_youtube=sync_youtube,
            )
        )
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


def cmd_transfer(
    config: Config,
    verbose: bool,
    auto: bool,
    sources: list[str] | None = None,
) -> int:
    """Run transfer command - interactive headphones transfer."""
    from music_ferry.transfer import InteractiveTransfer

    logger = logging.getLogger(__name__)

    try:
        transfer = InteractiveTransfer(config, sources=sources, auto=auto)
        return transfer.run()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        return 130
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        return 1


def cmd_serve(config: Config, host: str, port: int, reload: bool) -> int:
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

    configure_file_logging(config, args.verbose)

    if args.command == "sync":
        sync_spotify, sync_youtube = _resolve_sources(args, config)
        return cmd_sync(
            config,
            args.verbose,
            sync_spotify=sync_spotify,
            sync_youtube=sync_youtube,
        )
    elif args.command == "transfer":
        sync_spotify, sync_youtube = _resolve_sources(args, config)
        return cmd_transfer(
            config,
            args.verbose,
            args.auto,
            sources=_source_names(sync_spotify, sync_youtube),
        )
    elif args.command == "serve":
        return cmd_serve(config, args.host, args.port, args.reload)
    else:
        logger.error(f"Unknown command: {args.command}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
