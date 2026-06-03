# -*- coding: utf-8 -*-
"""摄像头人体检测器，YuNet + Haar + HOG 三级协同检测。"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from shutil import copyfile

from ..core.paths import resource_path


@dataclass
class CameraResult:
    """检测结果：是否可用、是否有人、详细信息。"""
    available: bool
    person_present: bool | None
    message: str


class CameraPresenceDetector:
    """摄像头人体检测器。

    检测优先级（准确率从高到低）：
    1. YuNet 深度学习人脸检测 — 最准，误判率最低
    2. Haar 级联分类器 — 正脸/侧面/上半身/全身，速度快
    3. HOG 人体轮廓检测 — 兜底，仅在前两者都失败时使用
    """

    def __init__(self, camera_index: int = 0, sample_frames: int = 5,
                 max_width: int = 800) -> None:
        self.camera_index = camera_index
        self.sample_frames = max(1, sample_frames)
        self.max_width = max(160, max_width)
        self._cv2 = None
        self._yunet = None
        self._hog = None
        self._cascades: list[tuple[str, object]] = []
        self._load_error: str | None = None
        self._load_cv2()

    # ── 初始化 ──

    def _load_cv2(self) -> None:
        """加载 OpenCV 及所有检测模型。"""
        try:
            import cv2
            self._cv2 = cv2
            self._load_yunet()
            self._load_hog()
            self._load_haar_cascades()
        except Exception as exc:
            self._load_error = str(exc)

    def _load_yunet(self) -> None:
        """加载 YuNet 深度学习人脸模型（准确率最高）。"""
        if not hasattr(self._cv2, "FaceDetectorYN"):
            return
        model_path = resource_path("models/face_detection_yunet_2023mar.onnx")
        if not model_path.exists():
            return
        safe_path = self._opencv_safe_path(model_path)
        try:
            self._yunet = self._cv2.FaceDetectorYN.create(
                str(safe_path), "",
                (self.max_width, 480),
                score_threshold=0.6,   # 高阈值，减少误判
                nms_threshold=0.3,
                top_k=3000,
            )
        except Exception as exc:
            self._load_error = f"YuNet unavailable: {exc}"

    def _load_hog(self) -> None:
        """加载 HOG 人体轮廓检测器（仅作兜底）。"""
        try:
            if not hasattr(self._cv2, "HOGDescriptor"):
                return
            hog = self._cv2.HOGDescriptor()
            hog.setSVMDetector(self._cv2.HOGDescriptor_getDefaultPeopleDetector())
            self._hog = hog
        except Exception:
            self._hog = None

    def _load_haar_cascades(self) -> None:
        """加载 Haar 级联分类器（正脸/侧面/上半身/全身）。"""
        cascade_names = [
            "haarcascade_frontalface_default.xml",
            "haarcascade_profileface.xml",
            "haarcascade_upperbody.xml",
            "haarcascade_fullbody.xml",
        ]
        for name in cascade_names:
            cascade_path = Path(self._cv2.data.haarcascades) / name
            cascade = self._load_single_cascade(cascade_path)
            if cascade is not None:
                self._cascades.append((name, cascade))
        if not self._cascades:
            self._load_error = (
                f"face cascades failed to load: "
                f"{Path(self._cv2.data.haarcascades)}"
            )

    def _load_single_cascade(self, cascade_path: Path):
        """加载单个级联文件，处理中文路径缓存。"""
        if not cascade_path.exists():
            return None
        load_path = self._opencv_safe_path(cascade_path)
        cascade = self._cv2.CascadeClassifier(str(load_path))
        if cascade.empty():
            cached = self._cache_model_for_opencv(cascade_path)
            if cached is not None:
                cascade = self._cv2.CascadeClassifier(str(cached))
        return None if cascade.empty() else cascade

    def _opencv_safe_path(self, path: Path) -> Path:
        """确保路径不含中文（OpenCV 不支持）。"""
        try:
            str(path).encode("ascii")
            return path
        except UnicodeEncodeError:
            return self._cache_model_for_opencv(path) or path

    def _cache_model_for_opencv(self, model_path: Path) -> Path | None:
        """将模型文件复制到纯 ASCII 路径以兼容 OpenCV。"""
        candidates = [
            Path(r"C:\ProgramData\HealthTrayReminder"),
            Path(r"C:\Windows\Temp\HealthTrayReminder"),
        ]
        for folder in candidates:
            try:
                folder.mkdir(parents=True, exist_ok=True)
                target = folder / model_path.name
                need_copy = (
                    not target.exists()
                    or target.stat().st_size != model_path.stat().st_size
                )
                if need_copy:
                    copyfile(model_path, target)
                if target.exists() and target.stat().st_size > 0:
                    return target
            except Exception:
                continue
        return None

    # ── 检测入口 ──

    def check(self) -> CameraResult:
        """执行一次摄像头检测，返回是否有人。"""
        no_detector = (
            self._cv2 is None
            or (self._yunet is None and not self._cascades and self._hog is None)
        )
        if no_detector:
            return CameraResult(
                False, None,
                f"OpenCV unavailable: {self._load_error or 'not installed'}",
            )

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
                count, name = self._detect_person(frame)
                if count > 0:
                    return CameraResult(
                        True, True,
                        f"{name} detections={count} frames={frames_checked}",
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
            except (OSError, RuntimeError):  # 释放摄像头失败时静默
                pass

    def _prepare_capture(self, cap) -> None:
        """设置摄像头分辨率。"""
        try:
            cap.set(self._cv2.CAP_PROP_FRAME_WIDTH, self.max_width)
            cap.set(self._cv2.CAP_PROP_FRAME_HEIGHT, 480)
        except (OSError, RuntimeError):  # 设置参数失败时静默
            pass

    def _resize_frame(self, frame):
        """缩放帧到最大宽度，保持比例。"""
        height, width = frame.shape[:2]
        if width <= self.max_width:
            return frame
        scale = self.max_width / width
        return self._cv2.resize(frame, (self.max_width, int(height * scale)))

    # ── 多算法协同检测 ──

    def _detect_person(self, frame) -> tuple[int, str]:
        """三级协同检测：YuNet → Haar → HOG。

        优先使用准确率最高的算法，一旦检测到即返回，
        避免低准确率算法的误判影响结果。
        """
        # 第一优先：YuNet 深度学习人脸检测（准确率最高）
        if self._yunet is not None:
            count = self._detect_yunet(frame)
            if count > 0:
                return count, "yunet"

        # 第二优先：Haar 级联（正面脸 > 侧面 > 上半身 > 全身）
        haar_count = self._detect_haar(frame)
        if haar_count > 0:
            return haar_count, "haar"

        # 第三优先：HOG 人体轮廓（误判率较高，仅作兜底）
        if self._hog is not None:
            hog_count = self._detect_hog(frame)
            if hog_count > 0:
                return hog_count, "hog_person"

        return 0, "none"

    def _detect_yunet(self, frame) -> int:
        """YuNet 深度学习人脸检测。"""
        resized = self._resize_frame(frame)
        h, w = resized.shape[:2]
        self._yunet.setInputSize((w, h))
        _ok, faces = self._yunet.detect(resized)
        return 0 if faces is None else len(faces)

    def _detect_haar(self, frame) -> int:
        """Haar 级联检测，按准确率排序尝试。"""
        resized = self._resize_frame(frame)
        gray = self._cv2.cvtColor(resized, self._cv2.COLOR_BGR2GRAY)
        self._cv2.equalizeHist(gray, gray)
        flipped = self._cv2.flip(gray, 1)

        for name, cascade in self._cascades:
            is_face = "face" in name
            min_size = (44, 44) if is_face else (64, 64)
            neighbors = 5 if is_face else 4
            for image in (gray, flipped):
                rects = cascade.detectMultiScale(
                    image,
                    scaleFactor=1.05,
                    minNeighbors=neighbors,
                    minSize=min_size,
                )
                if len(rects) > 0:
                    return len(rects)
        return 0

    def _detect_hog(self, frame) -> int:
        """HOG 人体轮廓检测（兜底方案）。"""
        resized = self._resize_frame(frame)
        # HOG 要求偶数尺寸
        h, w = resized.shape[:2]
        w = w // 2 * 2
        h = h // 2 * 2
        resized = self._cv2.resize(resized, (w, h))
        # OpenCV 4.10+ 的 finalThreshold 必须用位置参数
        bodies, _weights = self._hog.detectMultiScale(
            resized, (8, 8), (8, 8), 1.05, 2,
        )
        return len(bodies)