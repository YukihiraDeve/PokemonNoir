#!/usr/bin/env python3
"""Grille d'Arabelle (Accumula Town), relevée case par case sur docs/reference/accumula.webp.

La capture est à 37 px par case, origine (12 ; 8,5) : 38 colonnes × 34 lignes. La ville se pose au
nord de la Route 1, décalée de deux colonnes pour que son chemin de sable rejoigne celui de la route
(la dernière colonne de forêt, à l'est, sort de la grille).

Sorties (colonnes de la grille de la Route 1, lignes de la ville de 0 à 33 du nord au sud) :
  tools/maps/arabelle.txt          nature du sol
  tools/maps/arabelle-levels.txt   niveau de chaque case

Lettres en plus de celles de la Route 1 :
  P dalles claires       K muret ou rambarde en bord de niveau (infranchissable)
  X sol infranchissable (sous un escalier, derrière le Centre)   E escalier de pierre
Niveaux : 0 rue principale, U plateau de la maison bleue, D place en contrebas, p plateau de
l'estrade (35 cm), r rampe (escaliers,
talus boisé : hauteur calculée par build_scenes.py).

Usage : python3 tools/maps/build_arabelle.py
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent
COLS, ROWS = 38, 34
SHIFT = 2  # colonne de la capture → colonne de la grille

# (lettre, colonnes, lignes) dans le repère de la capture, bornes incluses ; peints dans l'ordre.
TERRAIN = [
    ("P", (0, 37), (0, 33)),
    # Forêt : bordures et bosquets.
    ("T", (0, 37), (0, 1)), ("T", (0, 9), (2, 9)), ("T", (16, 17), (2, 9)), ("T", (34, 37), (0, 33)),
    ("T", (4, 9), (13, 15)), ("T", (0, 3), (28, 33)), ("T", (0, 21), (31, 33)), ("T", (27, 33), (29, 33)),
    (".", (4, 5), (9, 9)),
    # Bâtiments : trois immeubles, bâtiment au toit vert, maison bleue, Centre Pokémon, scène.
    ("B", (10, 15), (2, 9)), ("B", (18, 23), (2, 9)), ("B", (4, 9), (16, 23)), ("B", (0, 3), (9, 13)),
    ("B", (26, 31), (4, 8)), ("B", (27, 33), (14, 17)), ("B", (29, 31), (18, 18)),
    # Estrade : on marche dessus (niveau p) ; seul son panneau d'information arrête le passage.
    ("X", (29, 31), (22, 22)),
    # Plateau de la maison bleue : rambardes, pelouse, escalier vers la rue.
    ("K", (24, 33), (2, 2)), ("K", (33, 33), (2, 11)), ("K", (26, 33), (11, 11)), ("K", (26, 26), (8, 11)),
    (".", (27, 32), (8, 10)),
    ("E", (24, 25), (5, 11)), ("K", (23, 23), (10, 11)),
    ("X", (26, 33), (12, 13)),
    # Jardin aux bancs, rambarde au-dessus de la place en contrebas.
    (".", (11, 17), (13, 21)), ("K", (10, 21), (22, 22)),
    # Place en contrebas : éboulis au pied du mur, escalier, rambarde côté est.
    ("X", (10, 11), (23, 24)), ("E", (16, 21), (23, 24)), ("X", (16, 21), (25, 25)), ("K", (22, 22), (25, 30)),
    # Talus boisé à l'ouest (une pente de forêt, de la rue jusqu'à la place en contrebas).
    ("T", (0, 3), (14, 27)),
    # Sortie sud vers la Route 1 : herbe et sable.
    (".", (22, 22), (31, 33)), ("S", (23, 26), (31, 33)),
]
LEVELS = [
    ("0", (0, 37), (0, 33)),
    ("U", (24, 33), (2, 11)), ("r", (24, 25), (5, 11)),
    ("D", (4, 9), (16, 30)), ("D", (10, 21), (23, 30)), ("r", (16, 21), (23, 24)),
    ("r", (0, 3), (14, 27)),
    ("p", (28, 32), (23, 27)),
]


def paint(layers):
    grid = [["?"] * COLS for _ in range(ROWS)]
    for ch, (c0, c1), (r0, r1) in layers:
        for r in range(r0, r1 + 1):
            for c in range(c0 + SHIFT, min(COLS - 1, c1 + SHIFT) + 1):
                grid[r][c] = ch
    for row in grid:  # colonnes laissées libres par le décalage : forêt, au niveau de sa voisine
        row[:SHIFT] = ["T" if layers is TERRAIN else row[SHIFT]] * SHIFT
    return ["".join(row) for row in grid]


def main() -> int:
    for name, layers in (("arabelle.txt", TERRAIN), ("arabelle-levels.txt", LEVELS)):
        rows = paint(layers)
        (ROOT / name).write_text("\n".join(rows) + "\n")
        print(f"{name} : {len(rows[0])}×{len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
