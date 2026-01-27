#!/usr/bin/env python3
"""Generate medicine bottle label textures.

Generates:
- label_albedo.png: high-resolution label with barcodes + OCR text
- label_roughness.png: grayscale roughness map (matte paper + glossy seal region)

Only dependency: Pillow.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


@dataclass(frozen=True)
class LabelSpec:
    width: int = 2048
    height: int = 1024
    medicine_name: str = "Amoxicillin 500mg"
    id_text: str = "AMX-62810001"
    ocr_line_1: str = "LOT: AMX23A"
    ocr_line_2: str = "EXP: 12/2026"


L_CODES = {
    "0": "0001101",
    "1": "0011001",
    "2": "0010011",
    "3": "0111101",
    "4": "0100011",
    "5": "0110001",
    "6": "0101111",
    "7": "0111011",
    "8": "0110111",
    "9": "0001011",
}

G_CODES = {
    "0": "0100111",
    "1": "0110011",
    "2": "0011011",
    "3": "0100001",
    "4": "0011101",
    "5": "0111001",
    "6": "0000101",
    "7": "0010001",
    "8": "0001001",
    "9": "0010111",
}

R_CODES = {
    "0": "1110010",
    "1": "1100110",
    "2": "1101100",
    "3": "1000010",
    "4": "1011100",
    "5": "1001110",
    "6": "1010000",
    "7": "1000100",
    "8": "1001000",
    "9": "1110100",
}

PARITY = {
    "0": "LLLLLL",
    "1": "LLGLGG",
    "2": "LLGGLG",
    "3": "LLGGGL",
    "4": "LGLLGG",
    "5": "LGGLLG",
    "6": "LGGGLL",
    "7": "LGLGLG",
    "8": "LGLGGL",
    "9": "LGGLGL",
}


def ean13_checksum(d12: str) -> str:
    assert len(d12) == 12 and d12.isdigit()
    s = 0
    for i, ch in enumerate(d12):
        n = int(ch)
        s += n * (1 if (i % 2 == 0) else 3)
    return str((10 - (s % 10)) % 10)


def build_ean13_bits(d13: str) -> str:
    # guard + left(6) + center + right(6) + guard
    first = d13[0]
    left6 = d13[1:7]
    right6 = d13[7:]
    parity = PARITY[first]

    bits = "101"  # start guard
    for d, p in zip(left6, parity):
        bits += (L_CODES[d] if p == "L" else G_CODES[d])
    bits += "01010"  # center guard
    for d in right6:
        bits += R_CODES[d]
    bits += "101"  # end guard
    return bits


def draw_ean13(draw: ImageDraw.ImageDraw, x: int, y: int, w: int, h: int, d13: str) -> None:
    # simple raster barcode
    bits = build_ean13_bits(d13)
    quiet = 10
    bar_w = (w - 2 * quiet) / len(bits)

    # background
    draw.rectangle([x, y, x + w, y + h], fill=(255, 255, 255))

    # bars
    for i, b in enumerate(bits):
        if b == "1":
            bx0 = x + quiet + int(i * bar_w)
            bx1 = x + quiet + int((i + 1) * bar_w)
            draw.rectangle([bx0, y, bx1, y + h], fill=(0, 0, 0))


def pseudo_datamatrix(img: Image.Image, x: int, y: int, size: int, payload: str) -> None:
    """Draws a DataMatrix-like symbol (visual only).

    This is *not* a standards-compliant GS1 DataMatrix encoder, but it provides a
    dense 2D code region for curvature and glare testing.
    """
    modules = 32
    m = size // modules
    draw = ImageDraw.Draw(img)
    draw.rectangle([x, y, x + size, y + size], fill=(255, 255, 255))

    seed = 0
    for ch in payload.encode("utf-8"):
        seed = (seed * 131 + ch) & 0xFFFFFFFF

    def bit(i: int) -> int:
        nonlocal seed
        seed = (1103515245 * seed + 12345) & 0x7FFFFFFF
        return (seed >> (i % 16)) & 1

    # finder patterns (solid L)
    for i in range(modules):
        # left border
        draw.rectangle([x, y + i * m, x + m, y + (i + 1) * m], fill=(0, 0, 0))
        # bottom border
        draw.rectangle([x + i * m, y + (modules - 1) * m, x + (i + 1) * m, y + modules * m], fill=(0, 0, 0))
        # alternating top/right
        if i % 2 == 0:
            draw.rectangle([x + i * m, y, x + (i + 1) * m, y + m], fill=(0, 0, 0))
            draw.rectangle([x + (modules - 1) * m, y + i * m, x + modules * m, y + (i + 1) * m], fill=(0, 0, 0))

    # payload bits
    for r in range(1, modules - 1):
        for c in range(1, modules - 1):
            if bit(r * 37 + c) == 1:
                draw.rectangle([x + c * m, y + r * m, x + (c + 1) * m, y + (r + 1) * m], fill=(0, 0, 0))


def try_draw_real_datamatrix(img: Image.Image, x: int, y: int, size: int, payload: str) -> bool:
    """Try to draw a real DataMatrix using pylibdmtx if available.

    Returns True if succeeded, else False (caller can fall back).
    """
    try:
        from pylibdmtx.pylibdmtx import encode  # type: ignore
    except Exception:
        return False


def try_draw_qrcode(img: Image.Image, x: int, y: int, size: int, payload: str) -> bool:
    try:
        import qrcode  # type: ignore
    except Exception:
        return False

    try:
        qr = qrcode.QRCode(
            version=2,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=2,
        )
        qr.add_data(payload)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
        qr_img = qr_img.resize((size, size), resample=Image.NEAREST)
        img.paste(qr_img, (x, y))
        return True
    except Exception:
        return False

    try:
        # pylibdmtx returns PNG bytes by default
        dm = encode(payload.encode("utf-8"), size="SquareAuto")
    except Exception:
        return False

    try:
        dm_img = Image.open(
            __import__("io").BytesIO(dm.png)  # avoid global import
        ).convert("RGB")
        dm_img = dm_img.resize((size, size), resample=Image.NEAREST)
        img.paste(dm_img, (x, y))
        return True
    except Exception:
        return False


def load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    ):
        p = Path(path)
        if p.exists():
            return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()


def main() -> None:
    spec = LabelSpec()
    out_dir = Path(__file__).resolve().parents[1] / "materials" / "textures"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Build EAN-13 from the given ID deterministically:
    digits = "".join(ch for ch in spec.id_text if ch.isdigit())
    # Make 12 digits (pad with zeros) then compute check digit
    d12 = (digits + "0" * 12)[:12]
    d13 = d12 + ean13_checksum(d12)

    albedo = Image.new("RGB", (spec.width, spec.height), (245, 245, 245))
    draw = ImageDraw.Draw(albedo)

    # Layout blocks
    margin = 80
    dm_size = 420
    barcode_w, barcode_h = 900, 220

    # Header band
    draw.rectangle([0, 0, spec.width, 120], fill=(20, 80, 50)) # Deep medicinal green
    font_title = load_font(64)
    font_small = load_font(36)
    font_mono = load_font(32)
    font_tiny = load_font(24)

    draw.text((margin, 20), "NanoTech Pharma", fill=(200, 255, 200), font=font_tiny)
    draw.text((margin, 40), spec.medicine_name, fill=(255, 255, 255), font=font_title)

    # Details block
    draw.text((margin, 130), "Dosage: 500mg | Qty: 100 Tablets", fill=(50, 50, 50), font=font_small)
    draw.text((margin, 580), "Direction: Take one tablet daily with water.", fill=(100, 100, 100), font=font_small)
    draw.text((margin, 620), "Warning: Keep out of reach of children.", fill=(200, 50, 50), font=font_small)

    # DataMatrix block
    dm_x, dm_y = margin, 170
    used_real_dm = try_draw_real_datamatrix(albedo, dm_x, dm_y, dm_size, spec.id_text)
    if not used_real_dm:
        pseudo_datamatrix(albedo, dm_x, dm_y, dm_size, spec.id_text)
    draw.text(
        (dm_x, dm_y + dm_size + 18),
        f"GS1 DataMatrix (ID): {spec.id_text}" + ("" if used_real_dm else " [visual demo]"),
        fill=(10, 10, 10),
        font=font_small,
    )

    # EAN-13 block
    bc_x = dm_x + dm_size + 120
    bc_y = dm_y + 40
    draw.text((bc_x, dm_y), "EAN-13:", fill=(10, 10, 10), font=font_small)
    draw_ean13(draw, bc_x, bc_y, barcode_w, barcode_h, d13)
    draw.text((bc_x, bc_y + barcode_h + 12), d13, fill=(10, 10, 10), font=font_mono)

    # OCR text block (large contrast for Tesseract)
    ocr_x = margin
    ocr_y = 720
    draw.rectangle([0, ocr_y - 20, spec.width, spec.height], fill=(255, 255, 255))
    draw.text((ocr_x, ocr_y), spec.ocr_line_1, fill=(0, 0, 0), font=load_font(52))
    draw.text((ocr_x, ocr_y + 70), spec.ocr_line_2, fill=(0, 0, 0), font=load_font(52))

    # Holographic seal (visual hint on the label):
    seal_center = (spec.width - 220, 360)
    for i, col in enumerate([(120, 210, 255), (255, 120, 220), (140, 255, 170), (255, 230, 120)]):
        r = 110 - i * 12
        draw.ellipse(
            [seal_center[0] - r, seal_center[1] - r, seal_center[0] + r, seal_center[1] + r],
            outline=col,
            width=10,
        )
    draw.text((seal_center[0] - 90, seal_center[1] - 18), "SEAL", fill=(30, 30, 30), font=load_font(44))

    albedo_path = out_dir / "label_albedo.png"
    albedo.save(albedo_path)

    # Top label for overhead camera (flat, high-contrast)
    top_size = 512
    top_label = Image.new("RGB", (top_size, top_size), (255, 255, 255))
    tdraw = ImageDraw.Draw(top_label)

    top_margin = 20
    top_qr_size = 220
    top_bc_w, top_bc_h = 420, 120

    used_qr = try_draw_qrcode(top_label, top_margin, top_margin, top_qr_size, spec.id_text)
    if not used_qr:
        used_real_dm_top = try_draw_real_datamatrix(top_label, top_margin, top_margin, top_qr_size, spec.id_text)
        if not used_real_dm_top:
            pseudo_datamatrix(top_label, top_margin, top_margin, top_qr_size, spec.id_text)

    top_bc_x = top_margin
    top_bc_y = top_margin + top_qr_size + 20
    draw_ean13(tdraw, top_bc_x, top_bc_y, top_bc_w, top_bc_h, d13)

    top_text_y = top_bc_y + top_bc_h + 10
    tdraw.text((top_margin, top_text_y), spec.medicine_name, fill=(0, 0, 0), font=load_font(32))
    tdraw.text((top_margin, top_text_y + 40), spec.ocr_line_1, fill=(0, 0, 0), font=load_font(28))
    tdraw.text((top_margin, top_text_y + 76), spec.ocr_line_2, fill=(0, 0, 0), font=load_font(28))

    top_albedo_path = out_dir / "top_label_albedo.png"
    top_label.save(top_albedo_path)

    # Roughness map: white=rough, black=shiny.
    rough = Image.new("L", (spec.width, spec.height), 220)  # mostly matte
    rdraw = ImageDraw.Draw(rough)
    # Make the seal area glossy
    rdraw.ellipse(
        [seal_center[0] - 130, seal_center[1] - 130, seal_center[0] + 130, seal_center[1] + 130],
        fill=60,
    )
    # Slightly glossy header band
    rdraw.rectangle([0, 0, spec.width, 120], fill=140)

    rough_path = out_dir / "label_roughness.png"
    rough.save(rough_path)

    top_rough = Image.new("L", (top_size, top_size), 220)
    top_rough_path = out_dir / "top_label_roughness.png"
    top_rough.save(top_rough_path)

    print(f"Wrote: {albedo_path}")
    print(f"Wrote: {rough_path}")
    print(f"Wrote: {top_albedo_path}")
    print(f"Wrote: {top_rough_path}")
    print(f"EAN-13 used: {d13}")
    if not used_real_dm:
        print("Note: pylibdmtx not found; DataMatrix is a visual demo. Install 'python3-pylibdmtx' or 'pip install pylibdmtx' for a real DataMatrix.")
    if not used_qr:
        print("Note: qrcode not found; top label uses DataMatrix or demo instead of QR. Install 'qrcode[pil]'.")


if __name__ == "__main__":
    main()
