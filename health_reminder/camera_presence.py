import os
import shutil
import tempfile
from datetime import datetime, timedelta


_MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")
_PROTOTXT = os.path.join(_MODEL_DIR, "deploy.prototxt")
_CAFFEMODEL = os.path.join(_MODEL_DIR, "res10_300x300_ssd_iter_140000.caffemodel")
_CONFIDENCE_THRESHOLD = 0.6
_ASCII_MODEL_DIRS = (
    r"C:\HealthReminderModels",
    os.path.join(os.environ.get("PUBLIC", r"C:\Users\Public"), "HealthReminderModels"),
    os.path.join(os.environ.get("PROGRAMDATA", r"C:\ProgramData"), "HealthReminderModels"),
    os.path.join(tempfile.gettempdir(), "HealthReminderModels"),
)


def _writable_ascii_model_dir():
    for model_dir in _ASCII_MODEL_DIRS:
        try:
            model_dir.encode("ascii")
        except UnicodeEncodeError:
            continue
        try:
            os.makedirs(model_dir, exist_ok=True)
            test_path = os.path.join(model_dir, ".write-test")
            with open(test_path, "w", encoding="utf-8") as handle:
                handle.write("ok")
            os.remove(test_path)
            return model_dir
        except OSError:
            continue
    raise OSError("No writable model cache directory found")


def _ascii_model_paths():
    for model_dir in _ASCII_MODEL_DIRS:
        try:
            model_dir.encode("ascii")
        except UnicodeEncodeError:
            continue
        prototxt = os.path.join(model_dir, "deploy.prototxt")
        caffemodel = os.path.join(model_dir, "res10_300x300_ssd_iter_140000.caffemodel")
        if (
            os.path.isfile(prototxt)
            and os.path.isfile(caffemodel)
            and os.path.getsize(prototxt) == os.path.getsize(_PROTOTXT)
            and os.path.getsize(caffemodel) == os.path.getsize(_CAFFEMODEL)
        ):
            return prototxt, caffemodel

    model_dir = _writable_ascii_model_dir()
    prototxt = os.path.join(model_dir, "deploy.prototxt")
    caffemodel = os.path.join(model_dir, "res10_300x300_ssd_iter_140000.caffemodel")
    for source, target in ((_PROTOTXT, prototxt), (_CAFFEMODEL, caffemodel)):
        if not os.path.isfile(target) or os.path.getsize(target) != os.path.getsize(source):
            shutil.copy2(source, target)
    return prototxt, caffemodel


class CameraPresenceDetector:
    def __init__(self, log, enabled=False, interval_minutes=30):
        self.log = log
        self.enabled = bool(enabled)
        self.interval_minutes = int(interval_minutes)
        self.last_checked_at = None
        self.last_result = "未启用"
        self._net = None

    def update_settings(self, enabled, interval_minutes):
        self.enabled = bool(enabled)
        self.interval_minutes = max(5, int(interval_minutes))
        if not self.enabled:
            self.last_result = "未启用"

    def _get_net(self):
        if self._net is None:
            import cv2
            if not os.path.isfile(_PROTOTXT) or not os.path.isfile(_CAFFEMODEL):
                raise FileNotFoundError("DNN model files not found")
            prototxt, caffemodel = _ascii_model_paths()
            self._net = cv2.dnn.readNetFromCaffe(prototxt, caffemodel)
        return self._net

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

            h, w = frame.shape[:2]
            blob = cv2.dnn.blobFromImage(
                cv2.resize(frame, (300, 300)),
                1.0, (300, 300), (104.0, 177.0, 123.0),
            )
            net = self._get_net()
            net.setInput(blob)
            detections = net.forward()

            for i in range(detections.shape[2]):
                confidence = detections[0, 0, i, 2]
                if confidence >= _CONFIDENCE_THRESHOLD:
                    return True
            return False
        except Exception as exc:
            self.last_result = "检测失败"
            self.log.write(f"摄像头检测失败：{exc}")
            self._net = None
            return None
        finally:
            if camera is not None:
                camera.release()
