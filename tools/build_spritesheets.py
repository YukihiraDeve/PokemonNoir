#!/usr/bin/env python3
"""Prépare les planches de sprites pour Three.js.

Pokémon (GIF animés Noir & Blanc) :
    Entrée : public/assets/pokemon/gif/<variante>/<id>.gif
    Sortie : public/assets/pokemon/sprites/<variante>/<id>.png  (grille de frames, ligne par ligne)
             public/assets/pokemon/sprites/index.json           (taille des frames, colonnes, durées en ms)
    Les marges transparentes communes à toutes les frames sont rognées : le bas de la
    frame correspond donc aux pieds du Pokémon, pratique pour poser un billboard au sol.
    Les frames identiques consécutives sont fusionnées (leur durée est additionnée).

Personnages du monde (bandes verticales de Pokémon Platine) :
    Entrée : .cache/pokeplatinum/{player,npc,objects}/<nom>.png
    Sortie : public/assets/characters/overworld/<nom>.png  (4 colonnes, une ligne par direction)
             public/assets/characters/overworld/index.json
             public/assets/characters/objects/<nom>.png
"""
import json
import math
import sys
from pathlib import Path

from PIL import Image, ImageSequence

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "public/assets/pokemon/gif"
DST = ROOT / "public/assets/pokemon/sprites"
VARIANTS = ["front", "back", "front-shiny", "back-shiny"]
MAX_SHEET_WIDTH = 2048
DEFAULT_DURATION = 50

PLATINUM_RAW = ROOT / ".cache/pokeplatinum"
OVERWORLD = ROOT / "public/assets/characters/overworld"
OBJECTS = ROOT / "public/assets/characters/objects"
# Platine range les frames par direction (haut, bas, gauche, droite), 4 frames chacune :
# immobile, pas A, immobile, pas B. Les joueurs ont ensuite les mêmes 16 frames en course.
SOURCE_DIRECTIONS = ["up", "down", "left", "right"]
OUTPUT_DIRECTIONS = ["down", "left", "right", "up"]
FRAMES_PER_DIRECTION = 4


def read_frames(path: Path):
    frames = []
    with Image.open(path) as gif:
        for frame in ImageSequence.Iterator(gif):
            img = frame.convert("RGBA")
            duration = frame.info.get("duration") or DEFAULT_DURATION
            if frames and img.tobytes() == frames[-1][0].tobytes():
                frames[-1][1] += duration
            else:
                frames.append([img, duration])
    return frames


def build_sheet(path: Path, out: Path) -> dict:
    frames = read_frames(path)
    bbox = None
    for img, _ in frames:
        b = img.getchannel("A").getbbox()
        if b:
            bbox = b if bbox is None else (min(bbox[0], b[0]), min(bbox[1], b[1]),
                                           max(bbox[2], b[2]), max(bbox[3], b[3]))
    bbox = bbox or (0, 0, *frames[0][0].size)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    cols = max(1, min(len(frames), MAX_SHEET_WIDTH // w))
    rows = math.ceil(len(frames) / cols)
    sheet = Image.new("RGBA", (cols * w, rows * h))
    for i, (img, _) in enumerate(frames):
        sheet.paste(img.crop(bbox), ((i % cols) * w, (i // cols) * h))
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out, optimize=True)
    return {"w": w, "h": h, "cols": cols, "durations": [d for _, d in frames]}


def build_overworld(path: Path, out: Path) -> dict | None:
    """Remet une bande Platine en grille : lignes walk-down, walk-left, … puis run-… s'il y en a."""
    with Image.open(path) as src:
        strip = src.convert("RGBA")
    size = strip.width
    count = strip.height // size
    if count < len(SOURCE_DIRECTIONS) * FRAMES_PER_DIRECTION:
        return None  # sprites de groupe ou spéciaux, pas de cycle de marche
    frame = lambda i: strip.crop((0, i * size, size, (i + 1) * size))
    blocks = [("walk", 0)] + ([("run", 16)] if count >= 32 else [])
    rows, extra = [], list(range(16 * len(blocks), count))
    sheet = Image.new("RGBA", (FRAMES_PER_DIRECTION * size, (len(blocks) * 4 + (1 if extra else 0)) * size))
    for kind, start in blocks:
        for direction in OUTPUT_DIRECTIONS:
            first = start + SOURCE_DIRECTIONS.index(direction) * FRAMES_PER_DIRECTION
            for col in range(FRAMES_PER_DIRECTION):
                sheet.paste(frame(first + col), (col * size, len(rows) * size))
            rows.append(f"{kind}-{direction}")
    if extra:
        # Frames en plus (ex. l'infirmière qui salue) sur une dernière ligne.
        for col, i in enumerate(extra[:FRAMES_PER_DIRECTION]):
            sheet.paste(frame(i), (col * size, len(rows) * size))
        rows.append("extra")
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out, optimize=True)
    return {"w": size, "h": size, "cols": FRAMES_PER_DIRECTION, "rows": rows}


def build_characters() -> int:
    index = {}
    for path in sorted(PLATINUM_RAW.glob("player/*.png")) + sorted(PLATINUM_RAW.glob("npc/*.png")):
        meta = build_overworld(path, OVERWORLD / path.name)
        if meta:
            index[path.stem] = meta
    (OVERWORLD / "index.json").write_text(json.dumps(index, separators=(",", ":")))
    OBJECTS.mkdir(parents=True, exist_ok=True)
    for path in PLATINUM_RAW.glob("objects/*.png"):
        with Image.open(path) as im:
            im.convert("RGBA").save(OBJECTS / path.name, optimize=True)
    return len(index)


def main() -> int:
    index_path = DST / "index.json"
    previous = json.loads(index_path.read_text()) if index_path.exists() else {}
    index = {}
    for variant in VARIANTS:
        for gif in sorted((SRC / variant).glob("*.gif"), key=lambda p: int(p.stem)):
            out = DST / variant / f"{gif.stem}.png"
            meta = previous.get(gif.stem, {}).get(variant)
            # Planche déjà à jour : on réutilise ses métadonnées.
            if not (meta and out.exists() and out.stat().st_mtime >= gif.stat().st_mtime):
                meta = build_sheet(gif, out)
            index.setdefault(gif.stem, {})[variant] = meta
    index = dict(sorted(index.items(), key=lambda kv: int(kv[0])))
    index_path.write_text(json.dumps(index, separators=(",", ":")))
    print(f"{sum(len(v) for v in index.values())} planches pour {len(index)} Pokémon")
    print(f"{build_characters()} personnages du monde")
    return 0


if __name__ == "__main__":
    sys.exit(main())
