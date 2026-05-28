from datetime import datetime

_CHECK_INTERVAL_SECONDS = 60
_ABSENT_TRIGGER_COUNT = 3
# 背景差分：前景像素占比低于此值视为无人
_MOTION_THRESHOLD = 0.008


class CameraPresenceDetector:
    """Dual-detector presence detection: HOG person + background subtraction.

    If *either* detector thinks someone is present, we count it as "person
    found".  Only when *both* agree there is nobody do we increment the
    absence counter.  This dramatically reduces false negatives.
    """

    def __init__(self, log):
        self.log = log
        self.last_checked_at = None
        self.last_result = "等待首次检测"
        self._hog = None
        self._bg_sub = None
        self._first_frame = True
        self.absent_count = 0
        self._popup_shown = False

    # ---- public helpers ------------------------------------------------

    @property
    def away_trigger_ready(self):
        return self.absent_count >= _ABSENT_TRIGGER_COUNT and not self._popup_shown

    def mark_popup_shown(self):
        self._popup_shown = True

    def reset_away_tracking(self):
        self.absent_count = 0
        self._popup_shown = False

    # ---- detection logic -----------------------------------------------

    def due(self):
        if self.last_checked_at is None:
            return True
        return (datetime.now() - self.last_checked_at).total_seconds() >= _CHECK_INTERVAL_SECONDS

    def detect_if_due(self):
        if not self.due():
            return None

        self.last_checked_at = datetime.now()
        result = self._detect()

        if result is True:
            self.last_result = "有人"
            if self.absent_count > 0:
                self.log.write(f"检测到人，连续缺席 {self.absent_count} 次已重置")
            self.reset_away_tracking()
        elif result is False:
            self.absent_count += 1
            self.last_result = f"未检测到人（{self.absent_count}/{_ABSENT_TRIGGER_COUNT}）"
            self.log.write(f"未检测到人，连续第 {self.absent_count} 次")

        return result

    # ---- internal detectors --------------------------------------------

    def _get_hog(self):
        if self._hog is None:
            import cv2
            hog = cv2.HOGDescriptor()
            hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
            self._hog = hog
        return self._hog

    def _get_bg_sub(self):
        if self._bg_sub is None:
            import cv2
            self._bg_sub = cv2.createBackgroundSubtractorMOG2(
                history=500, varThreshold=50, detectShadows=False)
        return self._bg_sub

    def _detect_hog(self, small):
        """Return True if HOG detects a person."""
        try:
            hog = self._get_hog()
            rects, _ = hog.detectMultiScale(
                small, winStride=(8, 8), padding=(4, 4), scale=1.05)
            return len(rects) > 0
        except Exception:
            return False

    def _detect_motion(self, frame):
        """Return True if significant foreground motion is detected."""
        try:
            import cv2
            bg_sub = self._get_bg_sub()
            mask = bg_sub.apply(frame)
            # Ignore first few frames while model calibrates
            if self._first_frame:
                self._first_frame = False
                return False
            ratio = cv2.countNonZero(mask) / (mask.shape[0] * mask.shape[1])
            return ratio >= _MOTION_THRESHOLD
        except Exception:
            return False

    def _detect(self):
        """Combined detection: HOG person OR motion = person present."""
        try:
            import cv2
        except Exception:
            self.last_result = "缺少 opencv-python"
            self.log.write("检测跳过：缺少 opencv-python")
            return None

        camera = None
        try:
            camera = cv2.VideoCapture(0, cv2.CAP_DSHOW)
            if not camera.isOpened():
                self.last_result = "摄像头不可用"
                self.log.write("检测跳过：摄像头不可用")
                return None

            ok, frame = camera.read()
            if not ok or frame is None:
                self.last_result = "未读取到画面"
                self.log.write("检测跳过：未读取到画面")
                return None

            small = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)

            hog_found = self._detect_hog(small)
            motion_found = self._detect_motion(small)

            if hog_found:
                self.last_result = "有人（人体检测）"
                return True
            if motion_found:
                self.last_result = "有人（画面变化）"
                return True
            return False
        except Exception as exc:
            self.last_result = "检测失败"
            self.log.write(f"检测失败：{exc}")
            self._hog = None
            self._bg_sub = None
            return None
        finally:
            if camera is not None:
                camera.release()
