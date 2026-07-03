import json
import os

import pygame

ASSETS = "assets"
IMAGE = "locations.png"
METADATA = "locations.txt"
COLS, ROWS = 5, 5


def parse_metadata(path):
    with open(path, encoding="utf-8") as f:
        lines = [l.strip() for l in f if l.strip()]
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
    records = parse_metadata(f"{ASSETS}/{METADATA}")
    sheet = pygame.image.load(f"{ASSETS}/{IMAGE}")
    w, h = sheet.get_size()
    cell_w, cell_h = w // COLS, h // ROWS
    assert len(records) == COLS * ROWS, f"{METADATA}: expected {COLS*ROWS} records, got {len(records)}"

    out_dir = f"{ASSETS}/locations"
    os.makedirs(out_dir, exist_ok=True)

    manifest = []
    for i, record in enumerate(records):
        col, row = i % COLS, i // COLS
        rect = pygame.Rect(col * cell_w, row * cell_h, cell_w, cell_h)
        tile = sheet.subsurface(rect).copy()
        filename = f"location_{i + 1:02d}.png"
        pygame.image.save(tile, f"{out_dir}/{filename}")
        entry = {"file": filename}
        entry.update({k.lower().replace(" ", "_"): v for k, v in record.items() if k != "#"})
        manifest.append(entry)

    with open(f"{out_dir}/manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"Sliced {len(manifest)} locations into {out_dir}/")


if __name__ == "__main__":
    main()
