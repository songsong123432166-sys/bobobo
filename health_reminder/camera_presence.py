from datetime import datetime, timedelta


class CameraPresenceDetector:
    def __init__(self, log, enabled=False, interval_minutes=30):
        self.log = log
        self.enabled = bool(enabled)
        self.interval_minutes = int(interval_minutes)
        self.last_checked_at = None
        self.last_result = "未启用"

    def update_settings(self, enabled, interval_minutes):
        self.enabled = bool(enabled)
        self.interval_minutes = max(5, int(interval_minutes))
        if not self.enabled:
            self.last_result = "未启用"

    def due(self):
        if not self.enabled:
            return False
        if self.last_checked_at is None:
            return True
        return datetime.now() - self.last_checked_at >= timedelta(
            minutes=self.interval_minutes
        )

    def detect_if_due(self):
        if not self.due():
            return None

        self.last_checked_at = datetime.now()
        result = self.detect_presence()
        self.last_result = "有人" if result is True else "未检测到人"
        self.log.write(f"摄像头检测完成：{self.last_result}")
        return result

    def detect_presence(self):
        try:
            import cv2
        except Exception:
            self.last_result = "缺少 opencv-python"
            self.log.write("摄像头检测跳过：缺少 opencv-python")
            return None

        camera = None
        try:
            camera = cv2.VideoCapture(0, cv2.CAP_DSHOW)
            if not camera.isOpened():
                self.last_result = "摄像头不可用"
                self.log.write("摄像头检测跳过：摄像头不可用")
                return None

            ok, frame = camera.read()
            if not ok or frame is None:
                self.last_result = "未读取到画面"
                self.log.write("摄像头检测跳过：未读取到画面")
                return None

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            face_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            face_detector = cv2.CascadeClassifier(face_path)
            faces = face_detector.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=(60, 60),
            )
            return len(faces) > 0
        except Exception as exc:
            self.last_result = "检测失败"
            self.log.write(f"摄像头检测失败：{exc}")
            return None
        finally:
            if camera is not None:
                camera.release()
