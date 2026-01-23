# music_ferry/recorder.py
import random
import subprocess
from pathlib import Path


# Generic sink names that look like standard audio devices
SINK_NAMES = [
    "alsa_output.virtual",
    "pulse_sink_0",
    "audio_loopback",
    "virtual_output",
    "monitor_sink",
]

# Generic descriptions that look like standard audio devices
SINK_DESCRIPTIONS = [
    "Built-in Audio Analog Stereo",
    "Virtual Output Device",
    "Audio Adapter",
    "Digital Audio Output",
]


class AudioRecorder:
    def __init__(self, bitrate: int = 192, sink_name: str | None = None):
        self.bitrate = bitrate
        # Use provided sink name or pick a random generic one
        self.sink_name = sink_name or random.choice(SINK_NAMES)
        self._sink_description = random.choice(SINK_DESCRIPTIONS)
        self._module_id: int | None = None
        self._ffmpeg_process: subprocess.Popen | None = None

    def create_virtual_sink(self) -> None:
        result = subprocess.run(
            [
                "pactl",
                "load-module",
                "module-null-sink",
                f"sink_name={self.sink_name}",
                f"sink_properties=device.description={self._sink_description}",
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            self._module_id = int(result.stdout.strip())

    def destroy_virtual_sink(self) -> None:
        if self._module_id is not None:
            subprocess.run(
                ["pactl", "unload-module", str(self._module_id)],
                capture_output=True,
            )
            self._module_id = None

    def get_monitor_source(self) -> str:
        return f"{self.sink_name}.monitor"

    def start_recording(self, output_path: Path) -> None:
        monitor_source = self.get_monitor_source()

        self._ffmpeg_process = subprocess.Popen(
            [
                "ffmpeg",
                "-y",
                "-f", "pulse",
                "-i", monitor_source,
                "-ac", "2",
                "-ar", "44100",
                "-b:a", f"{self.bitrate}k",
                "-f", "mp3",
                str(output_path),
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def stop_recording(self) -> None:
        if self._ffmpeg_process is not None:
            if self._ffmpeg_process.poll() is None:
                self._ffmpeg_process.terminate()
                self._ffmpeg_process.wait(timeout=5)
            self._ffmpeg_process = None

    def __enter__(self):
        self.create_virtual_sink()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop_recording()
        self.destroy_virtual_sink()
