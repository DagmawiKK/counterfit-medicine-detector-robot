#!/usr/bin/env python3
from pathlib import Path
import shutil

BASE_DIR = Path(__file__).resolve().parents[1] / "models"
BASE_MODEL = BASE_DIR / "medicine_bottle"

VARIANTS = [
    ("medicine_bottle_v1", "label_variant_1.png"),
    ("medicine_bottle_v2", "label_variant_2.png"),
    ("medicine_bottle_v3", "label_variant_3.png"),
    ("medicine_bottle_v4", "label_variant_4.png"),
    ("medicine_bottle_v5", "label_variant_5.png"),
]


def update_model_config(path: Path, model_name: str):
    config = path / "model.config"
    text = config.read_text()
    text = text.replace("<name>medicine_bottle</name>", f"<name>{model_name}</name>")
    config.write_text(text)


def update_model_sdf(path: Path, label_file: str):
    sdf = path / "model.sdf"
    text = sdf.read_text()
    text = text.replace("label.png", label_file)
    sdf.write_text(text)


def main():
    for model_name, label_file in VARIANTS:
        dst = BASE_DIR / model_name
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(BASE_MODEL, dst)
        update_model_config(dst, model_name)
        update_model_sdf(dst, label_file)
        print(f"Created {dst} with {label_file}")


if __name__ == "__main__":
    main()
