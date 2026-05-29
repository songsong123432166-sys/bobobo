from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class CameraResult:
    available: bool
    person_present: bool | None
    message: str


class CameraPresenceDetector:
    def __init__(self, camera_index: int = 0) -> None:
        self.camera_index = camera_index
        self._cv2 = None
        self._cascade = None
        self._load_error: str | None = None
        self._load_cv2()

    def _load_cv2(self) -> None:
        try:
            import cv2

            self._cv2 = cv2
            cascade_path = Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
            if not cascade_path.exists():
                self._load_error = f"face cascade missing: {cascade_path}"
                return
            self._cascade = cv2.CascadeClassifier(cascade_path)
        except Exception as exc:
            self._load_error = str(exc)

    def check(self) -> CameraResult:
        if self._cv2 is None:
            return CameraResult(False, None, f"OpenCV unavailable: {self._load_error or 'not installed'}")

        cap = None
        try:
            cap = self._cv2.VideoCapture(self.camera_index, self._cv2.CAP_DSHOW)
            if not cap or not cap.isOpened():
                return CameraResult(False, None, "Camera unavailable")
            ok, frame = cap.read()
            if not ok or frame is None:
                return CameraResult(False, None, "Camera frame unavailable")

            gray = self._cv2.cvtColor(frame, self._cv2.COLOR_BGR2GRAY)
            faces = []
            if self._cascade is not None and not self._cascade.empty():
                faces = self._cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(48, 48))
            return CameraResult(True, len(faces) > 0, f"faces={len(faces)}")
        except Exception as exc:
            return CameraResult(False, None, str(exc))
        finally:
            try:
                if cap:
                    cap.release()
            except Exception:
                pass
