#!/usr/bin/env python3
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import random

def main():
    base = Path(__file__).resolve().parents[1] / "models" / "medicine_bottle" / "materials" / "textures" / "label.png"
    out_dir = base.parent

    base_img = Image.open(base).convert("RGBA")
    width, height = base_img.size

    variants = [
        ("label_variant_1.png", (30, 144, 255, 80), "LOT A1"),  # dodger blue
        ("label_variant_2.png", (255, 99, 71, 80), "LOT B2"),   # tomato
        ("label_variant_3.png", (60, 179, 113, 80), "LOT C3"),  # medium sea green
        ("label_variant_4.png", (218, 165, 32, 80), "LOT D4"),  # goldenrod
        ("label_variant_5.png", (186, 85, 211, 80), "LOT E5"),  # medium orchid
    ]

    for filename, overlay_rgba, lot_text in variants:
        img = base_img.copy()
        overlay = Image.new("RGBA", img.size, overlay_rgba)
        img = Image.alpha_composite(img, overlay)

        draw = ImageDraw.Draw(img)
        # Simple text at top center
        text = f"{lot_text}"
        try:
            font = ImageFont.truetype("DejaVuSans-Bold.ttf", 18)
        except Exception:
            font = ImageFont.load_default()
        text_w, text_h = draw.textsize(text, font=font)
        draw.text(((width - text_w) // 2, 10), text, fill=(0, 0, 0, 255), font=font)

        out_path = out_dir / filename
        img.convert("RGB").save(out_path)
        print(f"Wrote {out_path}")

if __name__ == "__main__":
    main()
