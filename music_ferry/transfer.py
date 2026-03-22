# music_ferry/transfer.py
import logging
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from music_ferry.config import Config
from music_ferry.library import Library, LibraryTrack

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


@dataclass
class TransferCandidate:
    track_id: str
    filename: str
    title: str
    artist: str
    size_bytes: int
    src_path: Path
    playlist_id: str
    playlist_name: str
    source: str


@dataclass
class TransferPlan:
    files_to_copy: list[TransferCandidate]
    files_to_remove: list[Path]
    bytes_to_copy: int
    bytes_to_remove: int
    budget_bytes: int


@dataclass
class PlaylistSelection:
    playlist_id: str
    playlist_name: str
    source: str
    max_bytes: int | None
    library: Library


@dataclass
class PlaylistCandidateGroup:
    playlist_id: str
    playlist_name: str
    source: str
    max_bytes: int | None
    existing_bytes: int
    candidates: list[TransferCandidate]


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
        config: Config,
        sources: list[str] | None = None,
        spotify_library: Library | None = None,
        youtube_library: Library | None = None,
        library: Library | None = None,  # Backward compatibility
        auto: bool = False,
    ):
        self.config = config
        self.sources = sources or ["spotify", "youtube"]
        self.auto = auto

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

        self.youtube_library = youtube_library or Library(youtube_base / "library.json")

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

    def _bytes_from_gb(self, value: float | None) -> int | None:
        if value is None:
            return None
        return int(value * 1024 * 1024 * 1024)

    def _get_reserve_free_bytes(self) -> int:
        reserve_gb_value: object = getattr(
            getattr(self.config, "transfer", None),
            "reserve_free_gb",
            0.0,
        )
        if isinstance(reserve_gb_value, int | float):
            reserve_gb = float(reserve_gb_value)
        else:
            reserve_gb = 0.0
        return self._bytes_from_gb(reserve_gb) or 0

    def _get_free_space_bytes(self) -> int:
        return shutil.disk_usage(self.headphones_path).free

    def _format_bytes(self, size_bytes: int) -> str:
        if size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        if size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"

    def _get_playlist_selections(self) -> list[PlaylistSelection]:
        selections: list[PlaylistSelection] = []

        def add_from_config(
            source: str,
            library: Library,
            configured_playlists: object,
        ) -> None:
            if isinstance(configured_playlists, list) and configured_playlists:
                for playlist in configured_playlists:
                    selections.append(
                        PlaylistSelection(
                            playlist_id=playlist.playlist_id,
                            playlist_name=playlist.name,
                            source=source,
                            max_bytes=self._bytes_from_gb(playlist.max_gb),
                            library=library,
                        )
                    )
                return

            for library_playlist in library.get_all_playlists():
                selections.append(
                    PlaylistSelection(
                        playlist_id=library_playlist.id,
                        playlist_name=library_playlist.name,
                        source=source,
                        max_bytes=None,
                        library=library,
                    )
                )

        if "spotify" in self.sources:
            add_from_config(
                "spotify",
                self.spotify_library,
                self.config.spotify.playlists,
            )
        if "youtube" in self.sources:
            add_from_config(
                "youtube",
                self.youtube_library,
                self.config.youtube.playlists,
            )

        return selections

    def _ordered_tracks_for_playlist(
        self,
        library: Library,
        playlist_id: str,
    ) -> list[LibraryTrack]:
        tracks = library.get_tracks_for_playlist(playlist_id)
        track_map = {track.id: track for track in tracks}
        playlist = library.get_playlist(playlist_id)
        ordered_ids = playlist.track_order if playlist else []
        ordered: list[LibraryTrack] = []
        for track_id in ordered_ids:
            track = track_map.pop(track_id, None)
            if track:
                ordered.append(track)

        remaining = sorted(
            track_map.values(),
            key=lambda t: (t.title.lower(), t.artist.lower(), t.id),
        )
        return ordered + remaining

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

    def _get_orphaned_files(self, full_reset: bool) -> list[Path]:
        if not self.headphones_path.exists():
            return []
        if full_reset:
            return list(self.headphones_path.glob("*.mp3"))
        local_filenames = set(self._get_local_files().keys())
        headphones_files = self._get_headphones_files()
        return [
            self.headphones_path / filename
            for filename in headphones_files - local_filenames
        ]

    def _build_transfer_candidates(
        self,
        headphones_files: set[str],
    ) -> list[PlaylistCandidateGroup]:
        candidates: list[PlaylistCandidateGroup] = []
        local_files = self._get_local_files()

        for playlist in self._get_playlist_selections():
            library = playlist.library
            playlist_id = playlist.playlist_id
            playlist_name = playlist.playlist_name
            ordered_tracks = self._ordered_tracks_for_playlist(library, playlist_id)
            playlist_candidates: list[TransferCandidate] = []
            existing_bytes = 0

            for track in ordered_tracks:
                filename = track.filename
                src = local_files.get(filename)
                if not src or not src.exists():
                    continue

                size_bytes = src.stat().st_size
                if filename in headphones_files:
                    existing_bytes += size_bytes
                    continue

                playlist_candidates.append(
                    TransferCandidate(
                        track_id=track.id,
                        filename=filename,
                        title=track.title,
                        artist=track.artist,
                        size_bytes=size_bytes,
                        src_path=src,
                        playlist_id=playlist_id,
                        playlist_name=playlist_name,
                        source=playlist.source,
                    )
                )

            candidates.append(
                PlaylistCandidateGroup(
                    playlist_id=playlist_id,
                    playlist_name=playlist_name,
                    source=playlist.source,
                    max_bytes=playlist.max_bytes,
                    existing_bytes=existing_bytes,
                    candidates=playlist_candidates,
                )
            )

        return candidates

    def _prompt_playlist_selection(
        self,
        playlists: list[PlaylistCandidateGroup],
    ) -> list[str]:
        print("\n--- Playlist Selection ---")
        for idx, playlist in enumerate(playlists, 1):
            total_size = sum(t.size_bytes for t in playlist.candidates)
            max_bytes = playlist.max_bytes
            max_label = (
                self._format_bytes(max_bytes) if max_bytes is not None else "none"
            )
            print(
                f"[{idx}] {playlist.playlist_name} "
                f"({playlist.source}): "
                f"{self._format_bytes(total_size)} new, "
                f"cap: {max_label}"
            )

        choice = (
            input("Select playlists (comma list, 'all', or 'none'): ").strip().lower()
        )
        if choice == "none":
            return []
        if choice == "all" or choice == "":
            return [playlist.playlist_id for playlist in playlists]

        selected_ids: list[str] = []
        parts = [p.strip() for p in choice.split(",") if p.strip()]
        for part in parts:
            if part.isdigit():
                idx = int(part)
                if 1 <= idx <= len(playlists):
                    selected_ids.append(playlists[idx - 1].playlist_id)
        return selected_ids

    def _prompt_track_selection_mode(self, playlist_name: str) -> str:
        choice = (
            input(
                f"Track selection for '{playlist_name}': " "[a]uto, [m]anual, [s]kip: "
            )
            .strip()
            .lower()
        )
        if choice in ("m", "manual"):
            return "manual"
        if choice in ("s", "skip"):
            return "skip"
        return "auto"

    def _select_tracks_for_playlist(
        self,
        playlist: PlaylistCandidateGroup,
        budget_bytes: int,
        playlist_budget_bytes: int | None,
        selected_filenames: set[str],
        manual: bool,
    ) -> tuple[list[TransferCandidate], int]:
        selected: list[TransferCandidate] = []
        used_bytes = 0
        for track in playlist.candidates:
            if track.filename in selected_filenames:
                continue

            remaining_budget = budget_bytes - used_bytes
            if remaining_budget <= 0:
                break

            if playlist_budget_bytes is not None:
                remaining_playlist = playlist_budget_bytes - used_bytes
                if remaining_playlist <= 0:
                    break
                if track.size_bytes > remaining_playlist:
                    logger.info(
                        "Skipping %s (%s): playlist cap reached",
                        track.filename,
                        self._format_bytes(track.size_bytes),
                    )
                    continue

            if track.size_bytes > remaining_budget:
                logger.info(
                    "Skipping %s (%s): reserve free cap reached",
                    track.filename,
                    self._format_bytes(track.size_bytes),
                )
                continue

            if manual:
                prompt = (
                    f"Include {track.title} - {track.artist} "
                    f"({self._format_bytes(track.size_bytes)})? [Y/n]: "
                )
                answer = input(prompt).strip().lower()
                if answer == "n":
                    logger.info("Skipped by user: %s", track.filename)
                    continue

            selected.append(track)
            selected_filenames.add(track.filename)
            used_bytes += track.size_bytes
            logger.info(
                "Selected: %s (%s)",
                track.filename,
                self._format_bytes(track.size_bytes),
            )

        return selected, used_bytes

    def _plan_transfer(
        self,
        full_reset: bool,
        auto: bool,
    ) -> TransferPlan:
        if not self.is_mounted():
            raise RuntimeError(
                f"Headphones not mounted at {self.config.paths.headphones_mount}"
            )

        if not auto and not sys.stdin.isatty():
            logger.info("No TTY detected; switching to auto selection")
            auto = True

        headphones_files = set() if full_reset else self._get_headphones_files()
        orphaned_files = self._get_orphaned_files(full_reset)
        bytes_to_remove = sum(f.stat().st_size for f in orphaned_files if f.exists())
        free_bytes = self._get_free_space_bytes()
        reserve_bytes = self._get_reserve_free_bytes()
        budget_bytes = max(free_bytes + bytes_to_remove - reserve_bytes, 0)

        logger.info(
            "Transfer budget: free=%s, remove=%s, reserve=%s, available=%s",
            self._format_bytes(free_bytes),
            self._format_bytes(bytes_to_remove),
            self._format_bytes(reserve_bytes),
            self._format_bytes(budget_bytes),
        )

        playlists = self._build_transfer_candidates(headphones_files)
        selected_files: list[TransferCandidate] = []
        selected_filenames: set[str] = set()
        total_selected_bytes = 0

        if not playlists:
            return TransferPlan(
                files_to_copy=[],
                files_to_remove=orphaned_files,
                bytes_to_copy=0,
                bytes_to_remove=bytes_to_remove,
                budget_bytes=budget_bytes,
            )

        unique_candidates: dict[str, int] = {}
        for playlist in playlists:
            for track in playlist.candidates:
                unique_candidates.setdefault(track.filename, track.size_bytes)

        total_unique_bytes = sum(unique_candidates.values())
        needs_prompt = total_unique_bytes > budget_bytes
        for playlist in playlists:
            max_bytes = playlist.max_bytes
            if max_bytes is not None:
                playlist_total = playlist.existing_bytes + sum(
                    t.size_bytes for t in playlist.candidates
                )
                if playlist_total > max_bytes:
                    needs_prompt = True
                    break

        if auto or not needs_prompt:
            selected_playlist_ids = [playlist.playlist_id for playlist in playlists]
        else:
            selected_playlist_ids = self._prompt_playlist_selection(playlists)

        for playlist in playlists:
            if playlist.playlist_id not in selected_playlist_ids:
                logger.info("Skipping playlist: %s", playlist.playlist_name)
                continue

            remaining_budget = budget_bytes - total_selected_bytes
            if remaining_budget <= 0:
                logger.info(
                    "Budget exhausted before playlist %s", playlist.playlist_name
                )
                break

            max_bytes = playlist.max_bytes
            playlist_budget = None
            if max_bytes is not None:
                selected_overlap = sum(
                    t.size_bytes
                    for t in playlist.candidates
                    if t.filename in selected_filenames
                )
                used_on_device = playlist.existing_bytes + selected_overlap
                playlist_budget = max(max_bytes - used_on_device, 0)

            playlist_new_bytes = sum(t.size_bytes for t in playlist.candidates)
            needs_trim = playlist_new_bytes > remaining_budget or (
                playlist_budget is not None and playlist_new_bytes > playlist_budget
            )

            manual = False
            if not auto and needs_trim:
                mode = self._prompt_track_selection_mode(playlist.playlist_name)
                if mode == "skip":
                    logger.info("Skipping playlist by user: %s", playlist.playlist_name)
                    continue
                manual = mode == "manual"

            chosen, used_bytes = self._select_tracks_for_playlist(
                playlist,
                remaining_budget,
                playlist_budget,
                selected_filenames,
                manual,
            )

            if chosen:
                selected_files.extend(chosen)
                total_selected_bytes += used_bytes

        return TransferPlan(
            files_to_copy=selected_files,
            files_to_remove=orphaned_files,
            bytes_to_copy=total_selected_bytes,
            bytes_to_remove=bytes_to_remove,
            budget_bytes=budget_bytes,
        )

    def _execute_plan(self, plan: TransferPlan) -> tuple[int, int]:
        files_copied = 0
        total_to_copy = len(plan.files_to_copy)
        for i, track in enumerate(plan.files_to_copy, 1):
            dst = self.headphones_path / track.filename
            if track.src_path.exists():
                logger.info(
                    "Copying (%d/%d): %s (%s)",
                    i,
                    total_to_copy,
                    track.filename,
                    self._format_bytes(track.size_bytes),
                )
                shutil.copy2(track.src_path, dst)
                files_copied += 1

        files_removed = 0
        total_to_remove = len(plan.files_to_remove)
        for i, orphan_path in enumerate(plan.files_to_remove, 1):
            if orphan_path.exists():
                logger.info(
                    "Removing (%d/%d): %s",
                    i,
                    total_to_remove,
                    orphan_path.name,
                )
                orphan_path.unlink()
                files_removed += 1

        logger.info(
            "Sync complete: %d copied (%s), %d removed (%s)",
            files_copied,
            self._format_bytes(plan.bytes_to_copy),
            files_removed,
            self._format_bytes(plan.bytes_to_remove),
        )
        return files_copied, files_removed

    def sync_changes(self, auto: bool | None = None) -> tuple[int, int]:
        """Sync changes to headphones: copy new files, remove orphans.

        Returns tuple of (files_copied, files_removed).
        """
        use_auto = self.auto if auto is None else auto
        plan = self._plan_transfer(full_reset=False, auto=use_auto)
        if plan.budget_bytes <= 0 and plan.bytes_to_copy > 0:
            logger.warning("Transfer skipped: reserve free space exceeded")
            return 0, 0
        return self._execute_plan(plan)

    def full_reset(self, auto: bool | None = None) -> int:
        """Delete all files on headphones and copy all tracks from selected sources.

        Returns count of files copied.
        """
        use_auto = self.auto if auto is None else auto
        plan = self._plan_transfer(full_reset=True, auto=use_auto)
        if plan.budget_bytes <= 0 and plan.bytes_to_copy > 0:
            logger.warning("Full reset skipped: reserve free space exceeded")
            return 0
        files_copied, _ = self._execute_plan(plan)
        return files_copied

    def run(self) -> int:
        """Run the interactive transfer menu. Returns exit code."""
        if not self.is_mounted():
            logger.error(
                f"Headphones not mounted at {self.config.paths.headphones_mount}"
            )
            print(f"\nHeadphones not mounted at {self.config.paths.headphones_mount}")
            print("Please connect your headphones and try again.")
            return 1

        if self.auto:
            copied, removed = self.sync_changes(auto=True)
            print(f"\nSynced: {copied} copied, {removed} removed")
            return 0

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
                print(f"  {playlist.name}: " f"{synced}/{playlist.total_tracks} synced")

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
            confirm = input(
                "This will delete ALL files on headphones. Continue? [y/N]: "
            )
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
