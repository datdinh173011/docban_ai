import io
import shutil
import subprocess
import sys
import threading
import time
import wave
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from fakeredis.aioredis import FakeRedis
from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.main import MAX_VOICE_UPLOAD_BYTES, create_app
from voice_ai import speech_to_text
from voice_ai.speech_to_text import SpeechToTextProcessor, normalize_to_wav16k

TEST_DATABASE_URL = "postgresql+asyncpg://test:test@localhost:5432/test"


class FakeProcessor:
    def __init__(self, *, available: bool = True, result: str = "xin chào", error: str | None = None) -> None:
        self.available = available
        self.result = result
        self.error = error
        self.unavailable_reason = None if available else "model_files_missing"
        self.calls: list[bytes] = []

    def preflight(self) -> bool:
        return self.available

    def transcribe(self, raw_audio: bytes) -> str:
        self.calls.append(raw_audio)
        if self.error:
            raise RuntimeError(self.error)
        return self.result


@pytest.fixture
def app():
    return create_app(
        Settings(environment="LOCAL", database_url=TEST_DATABASE_URL),
        FakeRedis(decode_responses=True),
    )


def _write_model_placeholders(model_dir: Path) -> None:
    for name in ("encoder.int8.onnx", "decoder.onnx", "joiner.int8.onnx", "tokens.txt"):
        (model_dir / name).write_bytes(b"test")


def test_default_model_dir_points_at_committed_zipformer() -> None:
    processor = SpeechToTextProcessor()
    assert processor.model_dir == Path(speech_to_text.__file__).resolve().parent / "zipformer"
    assert all(path.is_file() for path in processor.model_paths)


def test_preflight_reports_missing_model_files(tmp_path: Path) -> None:
    processor = SpeechToTextProcessor(tmp_path)
    assert processor.preflight() is False
    assert processor.unavailable_reason == "model_files_missing"


def test_preflight_checks_dependencies_and_ffmpeg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_model_placeholders(tmp_path)
    processor = SpeechToTextProcessor(tmp_path)
    monkeypatch.setattr(speech_to_text.importlib.util, "find_spec", lambda _name: object())
    monkeypatch.setattr(speech_to_text.shutil, "which", lambda _name: None)
    assert processor.preflight() is False
    assert processor.unavailable_reason == "ffmpeg_unavailable"


def test_normalize_maps_ffmpeg_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(speech_to_text.shutil, "which", lambda _name: "/usr/bin/ffmpeg")
    monkeypatch.setattr(
        speech_to_text.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=1, stdout=b""),
    )
    with pytest.raises(RuntimeError, match="audio_decode_failed"):
        normalize_to_wav16k(b"invalid")

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("ffmpeg", 30)

    monkeypatch.setattr(speech_to_text.subprocess, "run", timeout)
    with pytest.raises(RuntimeError, match="audio_decode_timeout"):
        normalize_to_wav16k(b"audio")


def test_recognizer_initializes_only_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_model_placeholders(tmp_path)
    calls = 0

    class OfflineRecognizer:
        @staticmethod
        def from_transducer(**kwargs):
            nonlocal calls
            calls += 1
            return object()

    processor = SpeechToTextProcessor(tmp_path)
    monkeypatch.setattr(processor, "preflight", lambda: True)
    monkeypatch.setitem(sys.modules, "sherpa_onnx", SimpleNamespace(OfflineRecognizer=OfflineRecognizer))
    monkeypatch.setitem(sys.modules, "soundfile", SimpleNamespace())

    assert processor.initialize_if_needed() is True
    assert processor.initialize_if_needed() is True
    assert calls == 1


def test_transcriptions_are_serialized(monkeypatch: pytest.MonkeyPatch) -> None:
    active = 0
    max_active = 0
    guard = threading.Lock()

    class Stream:
        result = SimpleNamespace(text="xin chào")

        def accept_waveform(self, sample_rate, data) -> None:
            assert sample_rate == 16000
            assert data.dtype == np.float32

    class Recognizer:
        def create_stream(self):
            return Stream()

        def decode_stream(self, stream) -> None:
            nonlocal active, max_active
            with guard:
                active += 1
                max_active = max(max_active, active)
            time.sleep(0.02)
            with guard:
                active -= 1

    processor = SpeechToTextProcessor()
    processor.is_ready = True
    processor.recognizer = Recognizer()
    processor._soundfile = SimpleNamespace(read=lambda *args, **kwargs: (np.ones(160, dtype=np.float32), 16000))
    monkeypatch.setattr(speech_to_text, "normalize_to_wav16k", lambda raw: raw)

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(processor.transcribe, (b"one", b"two")))

    assert results == ["xin chào", "xin chào"]
    assert max_active == 1


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is not installed")
def test_real_ffmpeg_normalization_outputs_mono_16khz_wav() -> None:
    source = io.BytesIO()
    with wave.open(source, "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(8000)
        wav.writeframes(b"\x00\x00" * 2 * 800)

    normalized = normalize_to_wav16k(source.getvalue())
    import soundfile

    data, sample_rate = soundfile.read(io.BytesIO(normalized), always_2d=True)
    assert sample_rate == 16000
    assert data.shape[1] == 1


@pytest.mark.asyncio
async def test_voice_status_is_stateless(app) -> None:
    async with app.router.lifespan_context(app):
        app.state.speech_to_text = FakeProcessor()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/voice/status")
    assert response.status_code == 200
    assert response.json() == {"available": True}
    assert "set-cookie" not in response.headers


@pytest.mark.asyncio
async def test_voice_transcription_returns_text(app) -> None:
    processor = FakeProcessor(result="tôi cần đăng ký khai sinh")
    async with app.router.lifespan_context(app):
        app.state.speech_to_text = processor
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/voice/transcribe",
                files={"file": ("voice.webm", b"audio", "audio/webm")},
            )
    assert response.status_code == 200
    assert response.json() == {"text": "tôi cần đăng ký khai sinh"}
    assert processor.calls == [b"audio"]


@pytest.mark.asyncio
async def test_voice_transcription_returns_503_when_unavailable(app) -> None:
    async with app.router.lifespan_context(app):
        app.state.speech_to_text = FakeProcessor(available=False)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/voice/transcribe",
                files={"file": ("voice.webm", b"audio", "audio/webm")},
            )
    assert response.status_code == 503
    assert response.json() == {"detail": "voice_unavailable"}


@pytest.mark.asyncio
async def test_voice_transcription_rejects_large_upload(app) -> None:
    async with app.router.lifespan_context(app):
        app.state.speech_to_text = FakeProcessor()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/voice/transcribe",
                files={"file": ("voice.webm", b"x" * (MAX_VOICE_UPLOAD_BYTES + 1), "audio/webm")},
            )
    assert response.status_code == 413
    assert response.json() == {"detail": "audio_too_large"}


@pytest.mark.asyncio
@pytest.mark.parametrize("error_code", ["audio_decode_failed", "audio_too_long", "transcript_empty"])
async def test_voice_transcription_maps_client_errors_to_422(app, error_code: str) -> None:
    async with app.router.lifespan_context(app):
        app.state.speech_to_text = FakeProcessor(error=error_code)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/voice/transcribe",
                files={"file": ("voice.webm", b"audio", "audio/webm")},
            )
    assert response.status_code == 422
    assert response.json() == {"detail": error_code}
