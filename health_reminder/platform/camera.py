from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from shutil import copyfile


@dataclass
class CameraResult:
    available: bool
    person_present: bool | None
    message: str


class CameraPresenceDetector:
    def __init__(self, camera_index: int = 0, sample_frames: int = 3, max_width: int = 640) -> None:
        self.camera_index = camera_index
        self.sample_frames = max(1, sample_frames)
        self.max_width = max(160, max_width)
        self._cv2 = None
        self._cascades = []
        self._load_error: str | None = None
        self._load_cv2()

    def _load_cv2(self) -> None:
        try:
            import cv2

            self._cv2 = cv2
            cascade_names = [
                "haarcascade_frontalface_default.xml",
                "haarcascade_profileface.xml",
            ]
            for name in cascade_names:
                cascade_path = Path(cv2.data.haarcascades) / name
                cascade = self._load_cascade(cascade_path)
                if cascade is not None:
                    self._cascades.append((name, cascade))
            if not self._cascades:
                self._load_error = f"face cascades failed to load: {Path(cv2.data.haarcascades)}"
        except Exception as exc:
            self._load_error = str(exc)

    def _load_cascade(self, cascade_path: Path):
        if not cascade_path.exists():
            return None
        load_path = self._opencv_safe_path(cascade_path)
        cascade = self._cv2.CascadeClassifier(str(load_path))
        if cascade.empty():
            cached_path = self._cache_cascade_for_opencv(cascade_path)
            if cached_path is not None:
                cascade = self._cv2.CascadeClassifier(str(cached_path))
        if cascade.empty():
            return None
        return cascade

    def _opencv_safe_path(self, path: Path) -> Path:
        try:
            str(path).encode("ascii")
            return path
        except UnicodeEncodeError:
            return self._cache_cascade_for_opencv(path) or path

    def _cache_cascade_for_opencv(self, cascade_path: Path) -> Path | None:
        candidates = [
            Path(r"C:\ProgramData\HealthTrayReminder"),
            Path(r"C:\Windows\Temp\HealthTrayReminder"),
        ]
        for folder in candidates:
            try:
                folder.mkdir(parents=True, exist_ok=True)
                target = folder / cascade_path.name
                if not target.exists() or target.stat().st_size != cascade_path.stat().st_size:
                    copyfile(cascade_path, target)
                if target.exists() and target.stat().st_size > 0:
                    return target
            except Exception:
                continue
        return None

    def check(self) -> CameraResult:
        if self._cv2 is None or not self._cascades:
            return CameraResult(False, None, f"OpenCV unavailable: {self._load_error or 'not installed'}")

        cap = None
        try:
            cap = self._cv2.VideoCapture(self.camera_index, self._cv2.CAP_DSHOW)
            if not cap or not cap.isOpened():
                return CameraResult(False, None, "Camera unavailable")
            self._prepare_capture(cap)

            frames_checked = 0
            best_faces = 0
            for _ in range(self.sample_frames):
                ok, frame = cap.read()
                if not ok or frame is None:
                    continue
                frames_checked += 1
                face_count = self._detect_face_count(frame)
                best_faces = max(best_faces, face_count)
                if face_count > 0:
                    return CameraResult(True, True, f"faces={face_count} frames={frames_checked}")

            if frames_checked == 0:
                return CameraResult(False, None, "Camera frame unavailable")
            return CameraResult(True, False, f"faces=0 frames={frames_checked}")
        except Exception as exc:
            return CameraResult(False, None, str(exc))
        finally:
            try:
                if cap:
                    cap.release()
            except Exception:
                pass

    def _prepare_capture(self, cap) -> None:
        try:
            cap.set(self._cv2.CAP_PROP_FRAME_WIDTH, self.max_width)
            cap.set(self._cv2.CAP_PROP_FRAME_HEIGHT, 480)
        except Exception:
            pass

    def _detect_face_count(self, frame) -> int:
        gray = self._cv2.cvtColor(frame, self._cv2.COLOR_BGR2GRAY)
        height, width = gray.shape[:2]
        if width > self.max_width:
            scale = self.max_width / width
            gray = self._cv2.resize(gray, (self.max_width, int(height * scale)))
        gray = self._cv2.equalizeHist(gray)
        flipped = self._cv2.flip(gray, 1)
        best_count = 0
        for _name, cascade in self._cascades:
            for image in (gray, flipped):
                faces = cascade.detectMultiScale(
                    image,
                    scaleFactor=1.08,
                    minNeighbors=5,
                    minSize=(44, 44),
                )
                best_count = max(best_count, len(faces))
                if best_count > 0:
                    return best_count
        return best_count
