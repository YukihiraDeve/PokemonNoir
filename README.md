# Pokémon 3D

Prototype de jeu Pokémon en Three.js : décor 3D stylisé rendu en pixel art, personnages et
Pokémon en sprites, combats dans une clairière en 3D. Région : Unys.

## Lancer

```bash
npm install
npm run dev
```

- `/` : la route. La partie est sauvegardée automatiquement dans le navigateur.
- `/?new` : nouvelle partie (efface la sauvegarde).
- `/?scene=battle&enemy=506&level=4` : combat sauvage direct (numéro du Pokédex national).
- `/?trainer=NPC_Youngster` : combat de dresseur direct (noms dans `src/game/trainers.js`).

## Jouer

| Touche | Action |
|---|---|
| ZQSD ou flèches | Marcher (Maj pour courir) |
| Espace ou Entrée | Parler, faire défiler les dialogues |
| Échap ou X | Menu : équipe (changer le Pokémon de tête, soigner) et sac |

- **Renouet**, le village de départ au bord de la mer : labo du Professeur et son éolienne,
  trois maisons, digue. Reproduction de Pokémon Noir et Blanc (captures dans `docs/reference/`).
- **Route 1**, au nord de Renouet, tracée case par case d'après la carte du jeu : chemin de
  sable, herbes hautes, champs de fleurs, étang en contrebas avec son escalier, clôtures.
- **Arabelle**, la ville au bout de la Route 1, reproduite de Noir et Blanc sur trois niveaux :
  - rue principale avec trois immeubles de briques et un jardin à bancs ;
  - plateau de la maison au toit bleu, relié à la rue par un grand escalier ;
  - place en contrebas avec son escalier ;
  - l'estrade, le bâtiment au toit vert et le Centre Pokémon.

  On entre au Centre en avançant vers sa porte (fondu au noir), on ressort en marchant sur le
  tapis d'entrée.
- **Herbes hautes** : rencontres aléatoires avec 11 Pokémon d'Unys.
- **Capture** : SAC → Poké Ball pendant un combat sauvage. Plus le Pokémon est affaibli,
  plus la capture est probable. Il rejoint l'équipe (6 maximum), sinon le PC.
- **Équipe** : POKéMON pendant un combat pour changer de Pokémon ; remplacement obligatoire
  après un K.O. Le Pokémon de tête suit le joueur sur la route.
- **Dresseurs** : 4 dresseurs sur la route. S'ils vous voient (dans leur ligne de vue), ils
  s'approchent et vous défient. Impossible de fuir ou de capturer leurs Pokémon. Une victoire
  rapporte de l'argent et de l'expérience bonus.
- **Centre Pokémon** : parler à l'infirmière derrière le comptoir pour des soins gratuits.
  Si le sac n'a plus de Poké Ball et qu'il reste moins de 200 ₽, elle en offre 5. Après une
  première visite, une défaite ramène devant son comptoir (sinon devant la maison, à Renouet).
- **Boutique** : au comptoir de droite du Centre Pokémon, comme dans Noir et Blanc. Poké Ball, Super Ball, Hyper Ball,
  Potion, Super Potion, Hyper Potion, payées avec l'argent gagné contre les dresseurs.
  10 Poké Balls achetées d'un coup = une Honor Ball offerte.

## Organisation

| Dossier | Rôle |
|---|---|
| `src/engine/` | Rendu pixelisé (`pixelPass.js`), sprites, lumière, particules, sons, chargement |
| `src/game/pokemon.js` | Règles : stats, dégâts, types, modifications de stats, expérience |
| `src/game/items.js` | Objets (Balls, Potions), stock de la boutique, formule de capture |
| `src/game/state.js` | Partie en cours : équipe, PC, sac, argent, dresseurs battus, sauvegarde |
| `src/game/trainers.js` | PNJ : dresseurs (équipes, récompenses, dialogues), habitants, infirmière, vendeur |
| `src/game/maps.js` | Cartes du monde (route, intérieurs) : fichier, grille de cases, extérieur ou intérieur, nom affiché |
| `src/scenes/` | `overworld.js` (cartes, déplacements, PNJ, portes, rencontres) et `battle.js` (combat) |
| `src/ui/` | Interface de combat, boîte de dialogue, menu, boutique ; styles dans `src/style.css` |
| `public/assets/`, `public/data/` | Assets et données, voir [ASSETS.md](ASSETS.md) |
| `tools/` | Scripts Python de téléchargement et de préparation des assets |
| `tools/maps/` | Grilles de cases de Renouet et de la Route 1 (`route-1.txt`) et d'Arabelle (`arabelle*.txt`), relevées sur les captures |
| `tools/blender/build_scenes.py` | Construit les scènes dans Blender et les exporte en GLB |
| `blender/scenes.blend` | Fichier Blender des scènes (Library, Battle_Forest, Route_01 avec Renouet et Arabelle, Interior_Center) |

## Le rendu

Style « HD-2D » : décor 3D moderne, personnages et Pokémon en pixel art.

- La scène est rendue à environ 450 lignes (pixels de 2×2 en 1080p) avec MSAA, puis agrandie
  sans lissage : la 3D reste nette, les sprites gardent leurs pixels. Pour un rendu plus
  rétro, baisser `TARGET_LINES` dans `src/main.js` (240 = très pixelisé).
- Flou de profondeur : net autour des personnages, premier plan et lointain adoucis
  (`focus` dans chaque scène). Liseré sombre sur les silhouettes nettes.
- Bloom léger, étalonnage (saturation, contraste, teinte chaude) et vignette
  (`src/engine/gradePass.js`).
- Soleil chaud aux ombres légèrement adoucies, ciel HDR, brouillard de distance.
- Feuillages et herbes qui ondulent au vent (`WIND` dans `src/engine/world.js`). Les plantes
  basses (buissons, fougères, fleurs) se couchent en s'écartant du joueur et de son Pokémon
  (`grassPushers`, même fichier).
- Herbes hautes réalistes (`src/engine/grass.js`) : brins effilés générés par le GPU sur les
  cases « H » de la grille, dégradé de la racine à la pointe, vent, lisière fondue ; ils
  se couchent nettement au passage du joueur et de son Pokémon. Réglages : `TALL_GRASS` dans
  `src/scenes/overworld.js`. Fleurs pixel art plantées de la même façon sur les cases de fleurs.
- Eau en pixel art qui dérive lentement, reflets ondulés, liseré d'écume le long des berges.
- Chemins de sable et dalles d'Arabelle peints sur l'herbe, aux bords arrondis et irréguliers
  (`src/engine/paths.js`).
- Maisons en pièces peintes à la main avec normal maps (tuiles, bois, briques, pierre).
- Effets de pas discrets selon le sol (`src/engine/stepFx.js`) : un brin ou une feuille dans les
  herbes hautes avec un froissement, un brin de temps en temps sur l'herbe rase, un peu de
  poussière sur la terre, et un bruit de pas différent sur l'herbe, la terre, les pavés et le
  carrelage.
- Les sprites font face à la caméra, projettent leur ombre et s'assombrissent à l'ombre des arbres.
  Leur profondeur est celle d'un panneau vertical dressé à leurs pieds (`src/engine/sprites.js`) :
  un personnage contre un mur passe devant lui au lieu de s'y enfoncer, et reste caché par ce qui
  est devant lui.

## Modifier les scènes

Les scènes sont générées par script (positions aléatoires mais graine fixe). Dans Blender,
onglet Scripting :

```python
p = "/chemin/vers/Pokemon/tools/blender/build_scenes.py"
exec(compile(open(p).read(), p, "exec"), {"__file__": p})
```

Le script reconstruit `Battle_Forest`, `Route_01` et `Interior_Center` à
partir des modèles de la scène `Library`, puis réexporte `public/assets/scenes/*.glb`. Pour retoucher à la main, modifier
`blender/scenes.blend` puis exporter chaque scène en glTF binaire (« Active scene »,
« Custom properties » cochés).

Repères lus par le jeu (objets vides). Leur nom est aussi rangé dans la propriété `marker`,
car Blender renomme les doublons d'une scène à l'autre (« Bounds.001 ») :

| Repère | Rôle |
|---|---|
| `Spawn_PlayerPokemon`, `Spawn_EnemyPokemon`, `Camera_Battle` | Placement du combat |
| `Spawn_*` | Points d'arrivée : départ de la partie, entrée d'un bâtiment, sortie, comptoir du Centre |
| `NPC_*` | PNJ : propriétés `sprite`, `facing`, `sight` (portée de vue des dresseurs) |
| `Door_*` | Porte vers une autre carte : `target` (carte de `src/game/maps.js`), `spawn` (repère d'arrivée), `dir` (sens de marche pour la franchir), `arrive` (orientation à l'arrivée) |
| `Sign_*` | Panneau : propriété `text` |
| `Area_*` | Zone nommée : propriété `label`, affichée en bandeau en y entrant |
| `Bounds` | Limites de la carte |
| `Turbine_Rotor` | Rotor de l'éolienne du labo, que le jeu fait tourner |
| `Glow_*` (objets) | Lumière au sol, ajoutée en mode additif, sans ombre |

Obstacles : propriété `collider` (rayon en mètres) pour les objets ronds, `solid` pour les
bâtiments (boîte englobante). Un nouveau PNJ = un repère `NPC_Nom` dans Blender + une entrée
`NPC_Nom` dans `src/game/trainers.js`. Une nouvelle carte = une scène Blender exportée en GLB,
une entrée dans `src/game/maps.js` et des portes `Door_*` qui y mènent.

### Renouet, la Route 1 et Arabelle : la grille de cases

La carte est décrite case par case (une case du jeu Noir et Blanc = 1,25 m) :
`tools/maps/route-1.txt`, du nord (haut de la Route 1) au sud (la mer sous Renouet), et au-dessus
`tools/maps/arabelle.txt` (lignes négatives dans `build_scenes.py`).

| Lettre | Case | Lettre | Case |
|---|---|---|---|
| `T` | Forêt (infranchissable) | `W` | Eau (infranchissable) |
| `.` | Herbe | `C` | Falaise ou digue (infranchissable) |
| `S` | Sable (chemin) | `l` | Herbe en contrebas, au bord de l'étang |
| `H` | Herbes hautes (rencontres) | `R` | Escalier en bois |
| `F` / `f` | Fleurs roses (champ / éparses) | `B` | Bâtiment (posé à part dans Blender) |
| `w` | Fleurs blanches | `P` | Dalles claires (Arabelle) |
| `K` | Muret ou rambarde en bord de niveau (infranchissable) | `E` | Escalier de pierre (Arabelle) |
| `X` | Sol fermé : sous un escalier, derrière le Centre | | |

`tools/maps/trace.py` décalque une capture (16 px par case) en lettres ; `tools/maps/build_grid.py`
assemble la route et le village, nettoie le décalque et applique les retouches à la main.
`tools/maps/build_arabelle.py` peint Arabelle par rectangles relevés sur sa capture (37 px par
case) et écrit aussi `arabelle-levels.txt`, le niveau de chaque case :

- `0` rue principale ;
- `U` plateau (+2,5 m) ;
- `D` place en contrebas (−3 m) ;
- `p` plateau de l'estrade (+35 cm) ;
- `r` rampe : escaliers (`TOWN_RAMPS`) et talus boisé de l'ouest (`TALUS`), qui descend vers le
  sud et vers l'est jusqu'à la place en contrebas.

Entre deux cases de niveaux différents, `build_scenes.py` dresse un mur vertical. Il pose aussi
des rambardes sur les cases `K` qui dominent le vide.
`build_scenes.py` lit la grille pour le relief, le sol, la forêt, l'eau et l'écume, et l'exporte
dans `public/assets/scenes/route-01.json` (hauteur de chaque case : un nombre si elle est plate,
sinon ses quatre coins). Le jeu s'en sert pour les collisions, la hauteur du sol, les herbes
hautes, les fleurs et le bruit des pas (`src/engine/tiles.js`).

Les chemins ne sont pas des polygones : le jeu peint le sable sur l'herbe dans le shader du sol
(`src/engine/paths.js`) à partir d'un masque flou des cases « S ». Les angles deviennent des
courbes, le bord ondule et l'herbe mord sur le sable, comme dans les jeux Noir et Blanc. Les
dalles d'Arabelle sont peintes de la même façon (masque des cases P, B, K, X, E) : l'herbe s'y
arrête en festons serrés sur une bande de terre beige, au lieu d'un carré net.

### Les bâtiments d'Arabelle

`build_arabelle` (`build_scenes.py`) assemble la ville :

- immeubles (`apartment`) : briques sombres, bandeaux de bois, fenêtres et porte du kit,
  auvent rayé, toit-terrasse et acrotère ardoise ;
- maison bleue du plateau (`cross_house`) : grand toit et petit pignon en avant au-dessus de
  la porte ;
- bâtiment au toit vert (`gate_building`) ;
- estrade (`stage`), sur laquelle on peut monter (cases de niveau `p`, 35 cm) ;
- bancs et rambardes ;
- escaliers de pierre (`stair_steps`) : girons, contremarches, limons pleins sur les côtés et
  rampe côté vide ;
- bordures de pierre aux angles arrondis autour du jardin et de la pelouse du plateau (`curb`).

La route 2 n'existe pas encore : le panneau près du bâtiment vert l'indique.

### Le Centre Pokémon d'Arabelle

`pokemon_center` (`build_scenes.py`) reproduit le modèle de Noir et Blanc :

- bloc central à angles coupés sur deux niveaux, ailes basses à l'est et à l'ouest ;
- vitrage du rez-de-chaussée en trois rangées de carreaux, liseré jaune, blanc, bleu et marine ;
- jupe rouge en pente, puis vitrage de l'étage traversé d'une bande claire, avec l'emblème
  Poké Ball ;
- toit rouge biseauté, surmonté d'une voûte à pans ouverte en façade ;
- entrée en demi-octogone : intérieur sombre, poteaux gris, auvent rouge, arche blanche à
  facettes et socle blanc.

Les volumes sont des contours décalés et extrudés, regroupés en un objet par matériau
(`Builder`). Le bâtiment est construit aux proportions du modèle, puis réduit (`scale`, 68 %)
autour du milieu de sa façade pour rester à l'échelle des maisons et des personnages. Vitrages et emblème sont en pixel art (`center-*.png`, `tools/generate_textures.py`).

Les vitrages sont éclairés de l'intérieur : une carte d'émission (`center-glass-*-glow.png`)
allume les carreaux, pas les montants. Au fond du sas, on voit les portes vitrées du hall
allumées. La lumière retombe sur les pavés : des plans `Glow_*` (bande devant chaque pan,
flaque devant l'entrée) sont ajoutés en mode additif par le jeu (`WINDOW_LIGHT` dans
`src/engine/world.js` règle leur teinte et leur intensité).

### Les maisons de Renouet

Elles sont construites par `bw_house` et `bw_lab` (`build_scenes.py`) avec les pièces et
textures peintes du [Medieval Village MegaKit](https://quaternius.com/packs/medievalvillagemegakit.html)
(Quaternius, même auteur que les arbres), copiées de la bibliothèque `3DLib` par
`python3 tools/import_village_kit.py` (textures réduites à 512 px, variantes tuiles bleues et
bois clair) :

- un noyau sombre et un bardage à clins modélisé planche par planche, percé de vraies
  ouvertures (`wall_skin`) ; crépi lisse pour le labo ;
- toits en tuiles rondes du kit (bleues pour les maisons, orange pour le labo), étirés à la
  taille du bâtiment, pignon tourné vers le sud ;
- fenêtres, portes, lucarne, cheminée et chaînes d'angle du kit ; angles en briques,
  soubassement de pierre, auvent de tuiles, jardinière fleurie, châssis de toit.
