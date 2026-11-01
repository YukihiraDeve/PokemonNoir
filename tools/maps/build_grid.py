#!/usr/bin/env python3
"""Assemble Renouet et la Route 1 en une seule grille de cases, nettoyée.

Entrée  : les décalques bruts de tools/maps/trace.py (route-1.webp et nuvema.png, 16 px par case)
Sortie  : tools/maps/route-1.txt (grille finale, retouchable à la main) + aperçu PNG optionnel

Les deux captures sont à la même échelle : Renouet commence 1140 px sous le haut de la route
et 35 px à droite (le toit du labo apparaît sur les deux). La ville occupe les colonnes 2 à 28 ;
autour, c'est la forêt, puis la mer tout en bas.

Légende :
  T forêt (infranchissable)   . herbe        S sable / chemin   H herbes hautes
  F champ de fleurs roses     f fleurs roses éparses             w fleurs blanches
  W eau (infranchissable)     C falaise / digue (infranchissable)
  l herbe en contrebas (au bord de l'étang)   R escalier en bois (descend vers l'ouest)
  B emprise d'un bâtiment (infranchissable, posé à part dans Blender)

Usage : python3 tools/maps/build_grid.py <route_raw.txt> <nuvema_raw.txt> [aperçu.png]
"""
import sys
from collections import deque
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent
ROUTE_ROWS = 72      # lignes de la route avant le début de Renouet
TOWN_COL = 2         # colonne de la grille où commence l'image de Renouet
WIDTH = 38

# Emprises des bâtiments de Renouet, en cases de l'image de la ville (col, ligne, largeur, hauteur).
TOWN_BUILDINGS = [(3, 0, 10, 6), (12, 9, 5, 5), (5, 17, 5, 5), (18, 17, 5, 5)]
TOWN_WHITE_FLOWERS = [(2, 12), (3, 12), (2, 13), (3, 13), (2, 14), (24, 11), (24, 12), (24, 13),
                      (24, 22), (24, 23), (2, 26), (25, 26)]
TOWN_SEAWALL_ROW = 27  # la digue ; la mer commence juste en dessous

# Retouches à la main après le décalque automatique : (ligne, colonne de départ, cases).
ROUTE_FIXES = [
    # Haut de la carte (bord de l'image) : même rangée que la suivante, le chemin monte vers Arabelle.
    *[(r, 0, "TTTTTTTTTTTTTTTTTTTTTTTT.SSSS..TTTTTTT") for r in (0, 1)],
    # Débords des herbes hautes dans la forêt.
    (30, 33, "T"), (32, 33, "TT"), (37, 33, "TTT"), (52, 27, ".."), (61, 16, "TTT"), (61, 29, "TT"),
    (62, 19, "."), (62, 26, "."),
    # Étang en contrebas : écume = eau, falaise qui tourne à droite, petite rive basse, escalier.
    (41, 7, "CWWWWWWWCCC"),
    *[(r, 8, "W") for r in range(42, 53)],
    (42, 14, "WCCCC"),
    *[(r, 14, "WCllC") for r in (43, 44)],
    *[(r, 14, "WCllRR") for r in range(45, 49)],
    (49, 14, "CCTTTT"),
    (50, 12, "W"), (53, 0, "WWWWWWW"), (57, 5, "W"), (60, 0, "CC"), (61, 4, "T"),
]

# Haies et ombres des maisons de Renouet décalquées comme des arbres (lignes de la grille finale).
TOWN_FIXES = [(83, 13, "."), (84, 13, "."), (85, 13, "."), (86, 16, "..."), (92, 19, "."), (93, 19, "."),
              (94, 8, "...."), (94, 20, ".")]

COLORS = {"T": (20, 90, 70), "H": (60, 140, 50), ".": (150, 220, 140), "S": (230, 210, 150),
          "F": (220, 160, 200), "f": (190, 200, 160), "w": (240, 240, 230), "W": (40, 100, 210),
          "C": (140, 80, 40), "B": (90, 90, 110), "l": (110, 170, 100), "R": (200, 150, 110)}


def components(grid, letter):
    """Groupes de cases voisines (4-connexité) portant la même lettre."""
    seen = set()
    for r, row in enumerate(grid):
        for c, ch in enumerate(row):
            if ch != letter or (r, c) in seen:
                continue
            group, queue = [], deque([(r, c)])
            seen.add((r, c))
            while queue:
                y, x = queue.popleft()
                group.append((y, x))
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < len(grid) and 0 <= nx < len(grid[0]) and (ny, nx) not in seen and grid[ny][nx] == letter:
                        seen.add((ny, nx))
                        queue.append((ny, nx))
            yield group


def neighbours(grid, group):
    out = []
    for y, x in group:
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < len(grid) and 0 <= nx < len(grid[0]) and (ny, nx) not in group:
                out.append(grid[ny][nx])
    return out


def clean(grid):
    """Supprime le bruit du décalque : petits îlots absorbés par ce qui les entoure."""
    rules = [("H", 8, None), (".", 4, "T"), ("S", 4, "."), ("C", 3, "."), ("W", 3, "."), ("F", 4, "f")]
    for letter, min_size, forced in rules:
        for group in list(components(grid, letter)):
            if len(group) >= min_size:
                continue
            around = neighbours(grid, set(group))
            if forced == "T" and around and around.count("T") < len(around):
                continue  # clairière ouverte : on la garde
            replacement = forced or max(set(around), key=around.count, default=".")
            if letter == "H":
                replacement = "T" if around.count("T") >= len(around) / 2 else "."
            for y, x in group:
                grid[y][x] = replacement
    return grid


def main() -> int:
    route = [list(l) for l in Path(sys.argv[1]).read_text().split()]
    town = [list(l) for l in Path(sys.argv[2]).read_text().split()]
    route = clean(route[:ROUTE_ROWS])
    for r, c, cells in ROUTE_FIXES:
        route[r][c:c + len(cells)] = list(cells)

    # Renouet : sol décalqué, bâtiments, fleurs blanches, digue et mer posés à la main. Pas
    # d'herbes hautes en ville : les cases « H » sont des bords d'arbres, de murs ou des haies.
    for r, row in enumerate(town):
        for c, ch in enumerate(row):
            if r > TOWN_SEAWALL_ROW:
                row[c] = "W"
            elif r == TOWN_SEAWALL_ROW:
                row[c] = "C"
            elif ch in "WCF":
                row[c] = "."
            elif ch == "H":
                near = [town[y][x] for y, x in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1))
                        if 0 <= y < len(town) and 0 <= x < len(row)]
                row[c] = "T" if "T" in near else "."
    for col, row, w, h in TOWN_BUILDINGS:
        for r in range(row, row + h):
            for c in range(col, col + w):
                town[r][c] = "B"
    for c, r in TOWN_WHITE_FLOWERS:
        town[r][c] = "w"
    town = clean(town)

    grid = [row[:WIDTH] for row in route]
    for r, row in enumerate(town):
        full = ["W" if r > TOWN_SEAWALL_ROW else "C" if r == TOWN_SEAWALL_ROW else "T"] * WIDTH
        full[TOWN_COL:TOWN_COL + len(row)] = row
        grid.append(full)
    for r, c, cells in TOWN_FIXES:
        grid[r][c:c + len(cells)] = list(cells)

    out = ROOT / "route-1.txt"
    out.write_text("\n".join("".join(r) for r in grid) + "\n")
    if len(sys.argv) > 3:
        img = Image.new("RGB", (WIDTH * 8, len(grid) * 8))
        d = ImageDraw.Draw(img)
        for r, row in enumerate(grid):
            for c, ch in enumerate(row):
                d.rectangle((c * 8, r * 8, c * 8 + 7, r * 8 + 7), fill=COLORS[ch])
        img.save(sys.argv[3])
    print(f"{WIDTH}×{len(grid)} cases → {out.relative_to(ROOT.parent.parent)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
