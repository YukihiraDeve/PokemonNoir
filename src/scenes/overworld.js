import * as THREE from 'three';
import { loadGLTF, loadJSON } from '../engine/assets.js';
import { addLighting, prepareLevel, markerRect, inRect, grassPushers } from '../engine/world.js';
import { CharacterSprite, PokemonSprite } from '../engine/sprites.js';
import { animate, wait } from '../engine/tween.js';
import { StepFx } from '../engine/stepFx.js';
import { growGrass, growFlowers, tallGrassFields } from '../engine/grass.js';
import { createTileMap } from '../engine/tiles.js';
import { paintPaths } from '../engine/paths.js';
import { sounds } from '../engine/audio.js';
import { createMon } from '../game/pokemon.js';
import { healParty } from '../game/state.js';
import { MAPS } from '../game/maps.js';
import { NPCS } from '../game/trainers.js';
import { Dialog } from '../ui/dialog.js';
import { GameMenu } from '../ui/menu.js';
import { Shop } from '../ui/shop.js';

const CHARACTER_SCALE = 0.055; // mètres par pixel des sprites du monde (frames 32×32)
const FOLLOWER_SCALE = 0.024;
const OUTDOOR_CAMERA = new THREE.Vector3(0, 13, 11.5);
const INDOOR_CAMERA = new THREE.Vector3(0, 8.5, 7.5);
const WALK_SPEED = 3.6;
const RUN_SPEED = 6.5;
const BODY_RADIUS = 0.35;
const FOLLOW_DISTANCE = 1.1;
const ENCOUNTER_CHANCE_PER_METER = 0.12;
const TALK_DISTANCE = 1.6;
const SIGHT_HALF_WIDTH = 0.8;
const DOOR_DISTANCE = 0.8;
const STEP_LENGTH = { walk: 0.55, run: 0.75 }; // distance entre deux pas (effets et bruits)
const FAR_AWAY = new THREE.Vector3(1e4, 0, 1e4);
// Herbes hautes : brins réalistes poussés sur les cases « H » de la grille.
const TALL_GRASS ={ density: 230, height: [0.55, 0.95], width: [0.04, 0.065], edge: 0.8 };
const DOWN = new THREE.Vector3(0, -1, 0);
// Au Centre, l'infirmière dépanne un dresseur sans Ball ni argent pour en acheter.
const NURSE_BALLS = 5;

// Pokémon sauvages des herbes hautes : [id, niveau min, niveau max, poids].
const WILD = [
  [504, 2, 4, 30], [506, 2, 4, 30], [509, 3, 4, 15], [519, 3, 5, 20], [531, 4, 5, 8],
  [540, 3, 4, 10], [546, 3, 4, 8], [548, 3, 4, 8], [570, 4, 5, 3], [587, 4, 5, 3], [610, 5, 5, 2],
];

function rollWild() {
  let r = Math.random() * WILD.reduce((s, w) => s + w[3], 0);
  const [id, min, max] = WILD.find((w) => (r -= w[3]) < 0) ?? WILD[0];
  return createMon(id, min + Math.floor(Math.random() * (max - min + 1)));
}

const KEYS = {
  ArrowUp: 'up', KeyW: 'up', ArrowDown: 'down', KeyS: 'down',
  ArrowLeft: 'left', KeyA: 'left', ArrowRight: 'right', KeyD: 'right',
};
const FACING = {
  up: new THREE.Vector3(0, 0, -1), down: new THREE.Vector3(0, 0, 1),
  left: new THREE.Vector3(-1, 0, 0), right: new THREE.Vector3(1, 0, 0),
};
const facingTowards = (from, to) => {
  const d = to.clone().sub(from);
  return Math.abs(d.x) > Math.abs(d.z) ? (d.x > 0 ? 'right' : 'left') : (d.z > 0 ? 'down' : 'up');
};

/** Bulle « ! » au-dessus d'un dresseur qui repère le joueur (dessinée en pixel art). */
function exclamationSprite() {
  const canvas = Object.assign(document.createElement('canvas'), { width: 12, height: 14 });
  const g = canvas.getContext('2d');
  g.fillStyle = '#1d1d22';
  g.fillRect(1, 0, 10, 12);
  g.fillRect(0, 1, 12, 10);
  g.fillRect(4, 12, 3, 2);
  g.fillStyle = '#ffffff';
  g.fillRect(2, 1, 8, 10);
  g.fillRect(1, 2, 10, 8);
  g.fillStyle = '#e8463a';
  g.fillRect(5, 2, 2, 5);
  g.fillRect(5, 8, 2, 2);
  const texture = new THREE.CanvasTexture(canvas);
  texture.magFilter = THREE.NearestFilter;
  texture.colorSpace = THREE.SRGBColorSpace;
  const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: texture, depthTest: false }));
  sprite.scale.set(0.6, 0.7, 1);
  sprite.renderOrder = 10;
  sprite.visible = false;
  return sprite;
}

/**
 * Le monde à pied : Renouet, la Route 1 et Arabelle, intérieur du Centre Pokémon (soins et
 * boutique). Une seule carte est chargée à la fois (MAPS) ; les portes mènent de l'une à
 * l'autre avec un fondu au noir. Le joueur marche, son Pokémon de tête le suit, les herbes
 * hautes et les dresseurs déclenchent des combats.
 * Tout ce qui est interactif est un repère posé dans Blender (NPC_*, Door_*, Sign_*, Area_*) ;
 * la grille de cases de la carte (MAPS.grid) donne collisions, relief et herbes hautes.
 */
export async function createOverworld({ hud: container, state, onEncounter, onTrainer, onChange, onNewGame }) {
  const scene = new THREE.Scene();
  const { sun, hemi } = await addLighting(scene, { shadowExtent: 22 });
  // Ambiances : extérieur (ciel HDR, soleil) ou intérieur (fond noir, lumière plus douce).
  const LOOKS = {
    outdoor: { background: scene.background, fog: scene.fog, env: scene.environmentIntensity, sun: sun.intensity, hemi: hemi.intensity },
    indoor: { background: new THREE.Color(0x000000), fog: new THREE.Fog(0x000000, 30, 60), env: 0.2, sun: 2.4, hemi: 1.5 },
  };

  const player = await CharacterSprite.create('player_m', CHARACTER_SCALE);
  scene.add(player);
  const exclamation = exclamationSprite();
  scene.add(exclamation);
  const stepFx = new StepFx(scene);
  const raycaster = new THREE.Raycaster();

  // Le premier Pokémon de l'équipe suit le joueur (sprite de face ou de dos selon la direction).
  const follower = new THREE.Group();
  scene.add(follower);
  let followerFront = null;
  let followerBack = null;
  let followerId = null;
  let trail = [];
  async function refreshFollower() {
    const id = state.party[0].species.id;
    if (id === followerId) return;
    followerId = id;
    const [front, back] = await Promise.all([
      PokemonSprite.create(id, 'front', FOLLOWER_SCALE),
      PokemonSprite.create(id, 'back', FOLLOWER_SCALE),
    ]);
    for (const old of [followerFront, followerBack]) {
      if (!old) continue;
      follower.remove(old);
      old.dispose();
    }
    followerFront = front;
    followerBack = back;
    back.visible = false;
    follower.add(front, back);
  }
  await refreshFollower();

  const camera = new THREE.PerspectiveCamera(38, 16 / 9, 0.1, 300);
  const cameraTarget = new THREE.Vector3();
  const cameraOffset = OUTDOOR_CAMERA.clone();
  // Net autour du joueur ; feuillages au premier plan et lointains flous (effet maquette).
  const focus = { distance: cameraOffset.length(), range: 6 };

  const overlay = Object.assign(document.createElement('div'), {
    className: 'ow-hud',
    innerHTML: `<div class="ow-banner"></div>
      <div class="ow-help">ZQSD/flèches : marcher · Maj : courir · Espace : parler · Échap : menu</div>
      <div class="ow-fade"></div>`,
  });
  container.append(overlay);
  const banner = overlay.querySelector('.ow-banner');
  const fadeLayer = overlay.querySelector('.ow-fade');
  const fade = (to, ms) => {
    const from = parseFloat(fadeLayer.style.opacity || 0);
    return animate(ms, (t) => { fadeLayer.style.opacity = from + (to - from) * t; });
  };
  function showBanner(label) {
    // Relance l'animation du bandeau avec le nom du lieu.
    banner.textContent = label;
    banner.style.animation = 'none';
    void banner.offsetWidth;
    banner.style.animation = '';
  }

  const dialog = new Dialog(container);
  const shop = new Shop(container, state);
  shop.onBuy = onChange;
  const menu = new GameMenu(container, state, {
    onChange: () => {
      onChange();
      refreshFollower();
    },
    onNewGame,
  });

  const held = new Set();
  let paused = false;
  let busy = false; // dialogue, transition ou cinématique en cours
  let walkedInGrass = 0;
  let stepDistance = 0;
  let stepCount = 0;
  let followerDistance = 0;
  let currentArea = null;

  // ------------------------------------------------------------ cartes

  let map = null;
  const grassCache = new Map(); // herbes hautes générées une fois par carte
  const markerPosition = (name) => map.markers.get(name).getWorldPosition(new THREE.Vector3());

  /** Charge une carte et y place le joueur sur le repère `spawn`, tourné vers `facing`. */
  async function loadMap(id, spawn, facing = 'up') {
    const def = MAPS[id];
    const level = (await loadGLTF(def.file)).scene;
    prepareLevel(level);
    level.updateMatrixWorld(true);

    const next = {
      id, def, level, markers: new Map(), colliders: [], solids: [], npcs: [], doors: [], signs: [], areas: [], surfaces: [],
    };
    const npcNodes = [];
    const at = (obj) => obj.getWorldPosition(new THREE.Vector3());
    level.traverse((obj) => {
      const data = obj.userData;
      if (data.collider) next.colliders.push({ ...at(obj), r: data.collider });
      if (data.solid) next.solids.push(new THREE.Box3().setFromObject(obj));
      if (obj.isMesh && /^(Ground|Path|Pad|Floor)/.test(obj.name)) next.surfaces.push(obj);
      const name = data.marker;
      if (!name) return;
      next.markers.set(name, obj);
      if (name.startsWith('NPC_')) npcNodes.push(obj);
      if (name.startsWith('Door_')) next.doors.push({ position: at(obj), ...data });
      if (name.startsWith('Sign_')) next.signs.push({ position: at(obj), text: data.text });
      if (name.startsWith('Area_')) next.areas.push({ rect: markerRect(obj), label: data.label });
    });
    next.bounds = markerRect(next.markers.get('Bounds'));
    next.tiles = def.grid ? createTileMap(await loadJSON(def.grid)) : null;
    if (next.tiles && !level.userData.pathsPainted) {
      level.userData.pathsPainted = true;
      await paintPaths(level, next.tiles, next.tiles.town);
    }
    next.rotor = level.getObjectByName('Turbine_Rotor') ?? null; // éolienne du labo
    next.npcs = await Promise.all(npcNodes.map(async (node) => {
      const sprite = await CharacterSprite.create(node.userData.sprite, CHARACTER_SCALE);
      node.getWorldPosition(sprite.position);
      if (next.tiles) sprite.position.y = next.tiles.heightAt(sprite.position.x, sprite.position.z);
      sprite.facing = node.userData.facing ?? 'down';
      const collider = { x: sprite.position.x, z: sprite.position.z, r: 0.45 };
      next.colliders.push(collider);
      const npcId = node.userData.marker;
      return { id: npcId, sprite, collider, sight: node.userData.sight ?? 0, data: NPCS[npcId] ?? { kind: 'talk', lines: ['…'] } };
    }));

    if (next.tiles && !grassCache.has(id)) {
      const { tiles } = next;
      const plants = new THREE.Group();
      plants.add(growGrass(level, { fields: tallGrassFields(tiles, TALL_GRASS), heightAt: tiles.heightAt }));
      plants.add(growFlowers(tiles, { heightAt: tiles.heightAt }));
      grassCache.set(id, plants);
    }
    next.grass = grassCache.get(id) ?? null;

    if (map) {
      if (map.grass) scene.remove(map.grass);
      scene.remove(map.level);
      for (const npc of map.npcs) {
        scene.remove(npc.sprite);
        npc.sprite.dispose();
      }
    }
    map = next;
    scene.add(level);
    if (map.grass) scene.add(map.grass);
    for (const npc of map.npcs) scene.add(npc.sprite);

    const look = LOOKS[def.outdoor ? 'outdoor' : 'indoor'];
    scene.background = look.background;
    scene.fog = look.fog;
    scene.environmentIntensity = look.env;
    sun.intensity = look.sun;
    hemi.intensity = look.hemi;
    cameraOffset.copy(def.outdoor ? OUTDOOR_CAMERA : INDOOR_CAMERA);
    focus.distance = cameraOffset.length();

    player.position.copy(onGround(markerPosition(spawn)));
    player.facing = facing;
    // Juste derrière le joueur : plus loin, il risquerait d'apparaître dans le mur derrière la porte.
    follower.position.copy(player.position).addScaledVector(FACING[facing], -0.3);
    onGround(follower.position);
    trail = [follower.position.clone(), player.position.clone()];
    cameraTarget.copy(player.position);
    currentArea = null;
    walkedInGrass = 0;
    stepFx.clear();
    if (def.label) showBanner(def.label);
  }

  /** Pose un point sur le relief de la grille (sans grille, le sol est plat et on n'y touche pas). */
  function onGround(position) {
    if (map.tiles) position.y = map.tiles.heightAt(position.x, position.z);
    return position;
  }

  const inTallGrass = (position) => map.tiles?.tileAt(position.x, position.z) === 'H';

  // Nature du sol selon la case : sable, escalier en bois, falaise, dalles et escaliers de pierre
  // d'Arabelle ; le reste est de l'herbe.
  const TILE_SURFACES = { H: 'tallgrass', S: 'dirt', R: 'floor', C: 'stone', P: 'stone', E: 'stone', K: 'stone', X: 'stone', B: 'stone' };

  /** Nature du sol sous un point : herbes hautes, herbe, terre, pavés ou carrelage. */
  function surfaceAt(position) {
    const tile = map.tiles?.tileAt(position.x, position.z);
    if (tile) return TILE_SURFACES[tile] ?? 'grass';
    // Hors de la grille (intérieurs) : d'après le maillage sous les pieds.
    raycaster.set(position.clone().setY(position.y + 3), DOWN);
    const name = raycaster.intersectObjects(map.surfaces, false)[0]?.object.name ?? '';
    if (name.startsWith('Path_Plaza')) return 'stone';
    if (name.startsWith('Path') || name.startsWith('Pad')) return 'dirt';
    if (name.startsWith('Floor')) return 'floor';
    return 'grass';
  }

  /** Passage d'une porte : fondu au noir, changement de carte, retour de l'image. */
  async function travel(door) {
    sounds.door();
    await fade(1, 220);
    await loadMap(door.target, door.spawn, door.arrive);
    await fade(0, 320);
  }

  function updateArea() {
    const area = map.areas.find((a) => inRect(a.rect, player.position.x, player.position.z));
    if (!area || area === currentArea) return;
    currentArea = area;
    showBanner(area.label);
  }

  // ------------------------------------------------------------ PNJ

  async function talk(npc) {
    const { data } = npc;
    npc.sprite.facing = facingTowards(npc.sprite.position, player.position);
    if (data.kind === 'nurse') await visitCenter(data.name);
    else if (data.kind === 'clerk') await visitShop(data.name);
    else if (data.kind === 'talk') await dialog.say(data.lines, data.name);
    else if (data.kind === 'trainer' && !state.defeated.includes(npc.id)) await challenge(npc, false);
    else if (data.kind === 'trainer') await dialog.say(data.after, `${data.title} ${data.name}`);
  }

  /** Un dresseur repère le joueur (ou se fait aborder) : « ! », il approche, parle, combat. */
  async function challenge(npc, spotted) {
    const { sprite, data } = npc;
    held.clear();
    player.moving = false;
    if (spotted) {
      exclamation.position.copy(sprite.position).add(new THREE.Vector3(0, sprite.size.y + 0.45, 0));
      exclamation.visible = true;
      sounds.select();
      await wait(800);
      exclamation.visible = false;
      // Il marche vers le joueur jusqu'à se trouver juste devant lui.
      const dir = FACING[sprite.facing];
      const along = player.position.clone().sub(sprite.position).dot(dir);
      const start = sprite.position.clone();
      const end = onGround(start.clone().addScaledVector(dir, Math.max(0, along - 1.0)));
      sprite.moving = true;
      await animate(Math.max(1, start.distanceTo(end)) * 260, (t) => sprite.position.lerpVectors(start, end, t));
      sprite.moving = false;
      npc.collider.x = sprite.position.x;
      npc.collider.z = sprite.position.z;
      player.facing = facingTowards(player.position, sprite.position);
    }
    await dialog.say(data.intro, `${data.title} ${data.name}`);
    onTrainer(npc.id, data);
  }

  function spottedBy() {
    for (const npc of map.npcs) {
      if (npc.data.kind !== 'trainer' || !npc.sight || state.defeated.includes(npc.id)) continue;
      const d = player.position.clone().sub(npc.sprite.position).setY(0);
      const dir = FACING[npc.sprite.facing];
      const along = d.dot(dir);
      const lateral = d.clone().addScaledVector(dir, -along).length();
      if (along > 0.3 && along < npc.sight && lateral < SIGHT_HALF_WIDTH) return npc;
    }
    return null;
  }

  // Les PNJ derrière un comptoir (infirmière, vendeur) se parlent par-dessus.
  function npcInFront() {
    const ahead = player.position.clone().addScaledVector(FACING[player.facing], 0.9);
    return map.npcs.find((npc) => npc.sprite.position.distanceTo(ahead) < TALK_DISTANCE * 0.7)
      ?? map.npcs.find((npc) => npc.sprite.position.distanceTo(player.position) < TALK_DISTANCE * 0.8);
  }

  function signInFront() {
    const ahead = player.position.clone().addScaledVector(FACING[player.facing], 0.9);
    return map.signs.find((sign) => sign.position.distanceTo(ahead) < TALK_DISTANCE * 0.7);
  }

  /** Infirmière : soins gratuits ; ce Centre devient le point de retour après une défaite. */
  async function visitCenter(nurse) {
    await dialog.say(['Bienvenue au Centre Pokémon !', 'Nous allons soigner vos Pokémon. Un instant…'], nurse);
    healParty(state);
    state.respawn = 'center';
    sounds.heal();
    await fade(0.35, 200);
    await fade(0, 400);
    const lines = ['Vos Pokémon sont en pleine forme !'];
    if (!state.bag['poke-ball'] && state.money < 200) {
      state.bag['poke-ball'] = NURSE_BALLS;
      lines.push(`Plus de Poké Balls ni d'argent ? Tenez, en voici ${NURSE_BALLS} !`);
    }
    lines.push('À bientôt !');
    await dialog.say(lines, nurse);
    onChange();
  }

  async function visitShop(clerk) {
    await dialog.say('Bienvenue au comptoir de la boutique ! Que puis-je faire pour vous ?', clerk);
    await shop.show();
    await dialog.say('Merci, à bientôt !', clerk);
    onChange();
  }

  async function runBusy(task) {
    busy = true;
    held.clear();
    player.moving = false;
    try {
      await task();
    } finally {
      busy = false;
    }
  }

  // ------------------------------------------------------------ commandes

  const onKey = (e) => {
    if (paused) return;
    if (e.type === 'keydown' && (e.code === 'Escape' || e.code === 'KeyX')) {
      if (!busy) menu.toggle();
      return;
    }
    if (busy || menu.open || shop.open) return;
    if (KEYS[e.code]) {
      e.preventDefault();
      if (e.type === 'keydown') held.add(KEYS[e.code]);
      else held.delete(KEYS[e.code]);
    }
    if (e.code === 'ShiftLeft' || e.code === 'ShiftRight') player.running = e.type === 'keydown';
    if (e.type === 'keydown' && (e.code === 'Space' || e.code === 'Enter')) {
      e.preventDefault();
      const npc = npcInFront();
      const sign = npc ? null : signInFront();
      if (npc) runBusy(() => talk(npc));
      else if (sign) runBusy(() => dialog.say(sign.text));
    }
  };
  window.addEventListener('keydown', onKey);
  window.addEventListener('keyup', onKey);

  /** Repousse un point hors d'un rectangle (x, z) élargi du rayon du corps. */
  function pushOutOf(pos, box) {
    // Point du rectangle le plus proche du joueur ; on le repousse s'il est trop près.
    const cx = THREE.MathUtils.clamp(pos.x, box.minX, box.maxX);
    const cz = THREE.MathUtils.clamp(pos.z, box.minZ, box.maxZ);
    const dx = pos.x - cx;
    const dz = pos.z - cz;
    const d2 = dx * dx + dz * dz;
    if (d2 >= BODY_RADIUS * BODY_RADIUS) return;
    if (d2 > 1e-8) {
      const d = Math.sqrt(d2);
      pos.x = cx + (dx / d) * BODY_RADIUS;
      pos.z = cz + (dz / d) * BODY_RADIUS;
    } else {
      // Déjà dedans : sortie par le côté le plus proche.
      const exits = [[box.minX - BODY_RADIUS - pos.x, 0], [box.maxX + BODY_RADIUS - pos.x, 0],
        [0, box.minZ - BODY_RADIUS - pos.z], [0, box.maxZ + BODY_RADIUS - pos.z]];
      const [ex, ez] = exits.reduce((a, b) => (Math.hypot(...a) < Math.hypot(...b) ? a : b));
      pos.x += ex;
      pos.z += ez;
    }
  }

  function collide(pos) {
    for (const c of map.colliders) {
      const dx = pos.x - c.x;
      const dz = pos.z - c.z;
      const min = c.r + BODY_RADIUS;
      const d2 = dx * dx + dz * dz;
      if (d2 < min * min && d2 > 1e-6) {
        const d = Math.sqrt(d2);
        pos.x = c.x + (dx / d) * min;
        pos.z = c.z + (dz / d) * min;
      }
    }
    for (const box of map.solids) pushOutOf(pos, { minX: box.min.x, maxX: box.max.x, minZ: box.min.z, maxZ: box.max.z });
    if (map.tiles) {
      // Cases infranchissables autour du joueur : forêt, eau, falaises, bâtiments.
      const [c0, r0] = map.tiles.cell(pos.x, pos.z);
      for (let r = r0 - 1; r <= r0 + 1; r++) {
        for (let c = c0 - 1; c <= c0 + 1; c++) {
          if (map.tiles.blocked(c, r)) pushOutOf(pos, map.tiles.box(c, r));
        }
      }
    }
    pos.x = THREE.MathUtils.clamp(pos.x, map.bounds.minX, map.bounds.maxX);
    pos.z = THREE.MathUtils.clamp(pos.z, map.bounds.minZ, map.bounds.maxZ);
  }

  function updateFollower(dt) {
    if (!followerFront) return;
    // Point du chemin parcouru situé à FOLLOW_DISTANCE derrière le joueur.
    let remaining = FOLLOW_DISTANCE;
    let target = trail[0];
    for (let i = trail.length - 1; i > 0; i--) {
      const seg = trail[i].distanceTo(trail[i - 1]);
      if (seg >= remaining) {
        target = trail[i].clone().lerp(trail[i - 1], remaining / seg);
        trail.splice(0, i - 1);
        break;
      }
      remaining -= seg;
    }
    const move = target.clone().sub(follower.position);
    if (move.lengthSq() > 1e-5) {
      const showBack = move.z < -Math.abs(move.x) * 0.5;
      followerBack.visible = showBack;
      followerFront.visible = !showBack;
      followerFront.setFlipped(move.x > Math.abs(move.z));
    }
    const before = follower.position.clone();
    onGround(follower.position.lerp(target, Math.min(1, dt * 12)));
    // Le Pokémon qui suit froisse lui aussi les herbes hautes, en plus discret.
    followerDistance += follower.position.distanceTo(before);
    if (followerDistance > STEP_LENGTH.walk) {
      followerDistance = 0;
      if (inTallGrass(follower.position)) {
        stepFx.step(follower.position, 'tallgrass', { strength: 0.5 });
      }
    }
  }

  function step(dt) {
    const dir = new THREE.Vector3(
      (held.has('right') ? 1 : 0) - (held.has('left') ? 1 : 0), 0,
      (held.has('down') ? 1 : 0) - (held.has('up') ? 1 : 0));
    player.moving = dir.lengthSq() > 0;
    if (!player.moving) return;
    dir.normalize();
    player.facing = Math.abs(dir.x) > Math.abs(dir.z) ? (dir.x > 0 ? 'right' : 'left') : (dir.z > 0 ? 'down' : 'up');
    const before = player.position.clone();
    player.position.addScaledVector(dir, (player.running ? RUN_SPEED : WALK_SPEED) * dt);
    collide(player.position);
    onGround(player.position);
    const moved = player.position.distanceTo(before);
    if (moved > 0.001) trail.push(player.position.clone());

    stepDistance += moved;
    if (stepDistance > STEP_LENGTH[player.running ? 'run' : 'walk']) {
      stepDistance = 0;
      const surface = surfaceAt(player.position);
      stepFx.step(player.position, surface, { running: player.running });
      if (surface === 'tallgrass') sounds.rustle();
      if (stepCount++ % 2 === 0) sounds.step(surface);
    }

    const trainer = spottedBy();
    if (trainer) {
      runBusy(() => challenge(trainer, true));
      return;
    }
    // Une porte s'emprunte en marchant dans sa direction (vers le haut pour entrer, le bas pour sortir).
    const door = map.doors.find((d) => player.facing === d.dir
      && d.position.distanceTo(player.position.clone().setY(d.position.y)) < DOOR_DISTANCE);
    if (door) {
      runBusy(() => travel(door));
      return;
    }
    if (inTallGrass(player.position)) {
      walkedInGrass += moved;
      if (walkedInGrass > 1) {
        walkedInGrass -= 1;
        if (Math.random() < ENCOUNTER_CHANCE_PER_METER) {
          held.clear();
          player.moving = false;
          onEncounter(rollWild());
        }
      }
    }
  }

  await loadMap('route-01', 'Spawn_Player', 'up');

  return {
    scene,
    camera,
    focus,
    player,
    update(dt) {
      if (!paused && !busy && !menu.open && !shop.open) step(dt);
      updateArea();
      updateFollower(dt);
      if (!paused) {
        grassPushers.value[0].copy(player.position);
        grassPushers.value[1].copy(follower.position);
      }
      stepFx.update(dt);
      if (map.rotor) map.rotor.rotation.z += dt * 1.1;
      cameraTarget.lerp(player.position, Math.min(1, dt * 6));
      camera.position.copy(cameraTarget).add(cameraOffset);
      camera.lookAt(cameraTarget.x, cameraTarget.y + 0.8, cameraTarget.z);
      // Soleil côté caméra (sud-ouest) : les façades tournées vers le joueur sont éclairées.
      sun.position.copy(cameraTarget).add(new THREE.Vector3(-12, 24, 14));
      sun.target.position.copy(cameraTarget);
      for (const s of [player, ...map.npcs.map((n) => n.sprite), followerFront, followerBack]) {
        if (!s) continue;
        s.update(dt);
        s.faceCamera(camera);
      }
    },
    resize(aspect) {
      camera.aspect = aspect;
      camera.updateProjectionMatrix();
    },
    pause(value) {
      paused = value;
      // En combat, aucune plante de l'arène ne doit s'écarter d'un joueur absent.
      if (value) for (const p of grassPushers.value) p.copy(FAR_AWAY);
      held.clear();
      player.moving = false;
      overlay.style.display = value ? 'none' : '';
    },
    refreshFollower,
    /** Après une défaite : retour au Centre Pokémon s'il a été visité, sinon au point de départ. */
    async respawn() {
      const atCenter = state.respawn === 'center';
      await runBusy(async () => {
        await loadMap(atCenter ? 'center' : 'route-01', atCenter ? 'Spawn_Counter' : 'Spawn_Player', 'up');
        await (atCenter
          ? dialog.say(['Vos Pokémon ont été soignés.', 'Faites plus attention la prochaine fois !'],
            NPCS.NPC_Nurse.name)
          : dialog.say(['Vous vous dépêchez de rentrer…', 'Vos Pokémon se sont reposés et sont en pleine forme.']));
      });
    },
    dispose() {
      window.removeEventListener('keydown', onKey);
      window.removeEventListener('keyup', onKey);
      overlay.remove();
      dialog.dispose();
      menu.dispose();
      shop.dispose();
      scene.remove(map.level);
    },
  };
}
