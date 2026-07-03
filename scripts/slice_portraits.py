import json
import subprocess
import sys

import pygame

ASSETS = "assets"
GRIDS = [("images_younger.png", "data_younger.rtf", "younger"), ("images_older.png", "data_older.rtf", "older")]
COLS, ROWS = 5, 5


def parse_metadata(rtf_path):
    text = subprocess.run(["textutil", "-convert", "txt", "-stdout", rtf_path],
                           capture_output=True, text=True, check=True).stdout
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    idx = lines.index("#")
    header = []
    i = idx
    while i < len(lines) and not lines[i].isdigit():
        header.append(lines[i])
        i += 1
    group_size = len(header)
    records = []
    while i + group_size <= len(lines):
        group = lines[i:i + group_size]
        record = dict(zip(header, group))
        records.append(record)
        i += group_size
    return records


def main():
    pygame.init()
    pygame.display.set_mode((1, 1))
    manifest = []
    for image_name, rtf_name, source in GRIDS:
        records = parse_metadata(f"{ASSETS}/{rtf_name}")
        sheet = pygame.image.load(f"{ASSETS}/{image_name}")
        w, h = sheet.get_size()
        cell_w, cell_h = w // COLS, h // ROWS
        assert len(records) == COLS * ROWS, f"{rtf_name}: expected {COLS*ROWS} records, got {len(records)}"
        for i, record in enumerate(records):
            col, row = i % COLS, i // COLS
            rect = pygame.Rect(col * cell_w, row * cell_h, cell_w, cell_h)
            tile = sheet.subsurface(rect).copy()
            filename = f"{source}_{i + 1:02d}.png"
            pygame.image.save(tile, f"{ASSETS}/portraits/{filename}")
            entry = {"file": filename, "source": source}
            entry.update({k.lower().replace(" ", "_"): v for k, v in record.items() if k != "#"})
            manifest.append(entry)
    with open(f"{ASSETS}/portraits/manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"Sliced {len(manifest)} portraits into {ASSETS}/portraits/")


if __name__ == "__main__":
    main()
