from __future__ import annotations

import importlib.util
import io
import logging
import os
import shutil
import subprocess
import threading
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

MAX_AUDIO_SECONDS = 60
FFMPEG_OUTPUT_LIMIT_SECONDS = MAX_AUDIO_SECONDS + 1
FFMPEG_TIMEOUT_SECONDS = 30


def normalize_to_wav16k(raw_bytes: bytes) -> bytes:
    """Convert browser audio into bounded 16 kHz mono PCM WAV bytes."""
    if not raw_bytes:
        raise RuntimeError("audio_empty")
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg_unavailable")

    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        "pipe:0",
        "-t",
        str(FFMPEG_OUTPUT_LIMIT_SECONDS),
        "-ar",
        "16000",
        "-ac",
        "1",
        "-c:a",
        "pcm_s16le",
        "-f",
        "wav",
        "pipe:1",
    ]
    try:
        result = subprocess.run(
            command,
            input=raw_bytes,
            capture_output=True,
            check=False,
            timeout=FFMPEG_TIMEOUT_SECONDS,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("ffmpeg_unavailable") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("audio_decode_timeout") from exc

    if result.returncode != 0 or not result.stdout:
        raise RuntimeError("audio_decode_failed")
    return result.stdout


class SpeechToTextProcessor:
    def __init__(self, model_dir: str | Path | None = None) -> None:
        self.model_dir = Path(model_dir or Path(__file__).resolve().parent / "zipformer")
        self.encoder_path = self.model_dir / "encoder.int8.onnx"
        self.decoder_path = self.model_dir / "decoder.onnx"
        self.joiner_path = self.model_dir / "joiner.int8.onnx"
        self.tokens_path = self.model_dir / "tokens.txt"
        self.is_ready = False
        self.recognizer = None
        self.unavailable_reason: str | None = None
        self._lock = threading.Lock()
        self._sherpa_onnx = None
        self._soundfile = None

    @property
    def model_paths(self) -> tuple[Path, ...]:
        return (
            self.encoder_path,
            self.decoder_path,
            self.joiner_path,
            self.tokens_path,
        )

    def preflight(self) -> bool:
        """Check capability without loading the ONNX model into memory."""
        if self.unavailable_reason == "initialization_failed":
            return False

        missing = [path.name for path in self.model_paths if not path.is_file()]
        if missing:
            self.unavailable_reason = "model_files_missing"
            return False
        if importlib.util.find_spec("sherpa_onnx") is None or importlib.util.find_spec("soundfile") is None:
            self.unavailable_reason = "dependencies_missing"
            return False
        if shutil.which("ffmpeg") is None:
            self.unavailable_reason = "ffmpeg_unavailable"
            return False

        self.unavailable_reason = None
        return True

    def initialize_if_needed(self) -> bool:
        """Load optional packages and the recognizer on the first transcription."""
        if self.is_ready:
            return True
        if not self.preflight():
            return False

        with self._lock:
            if self.is_ready:
                return True
            try:
                import sherpa_onnx
                import soundfile

                self._sherpa_onnx = sherpa_onnx
                self._soundfile = soundfile
                self.recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
                    tokens=os.fspath(self.tokens_path),
                    encoder=os.fspath(self.encoder_path),
                    decoder=os.fspath(self.decoder_path),
                    joiner=os.fspath(self.joiner_path),
                    num_threads=1,
                    sample_rate=16000,
                    feature_dim=80,
                    decoding_method="greedy_search",
                )
                self.is_ready = True
                logger.info("voice_stt_initialized model_dir=%s", self.model_dir)
                return True
            except Exception:
                self.unavailable_reason = "initialization_failed"
                logger.exception("voice_stt_initialization_failed model_dir=%s", self.model_dir)
                return False

    def transcribe(self, raw_bytes: bytes) -> str:
        """Normalize and transcribe one bounded audio clip."""
        normalized = normalize_to_wav16k(raw_bytes)
        if not self.initialize_if_needed():
            raise RuntimeError("stt_unavailable")

        with self._lock:
            try:
                data, sample_rate = self._soundfile.read(
                    io.BytesIO(normalized),
                    dtype="float32",
                    always_2d=False,
                )
            except Exception as exc:
                raise RuntimeError("audio_decode_failed") from exc

            if data.size == 0 or sample_rate <= 0:
                raise RuntimeError("audio_empty")
            duration_seconds = data.shape[0] / sample_rate
            if duration_seconds > MAX_AUDIO_SECONDS:
                raise RuntimeError("audio_too_long")
            if data.ndim > 1:
                data = np.mean(data, axis=1)
            data = np.asarray(data, dtype=np.float32)
            if not np.isfinite(data).all():
                raise RuntimeError("audio_decode_failed")

            stream = self.recognizer.create_stream()
            stream.accept_waveform(sample_rate, data)
            self.recognizer.decode_stream(stream)
            transcript = stream.result.text.strip()

        if not transcript:
            raise RuntimeError("transcript_empty")
        return transcript
