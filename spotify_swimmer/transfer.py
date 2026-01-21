# spotify_swimmer/transfer.py
import shutil
import subprocess
from pathlib import Path


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
