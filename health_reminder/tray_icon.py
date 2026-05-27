from PIL import Image, ImageDraw


def create_icon_image():
    size = 64
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((6, 6, size - 6, size - 6), fill=(30, 136, 229, 255))
    draw.ellipse((18, 14, 34, 30), fill=(120, 200, 255, 230))
    return image
