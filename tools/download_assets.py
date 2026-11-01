#!/usr/bin/env python3
"""Télécharge les assets du jeu (sprites Pokémon, décors 3D, sons, polices, données PokeAPI).

Usage :
    python3 tools/download_assets.py               # Unys : #494 → #649
    python3 tools/download_assets.py --from 1 --to 649

Les fichiers déjà présents sont ignorés : le script peut être relancé sans risque.
Les sprites bruts du monde (Pokémon Platine) vont dans .cache/ : build_spritesheets.py
les remet en forme dans public/assets/characters/.
"""
import argparse
import json
import re
import shutil
import ssl
import sys
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "public/assets"
CACHE = ROOT / ".cache"

SPRITES = "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites"
BW_ANIM = f"{SPRITES}/pokemon/versions/generation-v/black-white/animated"
CRIES = "https://raw.githubusercontent.com/PokeAPI/cries/main/cries/pokemon"
POKEAPI_CSV = "https://raw.githubusercontent.com/PokeAPI/pokeapi/master/data/v2/csv"
SHOWDOWN_TRAINERS = "https://play.pokemonshowdown.com/sprites/trainers"
GOOGLE_FONTS = "https://raw.githubusercontent.com/google/fonts/main/ofl"

# Sprites du monde de Pokémon Platine (décompilation pret/pokeplatinum).
PLATINUM = "https://raw.githubusercontent.com/pret/pokeplatinum/main/res/graphics/field_sprites"
PLATINUM_NPC_LIST = ("https://api.github.com/repos/pret/pokeplatinum/contents/"
                     "res/graphics/field_sprites/npc?ref=main")
PLATINUM_PLAYERS = ["player_m", "player_f"]
PLATINUM_OBJECTS = ["cut_tree", "rock_smash", "strength_boulder", "pokeball", "moss_rock", "ice_rock"]

# Dresseurs de Pokémon Noir & Blanc (sprites de combat Showdown).
TRAINERS = [
    "hilbert", "hilda", "cheren", "bianca", "n", "ghetsis", "alder",
    "cilan", "chili", "cress", "lenora", "burgh", "elesa", "clay",
    "skyla", "brycen", "drayden", "iris",
    "shauntal", "grimsley", "caitlin", "marshal", "juniper",
    "youngster", "lass", "plasmagrunt-gen5bw", "plasmagruntf-gen5bw",
    # Classes de dresseurs de la route.
    "acetrainerf", "bugcatcher", "picnicker", "camper", "hiker", "preschoolerf", "nurse",
]

ITEMS = [
    "poke-ball", "great-ball", "ultra-ball", "master-ball", "premier-ball",
    "potion", "super-potion", "hyper-potion", "max-potion", "full-restore",
    "revive", "max-revive", "antidote", "paralyze-heal", "awakening",
    "burn-heal", "ice-heal", "full-heal", "ether", "elixir",
    "escape-rope", "repel", "rare-candy", "oran-berry", "sitrus-berry",
    "exp-share", "town-map",
]

# Packs Kenney (CC0). Le lien du zip contient un hash : on le lit sur la page du pack.
KENNEY = {
    "city-kit-suburban": "environment",
    "particle-pack": "vfx",
    "interface-sounds": "audio/sfx",
    "rpg-audio": "audio/sfx",
    "impact-sounds": "audio/sfx",
    "music-jingles": "audio/jingles",
}

# Dossiers inutiles pour un jeu web, supprimés après extraction.
PRUNE = {"Unity samples", "FBX format", "OBJ format"}

# Fichiers isolés : (url, destination relative à assets/)
SINGLE_FILES = [
    (f"{GOOGLE_FONTS}/pixelifysans/PixelifySans%5Bwght%5D.ttf", "fonts/pixelify-sans/PixelifySans.ttf"),
    (f"{GOOGLE_FONTS}/pixelifysans/OFL.txt", "fonts/pixelify-sans/OFL.txt"),
    (f"{GOOGLE_FONTS}/silkscreen/Silkscreen-Regular.ttf", "fonts/silkscreen/Silkscreen-Regular.ttf"),
    (f"{GOOGLE_FONTS}/silkscreen/Silkscreen-Bold.ttf", "fonts/silkscreen/Silkscreen-Bold.ttf"),
    (f"{GOOGLE_FONTS}/silkscreen/OFL.txt", "fonts/silkscreen/OFL.txt"),
    (f"{GOOGLE_FONTS}/jersey10/Jersey10-Regular.ttf", "fonts/jersey-10/Jersey10-Regular.ttf"),
    (f"{GOOGLE_FONTS}/jersey10/OFL.txt", "fonts/jersey-10/OFL.txt"),
    ("https://opengameart.org/sites/default/files/battleThemeA.mp3", "audio/music/battle-theme-a.mp3"),
    ("https://opengameart.org/sites/default/files/TownTheme.mp3", "audio/music/town-theme.mp3"),
    ("https://dl.polyhaven.org/file/ph-assets/HDRIs/hdr/1k/kloofendal_48d_partly_cloudy_puresky_1k.hdr",
     "environment/hdri/kloofendal_48d_partly_cloudy_puresky_1k.hdr"),
]

# Archives hors Kenney : (url, dossier d'extraction relatif à assets/, préfixes à garder)
ZIPS = [
    ("https://opengameart.org/sites/default/files/stylized_nature_megakitstandard.zip",
     "environment/quaternius_stylized-nature-megakit", ("glTF/", "License_Standard.txt", "Preview_")),
]
# Le rendu est pixelisé : des textures au-delà de 1024 px ne servent qu'à alourdir le jeu.
MAX_TEXTURE_SIZE = 1024

POKEAPI_TABLES = [
    "pokemon", "pokemon_species", "pokemon_species_names", "pokemon_species_flavor_text",
    "pokemon_stats", "stats", "pokemon_types", "types", "type_names", "type_efficacy",
    "pokemon_abilities", "abilities", "ability_names", "ability_flavor_text",
    "moves", "move_names", "move_flavor_text", "move_meta", "move_meta_stat_changes",
    "move_meta_ailments", "move_damage_classes", "move_targets", "move_effect_prose",
    "pokemon_moves", "pokemon_evolution", "evolution_triggers", "growth_rates",
    "experience", "natures", "nature_names", "version_groups", "items", "item_names",
]

UA = {"User-Agent": "pokemon3d-asset-fetcher/1.0 (+personal project)"}

# Le Python de python.org sur macOS n'a pas de certificats tant que « Install Certificates »
# n'a pas été lancé : on se rabat alors sur le bundle du système.
SSL_CTX = ssl.create_default_context()
if not SSL_CTX.get_ca_certs() and Path("/etc/ssl/cert.pem").exists():
    SSL_CTX = ssl.create_default_context(cafile="/etc/ssl/cert.pem")


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60, context=SSL_CTX) as r:
        return r.read()


def download(url: str, dest: Path, fallback: str | None = None) -> str:
    if dest.exists() and dest.stat().st_size > 0:
        return "skip"
    dest.parent.mkdir(parents=True, exist_ok=True)
    error = None
    for candidate in filter(None, (url, fallback)):
        try:
            data = fetch(candidate)
        except Exception as e:
            error = e
            continue
        tmp = dest.with_suffix(dest.suffix + ".part")
        tmp.write_bytes(data)
        tmp.replace(dest)
        return "ok"
    return f"FAIL {url} ({error})"


def extract_zip(url: str, dest_dir: Path, only: tuple[str, ...] | None = None) -> str:
    if dest_dir.exists() and any(dest_dir.iterdir()):
        return "skip"
    archive = CACHE / "zips" / url.rsplit("/", 1)[-1]
    status = download(url, archive)
    if status.startswith("FAIL"):
        return status
    dest_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as z:
        for member in z.infolist():
            name = member.filename
            # Ignore les fichiers parasites et tout chemin qui sortirait du dossier cible.
            if name.startswith("__MACOSX") or name.endswith((".url", ".DS_Store", "desktop.ini")):
                continue
            if only and not name.startswith(only):
                continue
            target = (dest_dir / name).resolve()
            if not target.is_relative_to(dest_dir.resolve()):
                continue
            z.extract(member, dest_dir)
    for png in dest_dir.rglob("*.png"):
        with Image.open(png) as im:
            if max(im.size) <= MAX_TEXTURE_SIZE:
                continue
            im.thumbnail((MAX_TEXTURE_SIZE, MAX_TEXTURE_SIZE), Image.LANCZOS)
            im.save(png, optimize=True)
    return "ok"


def kenney_zip_url(pack: str) -> str:
    html = fetch(f"https://kenney.nl/assets/{pack}").decode("utf-8", "replace")
    m = re.search(r'https://kenney\.nl/media/pages/assets/[^"]+\.zip', html)
    if not m:
        raise RuntimeError(f"lien zip introuvable pour {pack}")
    return m.group(0)


def pokemon_jobs(first: int, last: int):
    for i in range(first, last + 1):
        yield f"{BW_ANIM}/{i}.gif", ASSETS / f"pokemon/gif/front/{i}.gif", None
        yield f"{BW_ANIM}/back/{i}.gif", ASSETS / f"pokemon/gif/back/{i}.gif", None
        yield f"{BW_ANIM}/shiny/{i}.gif", ASSETS / f"pokemon/gif/front-shiny/{i}.gif", None
        yield f"{BW_ANIM}/back/shiny/{i}.gif", ASSETS / f"pokemon/gif/back-shiny/{i}.gif", None
        yield (f"{SPRITES}/pokemon/versions/generation-vii/icons/{i}.png",
               ASSETS / f"pokemon/icons/{i}.png", None)
        # Cri d'origine (époque NB) si disponible, sinon le cri actuel.
        yield (f"{CRIES}/legacy/{i}.ogg", ASSETS / f"pokemon/cries/{i}.ogg", f"{CRIES}/latest/{i}.ogg")


def platinum_jobs():
    raw = CACHE / "pokeplatinum"
    npc_dir = raw / "npc"
    if not any(npc_dir.glob("*.png")):
        listing = json.loads(fetch(PLATINUM_NPC_LIST))
        for f in listing:
            if f["name"].endswith(".png") and not f["name"].startswith("unused_"):
                yield f"{PLATINUM}/npc/{f['name']}", npc_dir / f["name"], None
    for p in PLATINUM_PLAYERS:
        yield f"{PLATINUM}/player/{p}.png", raw / f"player/{p}.png", None
    for o in PLATINUM_OBJECTS:
        yield f"{PLATINUM}/objects/{o}.png", raw / f"objects/{o}.png", None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="first", type=int, default=494)
    ap.add_argument("--to", dest="last", type=int, default=649)
    args = ap.parse_args()

    results = []
    jobs = list(pokemon_jobs(args.first, args.last))
    try:
        jobs += list(platinum_jobs())
    except Exception as e:
        results.append(f"FAIL liste des PNJ Platine ({e})")
    jobs += [(f"{SHOWDOWN_TRAINERS}/{t}.png", ASSETS / f"trainers/{t}.png", None) for t in TRAINERS]
    jobs += [(f"{SPRITES}/items/{it}.png", ASSETS / f"items/{it}.png", None) for it in ITEMS]
    jobs += [(u, ASSETS / d, None) for u, d in SINGLE_FILES]
    jobs += [(f"{POKEAPI_CSV}/{t}.csv", CACHE / f"pokeapi-csv/{t}.csv", None) for t in POKEAPI_TABLES]

    with ThreadPoolExecutor(max_workers=16) as pool:
        results += list(pool.map(lambda j: download(*j), jobs))

    zips = [(u, ASSETS / d, only) for u, d, only in ZIPS]
    for pack, folder in KENNEY.items():
        try:
            zips.append((kenney_zip_url(pack), ASSETS / folder / f"kenney_{pack}", None))
        except Exception as e:
            results.append(f"FAIL kenney {pack}: {e}")
    with ThreadPoolExecutor(max_workers=4) as pool:
        results += list(pool.map(lambda z: extract_zip(*z), zips))
    for d in [p for p in ASSETS.rglob("*") if p.is_dir() and p.name in PRUNE]:
        shutil.rmtree(d)

    failures = [r for r in results if r.startswith("FAIL")]
    print(f"{results.count('ok')} téléchargés, {results.count('skip')} déjà présents, {len(failures)} échecs")
    for f in failures:
        print(" ", f)
    return 0


if __name__ == "__main__":
    sys.exit(main())
