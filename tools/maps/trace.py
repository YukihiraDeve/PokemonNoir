#!/usr/bin/env python3
"""Décalque une carte de référence (capture de Pokémon Noir & Blanc) en grille de cases.

Usage : python3 tools/maps/trace.py <image> <offset_x> <offset_y> <sortie.txt> [aperçu.png]

Chaque case de 16 px reçoit une lettre selon sa couleur moyenne :
  T forêt  H herbes hautes  . herbe  S sable/chemin  F fleurs roses  W eau  C falaise
La grille texte se retouche ensuite à la main (panneaux, clôtures, maisons…).
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw

TILE = 16
PROTOTYPES = {
    "T": [(28, 110, 85), (20, 95, 80), (30, 125, 100)],
    "H": [(60, 135, 60), (75, 150, 70), (50, 120, 55)],
    ".": [(140, 215, 130), (120, 200, 120), (160, 225, 150)],
    "S": [(225, 205, 150), (215, 195, 145), (205, 200, 160)],
    "F": [(205, 165, 190), (215, 185, 200), (195, 150, 185)],
    "W": [(40, 100, 210), (30, 80, 180), (70, 140, 230)],
    "C": [(150, 90, 50), (175, 115, 70)],
}
PREVIEW = {"T": (20, 90, 70), "H": (60, 140, 50), ".": (150, 220, 140), "S": (230, 210, 150),
           "F": (220, 160, 200), "W": (40, 100, 210), "C": (140, 80, 40)}


def classify(color):
    best, dist = ".", 1e9
    for letter, protos in PROTOTYPES.items():
        for p in protos:
            d = sum((a - b) ** 2 for a, b in zip(color, p))
            if d < dist:
                best, dist = letter, d
    return best


def main() -> int:
    image, ox, oy, out = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
    im = Image.open(image).convert("RGB")
    cols = (im.width - ox) // TILE
    rows = (im.height - oy) // TILE
    lines = []
    for r in range(rows):
        line = ""
        for c in range(cols):
            box = (ox + c * TILE + 2, oy + r * TILE + 2, ox + (c + 1) * TILE - 2, oy + (r + 1) * TILE - 2)
            tile = im.crop(box).resize((1, 1), Image.BOX).getpixel((0, 0))
            line += classify(tile)
        lines.append(line)
    Path(out).write_text("\n".join(lines) + "\n")
    if len(sys.argv) > 5:
        prev = Image.new("RGB", (cols * TILE * 2, rows * TILE))
        prev.paste(im.crop((ox, oy, ox + cols * TILE, oy + rows * TILE)), (0, 0))
        d = ImageDraw.Draw(prev)
        for r, line in enumerate(lines):
            for c, ch in enumerate(line):
                x, y = cols * TILE + c * TILE, r * TILE
                d.rectangle((x, y, x + TILE - 1, y + TILE - 1), fill=PREVIEW[ch])
        prev.save(sys.argv[5])
    print(f"{cols}×{rows} cases → {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
