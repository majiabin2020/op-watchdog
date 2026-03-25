# assets/icon.py
from PIL import Image, ImageDraw


def create_icon(size: int = 64) -> Image.Image:
    """Create a simple crayfish-style icon: dark background, green circle."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Dark background circle
    draw.ellipse([2, 2, size - 2, size - 2], fill=(13, 17, 23, 255))
    # Green dot (online indicator style)
    cx, cy = size // 2, size // 2
    r = size // 4
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(63, 185, 80, 255))
    return img
