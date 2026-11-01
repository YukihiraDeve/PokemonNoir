#!/usr/bin/env python3
"""Génère les textures de sol en pixel art (raccordables), avec les couleurs de la référence.

Sortie : public/assets/environment/textures/{grass,grass-shade,dirt}.png  (128×128)
         public/assets/environment/textures/plaster.png  (murs des intérieurs)
         public/assets/environment/textures/{floor-center,emblem-ball}.png  (intérieur du Centre)
         public/assets/environment/textures/{sand,cliff,wood-planks,seawall}.png  (Route 1, Renouet)
         public/assets/environment/textures/{water,foam,hedge}.png  (étang, mer, écume, haies)
         public/assets/environment/textures/center-{glass-low,glass-high,emblem}.png  (Centre Pokémon)
         public/assets/environment/textures/center-glass-{low,high}-glow.png  (vitrages éclairés)
         public/assets/environment/textures/light-{spill,pool}.png  (lumière des fenêtres au sol)
         public/assets/environment/textures/{slabs,town-wall,roof-terrace,awning-stripes}.png  (Arabelle)
         public/assets/environment/textures/leaves-green.png
             feuillage rouge du kit Quaternius (buissons, arbres tordus) repeint en vert

À charger avec NearestFilter + RepeatWrapping dans Three.js. Graine fixe : le résultat
est identique à chaque exécution.
"""
import math
import random
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "public/assets/environment/textures"
KIT = ROOT / "public/assets/environment/quaternius_stylized-nature-megakit/glTF"
SIZE = 128

GRASS = ["#244f0c", "#2f6110", "#3c7414", "#4c8a1a", "#66a823", "#8cc63a"]
GRASS_SHADE = ["#163a09", "#1d470b", "#26550e", "#326612", "#457f18", "#5f9a24"]
DIRT = ["#5e3511", "#6f3f13", "#814b17", "#93591d", "#a96f2e", "#c08a4c"]
FOLIAGE = ["#2a6e12", "#3d8a18", "#5aa622", "#84c232"]
PLASTER = ["#d9d0bc", "#e6dfcd", "#efe9da", "#f6f2e7"]
INK = "#1d1d22"
# Teintes relevées sur les captures de la Route 1 et de Renouet (Noir & Blanc).
SAND = ["#9c7f52", "#b99d68", "#cdb37f", "#dcc592", "#e8d6a8", "#f3e6c2"]
CLIFF = ["#4e2b12", "#6b3d1c", "#864f28", "#a2673a", "#bf8452"]
PLANKS = ["#4a2a12", "#6d4220", "#86552b", "#9d6736", "#b47c46"]
SEAWALL = ["#4a302c", "#6e4a42", "#8f675a", "#ad8472", "#c9a48f"]
CENTER_GLASS = ["#14214a", "#2a4a8a", "#2d5fa6", "#4f86c6", "#9ccbec", "#d8eefa"]
SLABS = ["#a9a89a", "#c4c3b5", "#d2d1c3", "#dcdbcf", "#eceadf", "#d6d9b8"]
TOWN_WALL = ["#4f4740", "#665c53", "#72675d", "#7e7268", "#8c8076"]
ROOF_TERRACE = ["#8d6c48", "#b8946a", "#c9a678"]
HEDGE = ["#2f5a10", "#447c16", "#5c9a1e", "#77b828", "#96d23a", "#c2ea6c"]
WATER = ["#1a4aa2", "#2259b8", "#2a68c8", "#5b98e2", "#9fcaf6", "#ffffff"]
FLOOR_CENTER = ["#c9c2b3", "#e6e1d6", "#f4f1ea"]  # joint, carreau sombre, carreau clair

# Petite Poké Ball pour l'enseigne du Centre (X = contour, R = rouge, W = blanc).


def rgb(hex_color: str) -> tuple[int, int, int, int]:
    return tuple(int(hex_color[i:i + 2], 16) for i in (1, 3, 5)) + (255,)


def tileable_noise(rng: random.Random, cells: int) -> list[list[float]]:
    """Bruit de valeur raccordable (la grille de points se répète sur les bords)."""
    grid = [[rng.random() for _ in range(cells)] for _ in range(cells)]
    smooth = lambda t: t * t * (3 - 2 * t)
    out = []
    for y in range(SIZE):
        row = []
        for x in range(SIZE):
            gx, gy = x * cells / SIZE, y * cells / SIZE
            x0, y0 = int(gx), int(gy)
            tx, ty = smooth(gx - x0), smooth(gy - y0)
            x1, y1 = (x0 + 1) % cells, (y0 + 1) % cells
            a = grid[y0][x0] + (grid[y0][x1] - grid[y0][x0]) * tx
            b = grid[y1][x0] + (grid[y1][x1] - grid[y1][x0]) * tx
            row.append(a + (b - a) * ty)
        out.append(row)
    return out


def base_layer(rng: random.Random, palette: list[str], levels: int) -> Image.Image:
    coarse, fine = tileable_noise(rng, 6), tileable_noise(rng, 24)
    img = Image.new("RGBA", (SIZE, SIZE))
    for y in range(SIZE):
        for x in range(SIZE):
            v = 0.7 * coarse[y][x] + 0.3 * fine[y][x] + rng.uniform(-0.06, 0.06)
            img.putpixel((x, y), rgb(palette[min(levels - 1, max(0, int(v * levels)))]))
    return img


def put(img: Image.Image, x: int, y: int, color: str) -> None:
    img.putpixel((x % SIZE, y % SIZE), rgb(color))


def grass(seed: int, palette: list[str]) -> Image.Image:
    rng = random.Random(seed)
    img = base_layer(rng, palette, 3)
    # Touffes de brins : un « V » clair, ombré d'un pixel sombre à la base.
    for _ in range(260):
        x, y = rng.randrange(SIZE), rng.randrange(SIZE)
        light = palette[rng.choice([3, 3, 3, 4, 4, 5])]
        height = rng.choice([1, 2, 2, 3])
        if rng.random() < 0.35:
            # Brin isolé, légèrement penché.
            for dy in range(height + 1):
                put(img, x + (dy == height), y - dy, light)
        else:
            for dy in range(height):
                put(img, x - 1 - (dy == height - 1), y - dy, light)
                put(img, x + 1 + (dy == height - 1), y - dy, light)
            put(img, x, y - height + 1, light)
        put(img, x, y + 1, palette[0])
    # Quelques points de lumière isolés.
    for _ in range(70):
        put(img, rng.randrange(SIZE), rng.randrange(SIZE), palette[5])
    return img


def dirt(seed: int, palette: list[str]) -> Image.Image:
    rng = random.Random(seed)
    img = base_layer(rng, palette[1:5], 4)
    # Petits cailloux : un bloc clair avec une ombre en bas à droite.
    for _ in range(70):
        x, y = rng.randrange(SIZE), rng.randrange(SIZE)
        w, h = rng.choice([(2, 1), (2, 2), (3, 2)])
        for dx in range(w):
            for dy in range(h):
                put(img, x + dx, y + dy, palette[5 if dy == 0 else 4])
            put(img, x + dx + 1, y + h, palette[0])
        put(img, x + w, y + h - 1, palette[0])
    # Grains sombres.
    for _ in range(320):
        put(img, rng.randrange(SIZE), rng.randrange(SIZE), palette[rng.choice([0, 1])])
    return img


def plaster(seed: int, palette: list[str]) -> Image.Image:
    """Crépi clair avec une fine ligne de joint tous les 32 pixels."""
    img = base_layer(random.Random(seed), palette, 4)
    for y in range(0, SIZE, 32):
        for x in range(SIZE):
            put(img, x, y, palette[0])
    return img


def cliff(seed: int, palette: list[str]) -> Image.Image:
    """Paroi rocheuse : colonnes bosselées aux bords irréguliers, éclairées à gauche, fissurées."""
    rng = random.Random(seed)
    lumps = tileable_noise(rng, 8)
    # Bords des colonnes : positions de base, chacune ondule verticalement (motif raccordable).
    bases, x = [], 0
    while x < SIZE - 6:
        bases.append(x)
        x += rng.randint(7, 14)
    waves = [(rng.uniform(0.8, 2.0), rng.randint(1, 3), rng.uniform(0, math.tau)) for _ in bases]
    img = Image.new("RGBA", (SIZE, SIZE))
    for y in range(SIZE):
        edges = [b + round(a * math.sin(k * y / SIZE * math.tau + ph)) for b, (a, k, ph) in zip(bases, waves)]
        edges.append(edges[0] + SIZE)
        for i in range(len(edges) - 1):
            left, right = edges[i], edges[i + 1]
            for xx in range(left, right):
                t = (xx - left) / max(1, right - left - 1)
                v = 0.85 - 0.75 * t + 0.5 * (lumps[y][xx % SIZE] - 0.5) + rng.uniform(-0.08, 0.08)
                color = palette[1 + min(3, max(0, int(v * 4)))]
                if xx == left:
                    color = palette[0]
                put(img, xx, y, color)
    for _ in range(45):  # fissures et petites corniches
        x, y = rng.randrange(SIZE), rng.randrange(SIZE)
        for dx in range(rng.randint(2, 5)):
            put(img, x + dx, y, palette[0])
            put(img, x + dx, y + 1, palette[4])
    return img


def bricks(seed: int, palette: list[str]) -> Image.Image:
    """Mur de pierres taillées en rangées décalées (digue de Renouet)."""
    rng = random.Random(seed)
    img = Image.new("RGBA", (SIZE, SIZE), rgb(palette[0]))
    row_h, brick_w = 8, 16
    for row in range(SIZE // row_h):
        offset = 0 if row % 2 == 0 else brick_w // 2
        for b in range(SIZE // brick_w):
            tone = rng.choice([2, 2, 3])
            x0 = b * brick_w + offset
            for dx in range(1, brick_w):
                for dy in range(1, row_h):
                    color = palette[tone]
                    if dy == 1:
                        color = palette[min(4, tone + 1)]
                    elif dy == row_h - 1 or dx == brick_w - 1:
                        color = palette[1]
                    put(img, x0 + dx, row * row_h + dy, color)
    for _ in range(140):
        put(img, rng.randrange(SIZE), rng.randrange(SIZE), palette[rng.choice([1, 4])])
    return img


def water(seed: int, palette: list[str]) -> Image.Image:
    """Eau : fond bleu marbré, petites vagues claires en croissant, quelques reflets blancs."""
    rng = random.Random(seed)
    img = base_layer(rng, palette[:3], 3)
    for _ in range(80):
        x, y = rng.randrange(SIZE), rng.randrange(SIZE)
        length = rng.randint(4, 9)
        for dx in range(length):
            edge = dx in (0, length - 1)
            put(img, x + dx, y + (1 if edge else 0), palette[3])
        put(img, x + length // 2, y - 1, palette[4])
        for dx in range(1, length - 1):
            put(img, x + dx, y + 1, palette[0])  # creux sous la crête
    for _ in range(10):
        x, y = rng.randrange(SIZE), rng.randrange(SIZE)
        for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
            put(img, x + dx, y + dy, palette[5] if (dx, dy) == (0, 0) else palette[4])
    return img


def foam(seed: int, width: int = SIZE, height: int = 16) -> Image.Image:
    """Écume le long des berges : liseré blanc ondulé côté rive (bas de l'image), bulles au large."""
    rng = random.Random(seed)
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    white, light = (255, 255, 255, 255), (196, 226, 255, 235)
    phase = [rng.uniform(0, math.tau) for _ in range(3)]
    for x in range(width):
        t = x / width * math.tau
        thick = 4 + 1.6 * math.sin(2 * t + phase[0]) + 1.2 * math.sin(5 * t + phase[1]) + 0.8 * math.sin(9 * t + phase[2])
        top = height - 1 - round(thick)
        for y in range(top, height):
            img.putpixel((x, y), white)
        img.putpixel((x, top - 1), light)
        # Second liseré, interrompu : la vague suivante.
        if math.sin(3 * t + phase[1]) > -0.2:
            img.putpixel((x, max(0, top - 5 + round(math.sin(7 * t)))), light)
    for _ in range(width // 4):
        x, y = rng.randrange(width), rng.randrange(height - 9)
        img.putpixel((x, y), light if rng.random() < 0.6 else white)
    return img


def planks(seed: int, palette: list[str]) -> Image.Image:
    """Bardage de planches horizontales : joints sombres, raccords décalés, veinage."""
    rng = random.Random(seed)
    img = Image.new("RGBA", (SIZE, SIZE))
    for row in range(SIZE // 16):
        tone = rng.choice([2, 2, 3])
        seam = rng.randrange(SIZE)
        for x in range(SIZE):
            for dy in range(16):
                color = palette[tone]
                if dy == 0:
                    color = palette[0]
                elif dy == 1:
                    color = palette[4]
                elif (x - seam) % SIZE == 0:
                    color = palette[1]
                elif rng.random() < 0.04:
                    color = palette[tone - 1]
                put(img, x, row * 16 + dy, color)
    return img


def floor_tiles(seed: int, palette: list[str], tile: int = 32) -> Image.Image:
    """Carrelage en damier avec joints fins et léger grain."""
    rng = random.Random(seed)
    img = Image.new("RGBA", (SIZE, SIZE))
    for y in range(SIZE):
        for x in range(SIZE):
            if x % tile == 0 or y % tile == 0:
                color = palette[0]
            else:
                color = palette[1 + ((x // tile + y // tile) % 2)]
            img.putpixel((x, y), rgb(color))
    for _ in range(400):
        x, y = rng.randrange(SIZE), rng.randrange(SIZE)
        if x % tile and y % tile:
            put(img, x, y, palette[1])
    return img


def slabs(seed: int, palette: list[str]) -> Image.Image:
    """Grandes dalles claires d'Arabelle (une par texture, soit deux cases) : arêtes éclairées en
    haut à gauche, joints sombres, fines fissures et grain."""
    rng = random.Random(seed)
    img = base_layer(rng, palette[1:4], 3)
    for i in range(SIZE):
        put(img, i, 0, palette[0])
        put(img, 0, i, palette[0])
        put(img, i, 1, palette[4])
        put(img, 1, i, palette[4])
        put(img, i, SIZE - 1, palette[1])
        put(img, SIZE - 1, i, palette[1])
    for _ in range(9):  # fissures en zigzag, couleur de mousse claire
        x, y = rng.randrange(8, SIZE - 8), rng.randrange(8, SIZE - 8)
        dx, dy = rng.choice([(1, 0), (0, 1), (1, 1), (1, -1)])
        for _ in range(rng.randint(6, 16)):
            put(img, x, y, palette[5])
            x += dx if rng.random() < 0.8 else 0
            y += dy if rng.random() < 0.8 else rng.choice([-1, 1])
    for _ in range(220):
        put(img, rng.randrange(SIZE), rng.randrange(SIZE), palette[rng.choice([1, 4])])
    return img


def town_wall(seed: int, palette: list[str]) -> Image.Image:
    """Mur de soutènement taupe : panneaux lisses, joints horizontaux discrets, salissures."""
    rng = random.Random(seed)
    img = base_layer(rng, palette[1:4], 3)
    for y in range(0, SIZE, 32):
        for x in range(SIZE):
            put(img, x, y, palette[0])
            put(img, x, y + 1, palette[4])
    for x in range(0, SIZE, 64):
        for y in range(SIZE):
            put(img, x + (16 if (y // 32) % 2 else 0), y, palette[0])
    for _ in range(160):
        put(img, rng.randrange(SIZE), rng.randrange(SIZE), palette[rng.choice([0, 1])])
    return img


def awning_stripes(w: int = 64, h: int = 32) -> Image.Image:
    """Toile d'auvent rayée rouge et blanc, ourlet plus sombre en bas."""
    img = Image.new("RGBA", (w, h))
    for y in range(h):
        for x in range(w):
            red = (x // 8) % 2 == 0
            color = ("#b81e24" if red else "#d8d2c6") if y >= h - 4 else ("#e0302f" if red else "#f6f2ea")
            img.putpixel((x, y), rgb(color))
    return img


def emblem_ball(size: int = 32) -> Image.Image:
    """Grande Poké Ball pixel art pour le mur du Centre, sur fond crème (pas de transparence)."""
    img = Image.new("RGBA", (size, size), rgb(PLASTER[2]))
    c = (size - 1) / 2
    r = size / 2 - 1.5
    for y in range(size):
        for x in range(size):
            d = ((x - c) ** 2 + (y - c) ** 2) ** 0.5
            if d > r + 0.5:
                continue
            if d > r - 1.2:
                color = INK
            elif d < 5.5:
                color = INK if d > 3.8 else "#ffffff"
            elif abs(y - c) < 1.6:
                color = INK
            else:
                color = "#e8463a" if y < c else "#f6f6f2"
            img.putpixel((x, y), rgb(color))
    return img


def _steps(top: str, bottom: str, n: int) -> list[tuple[int, int, int, int]]:
    """Dégradé en paliers (pixel art) de `bottom` vers `top`."""
    a, b = rgb(bottom), rgb(top)
    return [tuple(round(a[k] + (b[k] - a[k]) * i / (n - 1)) for k in range(3)) + (255,) for i in range(n)]


def center_glass_low() -> Image.Image:
    """Une travée du vitrage du rez-de-chaussée du Centre Pokémon (1,25 × 2,95 m) : montants
    marine, petite rangée de carreaux tramés en haut et en bas, grande vitre au milieu."""
    w, h = 64, 96
    img = Image.new("RGBA", (w, h), rgb(CENTER_GLASS[0]))
    def short_row(y0, y1):
        for y in range(y0, y1):
            for x in range(4, w):
                color = CENTER_GLASS[5] if (x + y) % 2 == 0 and (y - y0) % 4 < 2 else CENTER_GLASS[4]
                if y == y0 or x == 4:
                    color = CENTER_GLASS[5]
                if y == y1 - 1 or x == w - 1:
                    color = CENTER_GLASS[2]
                img.putpixel((x, y), rgb(color) if isinstance(color, str) else color)
    short_row(4, 20)
    short_row(76, 92)
    steps = _steps(CENTER_GLASS[4], CENTER_GLASS[2], 6)
    for y in range(24, 72):
        for x in range(4, w):
            img.putpixel((x, y), steps[min(5, (71 - y) // 8)])
    for x in range(6, w - 2):  # liseré clair en haut de la grande vitre, ombre en bas
        img.putpixel((x, 25), rgb(CENTER_GLASS[5]))
        img.putpixel((x, 70), rgb(CENTER_GLASS[1]))
    for y in range(26, 70):
        img.putpixel((5, y), rgb(CENTER_GLASS[3]))
    for y in range(h):  # reflet du montant
        img.putpixel((1, y), rgb(CENTER_GLASS[1]))
    return img


def center_glass_high() -> Image.Image:
    """Une travée du vitrage de l'étage (0,85 × 1,7 m) : grande vitre en dégradé, traversée
    par la bande claire du Centre Pokémon."""
    w, h = 32, 72
    img = Image.new("RGBA", (w, h), rgb(CENTER_GLASS[0]))
    steps = _steps(CENTER_GLASS[4], CENTER_GLASS[2], 7)
    for y in range(3, h - 3):
        for x in range(3, w):
            img.putpixel((x, y), steps[min(6, (h - 4 - y) // 10)])
    for y in range(4, h - 4):
        img.putpixel((4, y), rgb(CENTER_GLASS[3]))
    for x in range(4, w - 1):
        img.putpixel((x, 4), rgb(CENTER_GLASS[5]))
    for y in range(h):
        img.putpixel((1, y), rgb(CENTER_GLASS[1]))
    band = rgb("#d6ebf7")
    for y in range(20, 30):  # bande claire, continue d'une travée à l'autre (montants compris)
        for x in range(w):
            base = img.getpixel((x, y))
            k = 0.78 if y not in (20, 29) else 0.55
            img.putpixel((x, y), tuple(round(base[i] * (1 - k) + band[i] * k) for i in range(3)) + (255,))
    return img


def window_glow(img: Image.Image, tint: str = "#5fb0ff", frame: float = 0.22) -> Image.Image:
    """Carte d'émission d'un vitrage : les carreaux s'allument presque uniformément (lumière
    intérieure, un peu plus forte sur les parties claires), les montants sombres restent éteints."""
    out = Image.new("RGBA", img.size)
    t = rgb(tint)
    for y in range(img.height):
        for x in range(img.width):
            r, g, b, _ = img.getpixel((x, y))
            lum = (0.3 * r + 0.59 * g + 0.11 * b) / 255
            k = 0.0 if lum < frame else 0.62 + 0.38 * (lum - frame) / (1 - frame)
            out.putpixel((x, y), tuple(round(c * k) for c in t[:3]) + (255,))
    return out


def light_spill(size: int = 64, radial: bool = False) -> Image.Image:
    """Lumière tombée au sol devant des fenêtres (blanc, opacité en dégradé ; mur en bas de
    l'image). `radial` : flaque centrée devant une porte."""
    img = Image.new("RGBA", (size, size), (255, 255, 255, 0))
    smooth = lambda t: max(0.0, min(1.0, t)) ** 2 * (3 - 2 * max(0.0, min(1.0, t)))
    for y in range(size):
        v = (size - 1 - y) / (size - 1)  # 0 contre le mur
        for x in range(size):
            u = x / (size - 1)
            if radial:
                a = max(0.0, 1 - math.hypot((u - 0.5) * 2, v)) ** 1.6
            else:
                a = (1 - v) ** 1.8 * smooth(u / 0.2) * smooth((1 - u) / 0.2)
            img.putpixel((x, y), (255, 255, 255, round(255 * a)))
    return img


def center_emblem(size: int = 64) -> Image.Image:
    """Emblème Poké Ball du Centre (anneau, petit cercle, barre) en clair sur fond transparent."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    light, edge, core = rgb("#e4f3ff"), rgb("#8ec2ea"), rgb("#4f86c6")
    c = (size - 1) / 2
    for y in range(size):
        for x in range(size):
            d = ((x - c) ** 2 + (y - c) ** 2) ** 0.5
            color = None
            if 23 <= d <= 30.5:
                color = edge if d > 29 or d < 24.2 else light
            elif d <= 11:
                color = core if d < 6.5 else (edge if d < 7.6 else light)
            elif abs(y - c) < 2.2 and d < 23:
                color = light
            if color:
                img.putpixel((x, y), color)
    return img


def recolor_foliage(src: Path, palette: list[str]) -> Image.Image:
    """Remplace la teinte d'une texture de feuillage en gardant son relief et son alpha."""
    img = Image.open(src).convert("RGBA")
    lum = sorted(p[0] for p in img.getdata() if p[3] > 0)
    lo, hi = lum[len(lum) // 20], lum[-len(lum) // 20]
    ramp = [rgb(c) for c in palette]

    def shade(p):
        if p[3] == 0:
            return p
        # Texture unie (simple masque) : on prend le milieu de la rampe.
        v = 0.5 if hi - lo < 8 else min(1.0, max(0.0, (p[0] - lo) / (hi - lo)))
        t = v * (len(ramp) - 1)
        i = min(len(ramp) - 2, int(t))
        a, b, f = ramp[i], ramp[i + 1], t - i
        return tuple(round(a[k] + (b[k] - a[k]) * f) for k in range(3)) + (p[3],)

    img.putdata([shade(p) for p in img.getdata()])
    return img


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    textures = {
        "grass": grass(7, GRASS),
        "grass-shade": grass(7, GRASS_SHADE),
        "dirt": dirt(11, DIRT),
        "plaster": plaster(3, PLASTER),
        "floor-center": floor_tiles(13, FLOOR_CENTER),
        "emblem-ball": emblem_ball(),
        "sand": dirt(19, SAND),
        "cliff": cliff(23, CLIFF),
        "seawall": bricks(31, SEAWALL),
        "water": water(37, WATER),
        "foam": foam(41),
        "hedge": grass(43, HEDGE),
        "center-glass-low": center_glass_low(),
        "center-glass-high": center_glass_high(),
        "center-glass-low-glow": window_glow(center_glass_low()),
        "center-glass-high-glow": window_glow(center_glass_high()),
        "slabs": slabs(47, SLABS),
        "town-wall": town_wall(53, TOWN_WALL),
        "roof-terrace": floor_tiles(59, ROOF_TERRACE, tile=64),
        "awning-stripes": awning_stripes(),
        "light-spill": light_spill(),
        "light-pool": light_spill(radial=True),
        "center-emblem": center_emblem(),
        "wood-planks": planks(29, PLANKS),
    }
    if (KIT / "Leaves_TwistedTree_C.png").exists():
        textures["leaves-green"] = recolor_foliage(KIT / "Leaves_TwistedTree_C.png", FOLIAGE)
    for name, img in textures.items():
        img.save(OUT / f"{name}.png", optimize=True)
    print(f"{len(textures)} textures dans {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
