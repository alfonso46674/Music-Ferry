# spotify_swimmer/transfer.py
import logging
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from spotify_swimmer.library import Library

logger = logging.getLogger(__name__)


@dataclass
class PlaylistStatus:
    name: str
    total_tracks: int
    new_tracks: int
    source: str = "spotify"
    track_details: list[tuple[str, str, str]] = field(default_factory=list)
    # track_details: (track_id, title - artist, status: "synced"/"new")


@dataclass
class TransferStatus:
    local_track_count: int
    headphones_track_count: int
    new_to_transfer: int
    orphaned_on_headphones: int
    playlists: list[PlaylistStatus] = field(default_factory=list)
    orphaned_files: list[str] = field(default_factory=list)


class TransferManager:
    def __init__(self, headphones_mount: Path, headphones_music_folder: str):
        self.headphones_mount = headphones_mount
        self.headphones_music_folder = headphones_music_folder

    @property
    def destination_path(self) -> Path:
        return self.headphones_mount / self.headphones_music_folder

    def is_mounted(self) -> bool:
        return self.headphones_mount.exists() and self.destination_path.exists()

    def transfer(self, source_dir: Path) -> int:
        if not self.is_mounted():
            raise RuntimeError(f"Headphones not mounted at {self.headphones_mount}")

        # Count mp3 files to transfer
        mp3_files = list(source_dir.glob("*.mp3"))

        # Use rsync for efficient transfer
        result = subprocess.run(
            [
                "rsync",
                "-av",
                "--ignore-existing",
                f"{source_dir}/",
                f"{self.destination_path}/",
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise RuntimeError(f"rsync failed: {result.stderr}")

        # Return count of source files (actual transferred may vary)
        return len(mp3_files)


class InteractiveTransfer:
    def __init__(
        self,
        config,
        sources: list[str] | None = None,
        spotify_library: Library | None = None,
        youtube_library: Library | None = None,
        library: Library | None = None,  # Backward compatibility
    ):
        self.config = config
        self.sources = sources or ["spotify", "youtube"]

        # Setup base directories
        spotify_base = config.paths.music_dir / "spotify"
        youtube_base = config.paths.music_dir / "youtube"

        # Setup libraries (backward compatible - if only library is passed, use it as spotify)
        if library is not None and spotify_library is None:
            self.spotify_library = library
        else:
            self.spotify_library = spotify_library or Library(
                spotify_base / "library.json"
            )

        self.youtube_library = youtube_library or Library(
            youtube_base / "library.json"
        )

        # Setup music directories
        self.spotify_music_dir = spotify_base / "music"
        self.youtube_music_dir = youtube_base / "music"

        self.headphones_path = (
            config.paths.headphones_mount / config.paths.headphones_music_folder
        )

    def is_mounted(self) -> bool:
        return (
            self.config.paths.headphones_mount.exists()
            and self.headphones_path.exists()
        )

    def _get_headphones_files(self) -> set[str]:
        """Get set of MP3 filenames on headphones."""
        if not self.headphones_path.exists():
            return set()
        return {f.name for f in self.headphones_path.glob("*.mp3")}

    def _get_local_files(self) -> dict[str, Path]:
        """Get dict of MP3 filenames to paths from selected source libraries."""
        files: dict[str, Path] = {}

        if "spotify" in self.sources:
            for track in self.spotify_library.get_all_tracks():
                files[track.filename] = self.spotify_music_dir / track.filename

        if "youtube" in self.sources:
            for track in self.youtube_library.get_all_tracks():
                files[track.filename] = self.youtube_music_dir / track.filename

        return files

    def _get_local_filenames(self) -> set[str]:
        """Get set of MP3 filenames from selected source libraries."""
        return set(self._get_local_files().keys())

    def compute_status(self) -> TransferStatus:
        """Compute current transfer status."""
        local_filenames = self._get_local_filenames()
        headphones_files = self._get_headphones_files()

        new_to_transfer = local_filenames - headphones_files
        orphaned_on_headphones = headphones_files - local_filenames

        # Build playlist status from selected sources
        playlists = []

        if "spotify" in self.sources:
            for playlist in self.spotify_library.get_all_playlists():
                tracks = self.spotify_library.get_tracks_for_playlist(playlist.id)
                details = []
                new_count = 0

                for track in tracks:
                    if track.filename in headphones_files:
                        status = "synced"
                    else:
                        status = "new"
                        new_count += 1
                    details.append(
                        (track.id, f"{track.title} - {track.artist}", status)
                    )

                playlists.append(
                    PlaylistStatus(
                        name=playlist.name,
                        total_tracks=len(tracks),
                        new_tracks=new_count,
                        source="spotify",
                        track_details=details,
                    )
                )

        if "youtube" in self.sources:
            for playlist in self.youtube_library.get_all_playlists():
                tracks = self.youtube_library.get_tracks_for_playlist(playlist.id)
                details = []
                new_count = 0

                for track in tracks:
                    if track.filename in headphones_files:
                        status = "synced"
                    else:
                        status = "new"
                        new_count += 1
                    details.append(
                        (track.id, f"{track.title} - {track.artist}", status)
                    )

                playlists.append(
                    PlaylistStatus(
                        name=playlist.name,
                        total_tracks=len(tracks),
                        new_tracks=new_count,
                        source="youtube",
                        track_details=details,
                    )
                )

        return TransferStatus(
            local_track_count=len(local_filenames),
            headphones_track_count=len(headphones_files),
            new_to_transfer=len(new_to_transfer),
            orphaned_on_headphones=len(orphaned_on_headphones),
            playlists=playlists,
            orphaned_files=list(orphaned_on_headphones),
        )

    def sync_changes(self) -> tuple[int, int]:
        """Sync changes to headphones: copy new files, remove orphans.

        Returns tuple of (files_copied, files_removed).
        """
        if not self.is_mounted():
            raise RuntimeError(
                f"Headphones not mounted at {self.config.paths.headphones_mount}"
            )

        local_files = self._get_local_files()
        local_filenames = set(local_files.keys())
        headphones_files = self._get_headphones_files()

        new_to_transfer = local_filenames - headphones_files
        orphaned_on_headphones = headphones_files - local_filenames

        logger.info(
            f"Syncing: {len(new_to_transfer)} to copy, "
            f"{len(orphaned_on_headphones)} to remove"
        )

        # Copy new files from correct source directories
        files_copied = 0
        total_to_copy = len(new_to_transfer)
        for i, filename in enumerate(new_to_transfer, 1):
            src = local_files[filename]
            dst = self.headphones_path / filename
            if src.exists():
                logger.info(f"Copying ({i}/{total_to_copy}): {filename}")
                shutil.copy2(src, dst)
                files_copied += 1

        # Remove orphans
        files_removed = 0
        total_to_remove = len(orphaned_on_headphones)
        for i, filename in enumerate(orphaned_on_headphones, 1):
            orphan_path = self.headphones_path / filename
            if orphan_path.exists():
                logger.info(f"Removing ({i}/{total_to_remove}): {filename}")
                orphan_path.unlink()
                files_removed += 1

        logger.info(f"Sync complete: {files_copied} copied, {files_removed} removed")
        return files_copied, files_removed

    def full_reset(self) -> int:
        """Delete all files on headphones and copy all tracks from selected sources.

        Returns count of files copied.
        """
        if not self.is_mounted():
            raise RuntimeError(
                f"Headphones not mounted at {self.config.paths.headphones_mount}"
            )

        logger.info("Starting full reset of headphones...")

        # Delete all MP3s on headphones
        existing_files = list(self.headphones_path.glob("*.mp3"))
        total_to_delete = len(existing_files)
        if total_to_delete > 0:
            logger.info(f"Deleting {total_to_delete} files from headphones...")
        for i, mp3_file in enumerate(existing_files, 1):
            logger.info(f"Deleting ({i}/{total_to_delete}): {mp3_file.name}")
            mp3_file.unlink()

        # Copy all tracks from selected sources
        local_files = self._get_local_files()
        total_to_copy = len(local_files)
        files_copied = 0
        for i, (filename, src_path) in enumerate(local_files.items(), 1):
            dst = self.headphones_path / filename
            if src_path.exists():
                logger.info(f"Copying ({i}/{total_to_copy}): {filename}")
                shutil.copy2(src_path, dst)
                files_copied += 1

        logger.info(f"Full reset complete: {files_copied} files copied")
        return files_copied

    def run(self) -> int:
        """Run the interactive transfer menu. Returns exit code."""
        if not self.is_mounted():
            logger.error(
                f"Headphones not mounted at {self.config.paths.headphones_mount}"
            )
            print(
                f"\nHeadphones not mounted at {self.config.paths.headphones_mount}"
            )
            print("Please connect your headphones and try again.")
            return 1

        status = self.compute_status()

        # Display status
        print("\n=== Transfer Status ===")
        print(f"Local library: {status.local_track_count} tracks")
        print(f"On headphones: {status.headphones_track_count} tracks")
        print(f"New to transfer: {status.new_to_transfer}")
        print(f"Orphaned on headphones: {status.orphaned_on_headphones}")

        if status.playlists:
            print("\n--- Playlists ---")
            for playlist in status.playlists:
                synced = playlist.total_tracks - playlist.new_tracks
                print(
                    f"  {playlist.name}: "
                    f"{synced}/{playlist.total_tracks} synced"
                )

        if status.orphaned_files:
            print("\n--- Orphaned files ---")
            for filename in status.orphaned_files[:5]:
                print(f"  {filename}")
            if len(status.orphaned_files) > 5:
                print(f"  ... and {len(status.orphaned_files) - 5} more")

        # Show menu
        print("\n=== Options ===")
        print("[1] Sync changes (copy new, remove orphans)")
        print("[2] Full reset (delete all, copy fresh)")
        print("[3] View detailed status")
        print("[q] Quit")

        choice = input("\nSelect option: ").strip().lower()

        if choice == "1":
            copied, removed = self.sync_changes()
            print(f"\nSynced: {copied} copied, {removed} removed")
        elif choice == "2":
            confirm = input("This will delete ALL files on headphones. Continue? [y/N]: ")
            if confirm.lower() == "y":
                copied = self.full_reset()
                print(f"\nReset complete: {copied} files copied")
            else:
                print("Cancelled")
        elif choice == "3":
            self._show_detailed_status(status)
        elif choice == "q":
            print("Goodbye!")
        else:
            print("Invalid option")

        return 0

    def _show_detailed_status(self, status: TransferStatus) -> None:
        """Display detailed status by playlist."""
        print("\n=== Detailed Status ===")
        for playlist in status.playlists:
            print(f"\n{playlist.name}:")
            for track_id, title, track_status in playlist.track_details:
                marker = "✓" if track_status == "synced" else "○"
                print(f"  {marker} {title}")
