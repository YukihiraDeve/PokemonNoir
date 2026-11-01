#!/usr/bin/env python3
"""Copie dans le projet les pièces du Medieval Village MegaKit (Quaternius, CC0) utilisées
pour les maisons de Renouet, depuis la bibliothèque 3DLib.

Source : 3DLib/assets/models/lowpoly/quaternius/medieval-village-megakit/glTF
Sortie : public/assets/environment/quaternius_medieval-village-megakit/glTF
  - les modèles (.gltf + .bin) de MODELS ;
  - leurs textures réduites à 512 px (le rendu du jeu n'en demande pas plus) ;
  - trois variantes : tuiles rondes bleues (maisons de Renouet), bois clair (bardage) et briques
    sombres (immeubles d'Arabelle).

Usage : python3 tools/import_village_kit.py [chemin/vers/3DLib]
"""
import colorsys
import json
import shutil
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
LIB = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "3DLib"
SRC = LIB / "assets/models/lowpoly/quaternius/medieval-village-megakit/glTF"
OUT = ROOT / "public/assets/environment/quaternius_medieval-village-megakit/glTF"
SIZE = 512

MODELS = [
    "Roof_RoundTiles_4x6", "Roof_RoundTiles_4x8", "Roof_RoundTiles_6x10", "Roof_Dormer_RoundTile",
    "Window_Wide_Flat1", "Window_Thin_Flat1", "Door_1_Flat", "DoorFrame_Flat_WoodDark", "Corner_Exterior_Brick",
    "Prop_Chimney",
    # Pour leurs matériaux seulement (briques rouges, pierres, crépi) :
    "Floor_RedBrick", "Floor_UnevenBrick", "Wall_Plaster_Straight",
]


def blue_tiles(img: Image.Image) -> Image.Image:
    """Tuiles orange → bleu de Renouet ; la mousse verte et les ombres restent."""
    out = img.convert("RGB").copy()
    px = out.load()
    for y in range(out.height):
        for x in range(out.width):
            r, g, b = (c / 255 for c in px[x, y])
            h, s, v = colorsys.rgb_to_hsv(r, g, b)
            if h < 0.14 or h > 0.95:  # tons orange et rouges
                r, g, b = colorsys.hsv_to_rgb(0.6, min(1.0, s * 1.05), min(1.0, v * 1.05))
            px[x, y] = tuple(round(c * 255) for c in (r, g, b))
    return out


def dark_brick(img: Image.Image) -> Image.Image:
    """Briques brun-rouge sombre des immeubles d'Arabelle."""
    out = img.convert("RGB").copy()
    px = out.load()
    for y in range(out.height):
        for x in range(out.width):
            r, g, b = (c / 255 for c in px[x, y])
            h, s, v = colorsys.rgb_to_hsv(r, g, b)
            px[x, y] = tuple(round(c * 255) for c in colorsys.hsv_to_rgb(max(0.0, h - 0.025), min(1.0, s * 1.05), v * 0.6))
    return out


def light_wood(img: Image.Image) -> Image.Image:
    """Bois plus clair et moins saturé, comme le bardage beige des maisons du jeu."""
    out = img.convert("RGB").copy()
    px = out.load()
    for y in range(out.height):
        for x in range(out.width):
            r, g, b = (c / 255 for c in px[x, y])
            h, s, v = colorsys.rgb_to_hsv(r, g, b)
            px[x, y] = tuple(round(c * 255) for c in colorsys.hsv_to_rgb(h, s * 0.72, min(1.0, v * 1.3)))
    return out


def main() -> int:
    if not SRC.exists():
        print(f"Kit introuvable : {SRC}")
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    textures = set()
    for name in MODELS:
        gltf = json.loads((SRC / f"{name}.gltf").read_text())
        for buffer in gltf["buffers"]:
            shutil.copy2(SRC / buffer["uri"], OUT / buffer["uri"])
        textures.update(image["uri"] for image in gltf.get("images", []))
        shutil.copy2(SRC / f"{name}.gltf", OUT / f"{name}.gltf")
    for uri in sorted(textures):
        img = Image.open(SRC / uri)
        img = img.resize((SIZE, SIZE), Image.LANCZOS) if img.width > SIZE else img
        img.save(OUT / uri, optimize=True)
    blue_tiles(Image.open(OUT / "T_RoundTiles_BaseColor.png")).save(OUT / "T_RoundTiles_BaseColor_Blue.png", optimize=True)
    light_wood(Image.open(OUT / "T_WoodTrim_BaseColor.png")).save(OUT / "T_WoodTrim_BaseColor_Light.png", optimize=True)
    dark_brick(Image.open(OUT / "T_RedBrick_BaseColor.png")).save(OUT / "T_RedBrick_BaseColor_Dark.png", optimize=True)
    print(f"{len(MODELS)} modèles et {len(textures) + 3} textures dans {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
