from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from shutil import copyfile

from ..core.paths import resource_path


@dataclass
class CameraResult:
    available: bool
    person_present: bool | None
    message: str


class CameraPresenceDetector:
    def __init__(self, camera_index: int = 0, sample_frames: int = 5, max_width: int = 800) -> None:
        self.camera_index = camera_index
        self.sample_frames = max(1, sample_frames)
        self.max_width = max(160, max_width)
        self._cv2 = None
        self._yunet = None
        self._hog = None
        self._cascades = []
        self._load_error: str | None = None
        self._load_cv2()

    def _load_cv2(self) -> None:
        try:
            import cv2

            self._cv2 = cv2
            self._load_yunet()
            self._load_hog_people_detector()
            cascade_names = [
                "haarcascade_frontalface_default.xml",
                "haarcascade_profileface.xml",
                "haarcascade_upperbody.xml",
                "haarcascade_fullbody.xml",
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

    def _load_hog_people_detector(self) -> None:
        try:
            if not hasattr(self._cv2, "HOGDescriptor"):
                return
            hog = self._cv2.HOGDescriptor()
            hog.setSVMDetector(self._cv2.HOGDescriptor_getDefaultPeopleDetector())
            self._hog = hog
        except Exception:
            self._hog = None

    def _load_yunet(self) -> None:
        if not hasattr(self._cv2, "FaceDetectorYN"):
            return
        model_path = resource_path("models/face_detection_yunet_2023mar.onnx")
        if not model_path.exists():
            return
        safe_path = self._opencv_safe_path(model_path)
        try:
            self._yunet = self._cv2.FaceDetectorYN.create(
                str(safe_path),
                "",
                (self.max_width, 480),
                score_threshold=0.45,
                nms_threshold=0.3,
                top_k=5000,
            )
        except Exception as exc:
            self._load_error = f"YuNet unavailable: {exc}"

    def _load_cascade(self, cascade_path: Path):
        if not cascade_path.exists():
            return None
        load_path = self._opencv_safe_path(cascade_path)
        cascade = self._cv2.CascadeClassifier(str(load_path))
        if cascade.empty():
            cached_path = self._cache_model_for_opencv(cascade_path)
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
            return self._cache_model_for_opencv(path) or path

    def _cache_model_for_opencv(self, model_path: Path) -> Path | None:
        candidates = [
            Path(r"C:\ProgramData\HealthTrayReminder"),
            Path(r"C:\Windows\Temp\HealthTrayReminder"),
        ]
        for folder in candidates:
            try:
                folder.mkdir(parents=True, exist_ok=True)
                target = folder / model_path.name
                if not target.exists() or target.stat().st_size != model_path.stat().st_size:
                    copyfile(model_path, target)
                if target.exists() and target.stat().st_size > 0:
                    return target
            except Exception:
                continue
        return None

    def check(self) -> CameraResult:
        if self._cv2 is None or (self._yunet is None and not self._cascades and self._hog is None):
            return CameraResult(False, None, f"OpenCV unavailable: {self._load_error or 'not installed'}")

        cap = None
        try:
            cap = self._cv2.VideoCapture(self.camera_index, self._cv2.CAP_DSHOW)
            if not cap or not cap.isOpened():
                return CameraResult(False, None, "Camera unavailable")
            self._prepare_capture(cap)

            frames_checked = 0
            for _ in range(self.sample_frames):
                ok, frame = cap.read()
                if not ok or frame is None:
                    continue
                frames_checked += 1
                detection_count, detector_name = self._detect_person_count(frame)
                if detection_count > 0:
                    return CameraResult(
                        True,
                        True,
                        f"{detector_name} detections={detection_count} frames={frames_checked}",
                    )

            if frames_checked == 0:
                return CameraResult(False, None, "Camera frame unavailable")
            return CameraResult(True, False, f"detections=0 frames={frames_checked}")
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

    def _resize_frame(self, frame):
        height, width = frame.shape[:2]
        if width <= self.max_width:
            return frame
        scale = self.max_width / width
        return self._cv2.resize(frame, (self.max_width, int(height * scale)))

    def _detect_person_count(self, frame) -> tuple[int, str]:
        if self._yunet is not None:
            count = self._detect_with_yunet(frame)
            if count > 0:
                return count, "yunet"
        haar_count = self._detect_with_haar(frame)
        if haar_count > 0:
            return haar_count, "haar"
        if self._hog is not None:
            hog_count = self._detect_with_hog(frame)
            if hog_count > 0:
                return hog_count, "hog_person"
        return 0, "none"

    def _detect_with_yunet(self, frame) -> int:
        resized = self._resize_frame(frame)
        height, width = resized.shape[:2]
        self._yunet.setInputSize((width, height))
        _retval, faces = self._yunet.detect(resized)
        return 0 if faces is None else len(faces)

    def _detect_with_hog(self, frame) -> int:
        frame = self._resize_frame(frame)
        frame = self._cv2.resize(frame, (frame.shape[1] // 2 * 2, frame.shape[0] // 2 * 2))
        bodies, _weights = self._hog.detectMultiScale(
            frame,
            winStride=(8, 8),
            padding=(8, 8),
            scale=1.05,
            finalThreshold=2,
        )
        return len(bodies)

    def _detect_with_haar(self, frame) -> int:
        frame = self._resize_frame(frame)
        gray = self._cv2.cvtColor(frame, self._cv2.COLOR_BGR2GRAY)
        gray = self._cv2.equalizeHist(gray)
        flipped = self._cv2.flip(gray, 1)
        best_count = 0
        for name, cascade in self._cascades:
            min_size = (44, 44) if "face" in name else (64, 64)
            for image in (gray, flipped):
                faces = cascade.detectMultiScale(
                    image,
                    scaleFactor=1.08,
                    minNeighbors=4,
                    minSize=min_size,
                )
                best_count = max(best_count, len(faces))
                if best_count > 0:
                    return best_count
        return best_count
