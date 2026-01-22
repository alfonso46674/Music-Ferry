# tests/test_recorder.py
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock
import asyncio

import pytest

from spotify_swimmer.recorder import AudioRecorder, SINK_NAMES


class TestAudioRecorder:
    def test_sink_name_generation(self):
        recorder = AudioRecorder(bitrate=192)
        # Sink name should be from the predefined list
        assert recorder.sink_name in SINK_NAMES

    def test_custom_sink_name(self):
        recorder = AudioRecorder(bitrate=192, sink_name="custom_sink")
        assert recorder.sink_name == "custom_sink"

    @patch("spotify_swimmer.recorder.subprocess.run")
    def test_create_virtual_sink(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="123")

        recorder = AudioRecorder(bitrate=192)
        recorder.create_virtual_sink()

        mock_run.assert_called()
        call_args = str(mock_run.call_args)
        assert "pactl" in call_args
        assert "load-module" in call_args
        assert "module-null-sink" in call_args

    @patch("spotify_swimmer.recorder.subprocess.run")
    def test_destroy_virtual_sink(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)

        recorder = AudioRecorder(bitrate=192)
        recorder._module_id = 123
        recorder.destroy_virtual_sink()

        mock_run.assert_called()
        call_args = str(mock_run.call_args)
        assert "pactl" in call_args
        assert "unload-module" in call_args

    @patch("spotify_swimmer.recorder.subprocess.Popen")
    def test_start_recording(self, mock_popen, tmp_path: Path):
        mock_process = MagicMock()
        mock_popen.return_value = mock_process

        recorder = AudioRecorder(bitrate=192)
        output_path = tmp_path / "test.mp3"

        recorder.start_recording(output_path)

        mock_popen.assert_called_once()
        call_args = mock_popen.call_args[0][0]
        assert "ffmpeg" in call_args
        assert "-b:a" in call_args
        assert "192k" in call_args

    @patch("spotify_swimmer.recorder.subprocess.Popen")
    def test_stop_recording(self, mock_popen, tmp_path: Path):
        mock_process = MagicMock()
        mock_process.poll.return_value = None
        mock_popen.return_value = mock_process

        recorder = AudioRecorder(bitrate=192)
        output_path = tmp_path / "test.mp3"

        recorder.start_recording(output_path)
        recorder.stop_recording()

        mock_process.terminate.assert_called_once()
        mock_process.wait.assert_called_once()
