from __future__ import annotations

from PIL import Image, ImageDraw


def create_tray_icon(size: int = 64) -> Image.Image:
    """创建系统托盘图标。"""
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    margin = int(size * 0.08)
    body = [margin, margin, size - margin, size - margin]
    draw.pieslice(body, start=32, end=328, fill=(255, 205, 38, 255))
    eye_r = max(2, size // 13)
    eye_x = int(size * 0.55)
    eye_y = int(size * 0.28)
    draw.ellipse([eye_x - eye_r, eye_y - eye_r, eye_x + eye_r, eye_y + eye_r], fill=(40, 40, 45, 255))
    draw.arc(body, start=32, end=328, fill=(235, 170, 10, 255), width=max(2, size // 18))
    return image
