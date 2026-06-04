"""Sound playback for reminder alerts."""

from __future__ import annotations

import tempfile
import threading
import time
import wave
from pathlib import Path
from shutil import copyfile

from ..core.paths import resource_path

_RIBBIT_PATH = resource_path("assets/ribbit.wav")
_CACHE_DIR = Path(tempfile.gettempdir()) / "HealthTrayReminder" / "sounds"
_LOCK = threading.Lock()
_LAST_PLAY = 0.0
_MIN_INTERVAL = 2.0


def play_ribbit(volume_percent: int = 80) -> None:
    """Play the reminder sound asynchronously without changing system volume."""
    global _LAST_PLAY

    volume = _clamp_volume(volume_percent)
    if volume <= 0:
        return

    now = time.monotonic()
    with _LOCK:
        if now - _LAST_PLAY < _MIN_INTERVAL:
            return
        _LAST_PLAY = now

    thread = threading.Thread(target=_play_sync, args=(volume,), daemon=True)
    thread.start()


def _play_sync(volume_percent: int) -> None:
    """同步播放提示音，根据音量百分比调整WAV音量。"""
    try:
        import winsound

        sound_path = _volume_adjusted_wav(_RIBBIT_PATH, volume_percent)
        winsound.PlaySound(str(sound_path), winsound.SND_FILENAME | winsound.SND_ASYNC)
    except (OSError, RuntimeError):
        pass


def _clamp_volume(volume_percent: int) -> int:
    """将音量百分比限制在0-100范围内。"""
    try:
        return max(0, min(100, int(volume_percent)))
    except (TypeError, ValueError):
        return 80


def _volume_adjusted_wav(source: Path, volume_percent: int) -> Path:
    """根据音量百分比调整WAV文件音量，返回临时文件路径。"""
    if volume_percent >= 100:
        return source

    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    target = _CACHE_DIR / f"{source.stem}_{volume_percent:03d}.wav"
    if target.exists() and target.stat().st_mtime >= source.stat().st_mtime:
        return target

    try:
        with wave.open(str(source), "rb") as reader:
            params = reader.getparams()
            frames = reader.readframes(reader.getnframes())
        adjusted = _scale_pcm(frames, params.sampwidth, volume_percent / 100)
        with wave.open(str(target), "wb") as writer:
            writer.setparams(params)
            writer.writeframes(adjusted)
        return target
    except Exception:
        copyfile(source, target)
        return target


def _scale_pcm(frames: bytes, sample_width: int, factor: float) -> bytes:
    """按比例缩放PCM音频数据的振幅。"""
    if sample_width == 1:
        return bytes(max(0, min(255, round((sample - 128) * factor + 128))) for sample in frames)

    if sample_width not in {2, 4}:
        return frames

    limit = 2 ** (sample_width * 8 - 1)
    output = bytearray(len(frames))
    for index in range(0, len(frames), sample_width):
        sample = int.from_bytes(frames[index : index + sample_width], "little", signed=True)
        scaled = max(-limit, min(limit - 1, round(sample * factor)))
        output[index : index + sample_width] = int(scaled).to_bytes(
            sample_width, "little", signed=True
        )
    return bytes(output)
