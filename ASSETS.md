# Assets du jeu

Direction artistique (voir les captures de référence) : décor 3D stylisé et luxuriant
(arbres, fougères, buissons, rochers), rendu pixelisé, avec ombres nettes et lumière
chaude. Personnages et Pokémon en sprites pixel art posés en billboard dans la 3D, sur
la carte comme en combat. Région de départ : Unys (#494 → #649).

Une bonne partie du look vient du rendu, pas des fichiers : scène rendue en basse
résolution puis agrandie sans lissage (`NearestFilter`), éclairage toon, ombres nettes,
bloom léger et profondeur de champ.

Tout ce qui est dans `public/` est servi tel quel par Vite (`/assets/...`, `/data/...`).

## Régénérer

```bash
npm run assets
```

Lance les scripts de `tools/` : téléchargement, planches de sprites, textures de sol,
données. Les fichiers déjà présents sont ignorés. Pour d'autres générations (sprites NB
disponibles jusqu'au #649) :
`python3 -I tools/download_assets.py --from 1 --to 649`, puis
`python3 -I tools/build_spritesheets.py` et `python3 -I tools/build_data.py --from 1 --to 649`.

## Contenu

### Décor

| Dossier | Contenu | Source | Licence |
|---|---|---|---|
| `assets/environment/quaternius_stylized-nature-megakit/glTF` | 68 modèles : arbres (feuillus, pins, tordus, morts), buissons, fougères, fleurs, herbes hautes et basses, trèfles, champignons, rochers, galets, pierres de chemin, pétales | [Quaternius, Stylized Nature MegaKit](https://quaternius.com/packs/stylizednaturemegakit.html) (version gratuite) | CC0 |
| `assets/environment/textures` | Herbe, terre, sable, crépi, planches, falaise, pierres de la digue, haie, eau et écume en pixel art 128×128 raccordables ; vitrages et emblème du Centre Pokémon ; dalles, murs de soutènement, toits-terrasses et auvents rayés d'Arabelle ; carrelage et emblème Poké Ball de l'intérieur du Centre ; feuillage vert pour les buissons du kit | générées par `tools/generate_textures.py` | CC0 (fait maison) |
| `assets/scenes/battle-forest.glb` | Clairière de combat : couronnes d'arbres, lisière dense, rochers, deux terrains de terre, caméra | composée dans Blender par `tools/blender/build_scenes.py` | CC0 |
| `assets/scenes/route-01.glb` | Renouet (labo, éolienne, maisons, digue, mer), Route 1 (chemin de sable, forêt, étang, escalier, clôtures) et Arabelle (immeubles, maison bleue du plateau, Centre Pokémon, jardin, place en contrebas, estrade, bâtiment vert), repères de jeu | idem | CC0 |
| `assets/scenes/route-01.json` | Grille de cases d'Arabelle, de la Route 1 et de Renouet (collisions, hauteurs, herbes hautes, fleurs) | exportée par `build_scenes.py` depuis `tools/maps/*.txt` | CC0 |
| `assets/scenes/center.glb` | Intérieur du Centre Pokémon (comptoir et machine de soin, PC, coin salon, comptoir de la boutique) | composé dans Blender par `tools/blender/build_scenes.py` | CC0 |
| `assets/environment/quaternius_medieval-village-megakit/glTF` | 13 pièces pour les maisons de Renouet et le labo (toits en tuiles rondes, lucarne, fenêtres, portes, encadrement, chaîne d'angle, cheminée) et leurs textures peintes (512 px) ; variantes générées : tuiles bleues, bois clair, briques sombres | [Quaternius, Medieval Village MegaKit](https://quaternius.com/packs/medievalvillagemegakit.html), copié de la bibliothèque `3DLib` par `tools/import_village_kit.py` | CC0 |
| `assets/environment/kenney_city-kit-suburban` | Jardinière des intérieurs (seul modèle utilisé) | [Kenney](https://kenney.nl/assets/city-kit-suburban) | CC0 |
| `assets/environment/hdri` | Ciel HDR 1k pour l'éclairage et le fond | [Poly Haven](https://polyhaven.com/a/kloofendal_48d_partly_cloudy_puresky) | CC0 |
| `assets/vfx/kenney_particle-pack` | 81 textures de particules (feu, fumée, magie, étincelles) | [Kenney](https://kenney.nl/assets/particle-pack) | CC0 |

Les textures du kit ont été réduites à 1024 px maximum : le rendu pixelisé n'en a pas besoin de plus.

### Personnages et Pokémon

| Dossier | Contenu | Source | Licence |
|---|---|---|---|
| `assets/characters/overworld` + `index.json` | Joueur (Lucas, Aurore : marche + course) et 116 PNJ (montagnard, infirmière, sbires…) | [pret/pokeplatinum](https://github.com/pret/pokeplatinum), remis en grille par `tools/build_spritesheets.py` | © Nintendo / Game Freak |
| `assets/characters/objects` | Poké Ball au sol, arbuste à couper, rocher à briser, rocher Force, rochers mousse/glace | pret/pokeplatinum | © Nintendo / Game Freak |
| `assets/pokemon/gif/{front,back,front-shiny,back-shiny}` | GIF animés Noir & Blanc (156 × 4) | [PokeAPI/sprites](https://github.com/PokeAPI/sprites) | © Nintendo / Game Freak |
| `assets/pokemon/sprites/…` + `index.json` | Les mêmes en planches PNG pour Three.js (combat et Pokémon qui suit le joueur) | généré par `tools/build_spritesheets.py` | idem |
| `assets/pokemon/icons` | Icônes d'équipe 40×30 | PokeAPI/sprites (gen VII) | © Nintendo / Game Freak |
| `assets/pokemon/cries` | Cris (.ogg, version d'origine) | [PokeAPI/cries](https://github.com/PokeAPI/cries) | © Nintendo / Game Freak |
| `assets/trainers` | Sprites de combat des dresseurs (80×80) : personnages NB et classes de la route (Topdresseuse, Scout, Gamin, Fillette…) | [Pokémon Showdown](https://play.pokemonshowdown.com/sprites/trainers/) | © Nintendo / Game Freak |
| `assets/items` | Objets (Poké Balls, potions, baies…) | PokeAPI/sprites | © Nintendo / Game Freak |

Modèles 3D déjà présents dans `Pokemon3D/` (Sketchfab, CC-BY 4.0, crédit obligatoire).
Ils ne collent pas au style des captures (tout y est en sprites) mais restent disponibles :
- Tepig — « Tepig » par [a-random-person](https://sketchfab.com/a-random-person)
- Snivy — « PokkenTournament Snivy » par [akennedy007](https://sketchfab.com/akennedy007)

### Interface, polices et son

| Dossier | Contenu | Source | Licence |
|---|---|---|---|
| `assets/fonts/pixelify-sans` | Police pixel à graisse variable (titres, « FIGHT! ») | [Google Fonts](https://fonts.google.com/specimen/Pixelify+Sans) | OFL 1.1 |
| `assets/fonts/silkscreen` | Police pixel capitales, normal + gras (noms, niveaux, PV) | [Google Fonts](https://fonts.google.com/specimen/Silkscreen) | OFL 1.1 |
| `assets/fonts/jersey-10` | Police pixel condensée (dialogues, menus) | [Google Fonts](https://fonts.google.com/specimen/Jersey+10) | OFL 1.1 |
| `assets/audio/sfx/*` | 286 bruitages (interface, RPG, impacts) | Kenney [Interface](https://kenney.nl/assets/interface-sounds), [RPG](https://kenney.nl/assets/rpg-audio), [Impact](https://kenney.nl/assets/impact-sounds) | CC0 |
| `assets/audio/jingles` | Jingles 8-bit (victoire, niveau…) | [Kenney](https://kenney.nl/assets/music-jingles) | CC0 |
| `assets/audio/music/town-theme.mp3` | Musique de ville | [cynicmusic, OpenGameArt](https://opengameart.org/content/town-theme-rpg) | CC0 |
| `assets/audio/music/battle-theme-a.mp3` | Musique de combat | [cynicmusic, OpenGameArt](https://opengameart.org/content/battle-theme-a) | CC0 |

Toutes les polices affichent les accents français. L'interface de combat (cadres, barres de
PV, boutons FIGHT / BAG / RUN / PKMN) est à dessiner en CSS ou en canvas : aucun pack libre
ne reprend ce style.

### Données

| Fichier | Contenu |
|---|---|
| `data/pokemon.json` | Pokédex : noms FR/EN, types, stats, talents, évolutions, description, apprentissages (N2B2) |
| `data/moves.json` | 439 attaques : type, catégorie, puissance, précision, PP, effets, statuts |
| `data/types.json` | 18 types (Fée inclus) avec nom FR et couleur, table d'efficacité `chart[attaque][défense]` |
| `data/natures.json`, `data/growth-rates.json` | Natures et courbes d'expérience |

Source : [PokeAPI](https://github.com/PokeAPI/pokeapi) via `tools/build_data.py` (données sous BSD-3).

## Formats

**Pokémon** — `assets/pokemon/sprites/index.json` → `index["495"]["front"] = { w, h, cols, durations }`
- `w`, `h` : taille d'une frame ; frame `i` en `x = (i % cols) * w`, `y = floor(i / cols) * h`.
- `durations` : durée de chaque frame en ms (sa longueur donne le nombre de frames).
- Les marges vides sont rognées : le bas de la frame = les pieds du Pokémon.

**Personnages** — `assets/characters/overworld/index.json` → `index["player_m"] = { w, h, cols, rows }`
- Frames 32×32, 4 colonnes : immobile, pas A, immobile, pas B (boucler 0→3 pour marcher).
- `rows` donne le nom de chaque ligne : `walk-down`, `walk-left`, `walk-right`, `walk-up`,
  puis `run-…` pour les joueurs et `extra` pour quelques PNJ (l'infirmière qui salue).

## À savoir

- Les sprites, cris et noms Pokémon sont la propriété de Nintendo / Game Freak / The Pokémon
  Company : usage personnel et non commercial uniquement, pas de diffusion publique monétisée.
- Joueur et PNJ viennent de Platine (Sinnoh) : la 5e génération n'a pas de sprites de
  marche exploitables. Même style que la référence.
- Les cris et bruitages Kenney sont en `.ogg` : OK sur Chrome, Firefox et Safari récent.
