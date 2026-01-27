import argparse
import cv2
from pyzbar import pyzbar
import pytesseract


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True, help="Path to an image file")
    args = parser.parse_args()

    image = cv2.imread(args.image)
    if image is None:
        raise SystemExit("Could not read image")

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    barcodes = pyzbar.decode(gray)
    for barcode in barcodes:
        print(f"Barcode: {barcode.data.decode('utf-8', errors='ignore')} | type={barcode.type}")
        rect = barcode.rect
        roi = image[rect.top:rect.top + rect.height, rect.left:rect.left + rect.width]
        roi_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(roi_gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        text = pytesseract.image_to_string(thresh)
        print(f"OCR: {' '.join(text.split())}")


if __name__ == "__main__":
    main()
