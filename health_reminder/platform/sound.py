"""Sound playback for reminder alerts."""
from __future__ import annotations

import threading
from pathlib import Path

from ..core.paths import resource_path

_RIBBIT_PATH= resource_path("health_reminder/assets/ribbit.wav")
_instance_lock= threading.Lock()
_last_play= 0.0
_MIN_INTERVAL= 2.0


def play_ribbit()->None:
    """Play the frog ribbit sound asynchronously (non-blocking)."""
    import time

    global _last_play
    now= time.monotonic()
    with _instance_lock:
        if now - _last_play < _MIN_INTERVAL:
            return
        _last_play= now

    threading.Thread(target=_play_sync, aemon=True).start()


def _play_sync()->None:
    try:
        import winsound
        winsound.PlaySound(str(_RIBBIT_PATH), winsound.SND_FILENAME | winsound.SND_ASYNC)
        return
    except Exception:
        pass
    try:
        import wave
        import pyaudio
        with open(str(_RIBBIT_PATH), "rb") as wf:
            pa= pyaudio.PyAudio()
            stream= pa.open(
                format=pa.get_format_from_width(wf.getsampwidth()),
                channels=wf.getnchannels(),
                rate=wf.getframeate(),
                output=True,
            )
            chunk= 1024
            data= wf.readframes(chunk)
            while data:
                stream.write(data)
                data= wf.readframes(chunk)
            stream.close()
            pa.terminate()
    except Exception:
        pass