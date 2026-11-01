#!/usr/bin/env python3
"""Construit les données de jeu (JSON compact) à partir des CSV PokeAPI en cache.

Entrée  : .cache/pokeapi-csv/*.csv  (téléchargés par download_assets.py)
Sortie  : public/data/pokemon.json, moves.json, types.json, natures.json, growth-rates.json

Mécaniques et types actuels (type Fée inclus), apprentissages de Noir 2 & Blanc 2,
textes en français (et anglais pour les noms).

Usage :
    python3 tools/build_data.py               # Unys : #494 → #649
    python3 tools/build_data.py --from 1 --to 649
"""
import argparse
import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSV_DIR = ROOT / ".cache/pokeapi-csv"
OUT = ROOT / "public/data"

FR, EN = "5", "9"
VG_B2W2, VG_BW = "14", "11"
VERSION_BLACK, VERSION_WHITE = "17", "18"
METHOD_LEVEL_UP, METHOD_MACHINE = "1", "4"
# Couleurs usuelles des types, pour dessiner les badges de l'interface.
TYPE_COLORS = {
    "normal": "#A8A77A", "fighting": "#C22E28", "flying": "#A98FF3", "poison": "#A33EA1",
    "ground": "#E2BF65", "rock": "#B6A136", "bug": "#A6B91A", "ghost": "#735797",
    "steel": "#B7B7CE", "fire": "#EE8130", "water": "#6390F0", "grass": "#7AC74C",
    "electric": "#F7D02C", "psychic": "#F95587", "ice": "#96D9D6", "dragon": "#6F35FC",
    "dark": "#705746", "fairy": "#D685AD",
}
STAT_KEYS = {"hp": "hp", "attack": "atk", "defense": "def",
             "special-attack": "spa", "special-defense": "spd", "speed": "spe",
             "accuracy": "acc", "evasion": "eva"}


def table(name: str) -> list[dict]:
    with open(CSV_DIR / f"{name}.csv", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def by_id(name: str) -> dict:
    return {r["id"]: r for r in table(name)}


def names(name: str, key: str, field: str = "name") -> dict:
    """{id: {"fr": ..., "en": ...}} depuis une table *_names."""
    out = defaultdict(dict)
    for r in table(name):
        if r["local_language_id"] in (FR, EN):
            out[r[key]]["fr" if r["local_language_id"] == FR else "en"] = r[field]
    return out


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("­", "")).strip()


def num(v: str):
    return int(v) if v not in ("", None) else None


def pick_flavor(rows: list[dict], key: str, preferred: list[str]) -> dict:
    """Texte FR par objet : version préférée si elle existe, sinon la plus récente."""
    cands = defaultdict(dict)
    for r in rows:
        if r["language_id"] == FR:
            cands[r[key]][r.get("version_id") or r.get("version_group_id")] = r["flavor_text"]
    out = {}
    for obj, texts in cands.items():
        ver = next((v for v in preferred if v in texts), max(texts, key=int))
        out[obj] = clean(texts[ver])
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="first", type=int, default=494)
    ap.add_argument("--to", dest="last", type=int, default=649)
    args = ap.parse_args()
    ids = {str(i) for i in range(args.first, args.last + 1)}

    types = by_id("types")
    type_key = {i: r["identifier"] for i, r in types.items() if int(i) < 10000}
    stats = {i: STAT_KEYS[r["identifier"]] for i, r in by_id("stats").items()
             if r["identifier"] in STAT_KEYS}
    growth = {i: r["identifier"] for i, r in by_id("growth_rates").items()}
    items = by_id("items")

    # ---- Types
    type_names = names("type_names", "type_id")
    chart = defaultdict(dict)
    for r in table("type_efficacy"):
        if r["damage_factor"] != "100":
            chart[type_key[r["damage_type_id"]]][type_key[r["target_type_id"]]] = int(r["damage_factor"]) / 100
    types_json = {
        "types": [{"key": k, "name": type_names[i], "color": TYPE_COLORS[k]} for i, k in type_key.items()
                  if k in TYPE_COLORS],
        # chart[attaque][défense] = multiplicateur ; absent = x1
        "chart": chart,
    }

    # ---- Pokémon
    species = by_id("pokemon_species")
    pokemon = {i: r for i, r in by_id("pokemon").items() if i in ids}
    sp_names = names("pokemon_species_names", "pokemon_species_id")
    sp_genus = names("pokemon_species_names", "pokemon_species_id", "genus")
    sp_flavor = pick_flavor(table("pokemon_species_flavor_text"), "species_id",
                            [VERSION_BLACK, VERSION_WHITE])
    ab_names = names("ability_names", "ability_id")
    ab_flavor = pick_flavor(table("ability_flavor_text"), "ability_id", [VG_B2W2, VG_BW])
    abilities = by_id("abilities")
    item_names = names("item_names", "item_id")

    poke_types, poke_stats, poke_evs, poke_abilities = (defaultdict(list), defaultdict(dict),
                                                       defaultdict(dict), defaultdict(list))
    for r in table("pokemon_types"):
        if r["pokemon_id"] in ids:
            poke_types[r["pokemon_id"]].append((int(r["slot"]), type_key[r["type_id"]]))
    for r in table("pokemon_stats"):
        if r["pokemon_id"] in ids:
            poke_stats[r["pokemon_id"]][stats[r["stat_id"]]] = int(r["base_stat"])
            if r["effort"] != "0":
                poke_evs[r["pokemon_id"]][stats[r["stat_id"]]] = int(r["effort"])
    for r in table("pokemon_abilities"):
        if r["pokemon_id"] in ids:
            a = abilities[r["ability_id"]]
            poke_abilities[r["pokemon_id"]].append((int(r["slot"]), {
                "key": a["identifier"], "name": ab_names[a["id"]],
                "hidden": r["is_hidden"] == "1", "description": ab_flavor.get(a["id"], ""),
            }))

    triggers = {i: r["identifier"] for i, r in by_id("evolution_triggers").items()}
    evolutions = defaultdict(list)
    for r in table("pokemon_evolution"):
        to = r["evolved_species_id"]
        frm = species[to]["evolves_from_species_id"] if to in species else ""
        if frm in ids:
            evo = {"to": int(to), "trigger": triggers[r["evolution_trigger_id"]]}
            if r["minimum_level"]:
                evo["level"] = int(r["minimum_level"])
            for field, out_key in (("trigger_item_id", "item"), ("held_item_id", "heldItem")):
                if r[field]:
                    evo[out_key] = {"key": items[r[field]]["identifier"], "name": item_names[r[field]]}
            for field in ("minimum_happiness", "known_move_id", "trade_species_id"):
                if r[field]:
                    evo[re.sub(r"_(\w)", lambda m: m.group(1).upper(), field)] = int(r[field])
            if r["time_of_day"]:
                evo["timeOfDay"] = r["time_of_day"]
            if evo not in evolutions[frm]:
                evolutions[frm].append(evo)

    learn = defaultdict(lambda: {"levelUp": [], "tm": []})
    learn_vg = {}
    for r in table("pokemon_moves"):
        pid, vg = r["pokemon_id"], r["version_group_id"]
        if pid not in ids or vg not in (VG_B2W2, VG_BW):
            continue
        # B2W2 en priorité, NB seulement si le Pokémon en est absent.
        if learn_vg.setdefault(pid, vg) != vg:
            if vg == VG_B2W2:
                learn_vg[pid] = vg
                learn[pid] = {"levelUp": [], "tm": []}
            else:
                continue
        if r["pokemon_move_method_id"] == METHOD_LEVEL_UP:
            learn[pid]["levelUp"].append([int(r["level"]), int(r["move_id"])])
        elif r["pokemon_move_method_id"] == METHOD_MACHINE:
            learn[pid]["tm"].append(int(r["move_id"]))

    pokedex = []
    for pid in sorted(pokemon, key=int):
        p, s = pokemon[pid], species[pokemon[pid]["species_id"]]
        moves = learn[pid]
        pokedex.append({
            "id": int(pid),
            "key": p["identifier"],
            "name": sp_names[pid],
            "genus": sp_genus[pid].get("fr", ""),
            "types": [t for _, t in sorted(poke_types[pid])],
            "stats": poke_stats[pid],
            "evYield": poke_evs[pid],
            "abilities": [a for _, a in sorted(poke_abilities[pid], key=lambda x: x[0])],
            "height": int(p["height"]) / 10,   # mètres
            "weight": int(p["weight"]) / 10,   # kg
            "baseExp": num(p["base_experience"]),
            "captureRate": int(s["capture_rate"]),
            "baseHappiness": num(s["base_happiness"]),
            "genderRate": int(s["gender_rate"]),  # femelles sur 8, -1 = asexué
            "growthRate": growth[s["growth_rate_id"]],
            "isLegendary": s["is_legendary"] == "1",
            "isMythical": s["is_mythical"] == "1",
            "evolvesFrom": num(s["evolves_from_species_id"]),
            "evolutions": evolutions.get(pid, []),
            "description": sp_flavor.get(pid, ""),
            "learnset": {"levelUp": sorted(moves["levelUp"]), "tm": sorted(set(moves["tm"]))},
        })

    # ---- Attaques (seulement celles apprises par les Pokémon exportés)
    used = {m for p in pokedex for _, m in p["learnset"]["levelUp"]} | \
           {m for p in pokedex for m in p["learnset"]["tm"]}
    mv_names = names("move_names", "move_id")
    mv_flavor = pick_flavor(table("move_flavor_text"), "move_id", [VG_B2W2, VG_BW])
    classes = {i: r["identifier"] for i, r in by_id("move_damage_classes").items()}
    targets = {i: r["identifier"] for i, r in by_id("move_targets").items()}
    ailments = {i: r["identifier"] for i, r in by_id("move_meta_ailments").items()}
    meta = {r["move_id"]: r for r in table("move_meta")}
    stat_changes = defaultdict(list)
    for r in table("move_meta_stat_changes"):
        stat_changes[r["move_id"]].append({"stat": stats[r["stat_id"]], "change": int(r["change"])})
    effects = {r["move_effect_id"]: r["short_effect"] for r in table("move_effect_prose")
               if r["local_language_id"] == EN}

    moves_json = {}
    for r in table("moves"):
        if int(r["id"]) not in used:
            continue
        mid, m = r["id"], meta.get(r["id"], {})
        effect = effects.get(r["effect_id"], "").replace("$effect_chance", r["effect_chance"] or "?")
        moves_json[mid] = {
            "id": int(mid),
            "key": r["identifier"],
            "name": mv_names[mid],
            "type": type_key[r["type_id"]],
            "category": classes[r["damage_class_id"]],  # physical | special | status
            "power": num(r["power"]),
            "accuracy": num(r["accuracy"]),             # null = touche toujours
            "pp": num(r["pp"]),
            "priority": int(r["priority"]),
            "target": targets[r["target_id"]],
            "effectChance": num(r["effect_chance"]),
            "meta": {
                "ailment": ailments.get(m.get("meta_ailment_id", ""), "none"),
                "ailmentChance": num(m.get("ailment_chance", "")) or 0,
                "minHits": num(m.get("min_hits", "")),
                "maxHits": num(m.get("max_hits", "")),
                "drain": num(m.get("drain", "")) or 0,
                "healing": num(m.get("healing", "")) or 0,
                "critRate": num(m.get("crit_rate", "")) or 0,
                "flinchChance": num(m.get("flinch_chance", "")) or 0,
                "statChance": num(m.get("stat_chance", "")) or 0,
                "statChanges": stat_changes.get(mid, []),
            },
            "description": mv_flavor.get(mid, ""),
            "effect": clean(re.sub(r"\[([^\]]*)\]\{[^}]+\}", lambda x: x.group(1), effect)),
        }

    # ---- Natures
    nat_names = names("nature_names", "nature_id")
    natures_json = [{
        "key": r["identifier"], "name": nat_names[r["id"]],
        "up": stats[r["increased_stat_id"]] if r["increased_stat_id"] != r["decreased_stat_id"] else None,
        "down": stats[r["decreased_stat_id"]] if r["increased_stat_id"] != r["decreased_stat_id"] else None,
    } for r in sorted(table("natures"), key=lambda r: int(r["game_index"]))]

    # ---- Courbes d'expérience : xp totale requise pour chaque niveau (index 0 = niveau 1)
    curves = defaultdict(list)
    for r in sorted(table("experience"), key=lambda r: int(r["level"])):
        curves[growth[r["growth_rate_id"]]].append(int(r["experience"]))

    OUT.mkdir(exist_ok=True)
    for name, obj in (("pokemon", pokedex), ("moves", moves_json), ("types", types_json),
                      ("natures", natures_json), ("growth-rates", curves)):
        (OUT / f"{name}.json").write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")),
                                          encoding="utf-8")
    print(f"{len(pokedex)} Pokémon, {len(moves_json)} attaques, {len(types_json['types'])} types, "
          f"{len(natures_json)} natures, {len(curves)} courbes d'xp")
    return 0


if __name__ == "__main__":
    sys.exit(main())
