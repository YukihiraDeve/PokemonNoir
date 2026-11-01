import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { PixelPass } from './engine/pixelPass.js';
import { createGradePass } from './engine/gradePass.js';
import { windTime } from './engine/world.js';
import { loadingManager, loadGLTF } from './engine/assets.js';
import { playMusic } from './engine/audio.js';
import { animate } from './engine/tween.js';
import { loadGameData, createMon } from './game/pokemon.js';
import { newGame, loadGame, saveGame, clearSave, healParty } from './game/state.js';
import { NPCS } from './game/trainers.js';
import { MAPS } from './game/maps.js';
import { createOverworld } from './scenes/overworld.js';
import { createBattle } from './scenes/battle.js';

// Hauteur visée de l'image réduite : environ 450 lignes, soit des pixels de 2×2 en 1080p.
// Plus bas = plus pixelisé (240 donnait le rendu très rétro du premier prototype).
const TARGET_LINES = 450;
const PIXEL_RATIO = Math.min(window.devicePixelRatio, 2);

const canvas = document.getElementById('game');
const hud = document.getElementById('hud');
const flash = document.getElementById('flash');
const loading = document.getElementById('loading');

const renderer = new THREE.WebGLRenderer({ canvas, antialias: false, powerPreference: 'high-performance' });
renderer.setPixelRatio(PIXEL_RATIO);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFShadowMap;
renderer.toneMapping = THREE.NeutralToneMapping;
renderer.toneMappingExposure = 1.15;

const composer = new EffectComposer(renderer);
composer.setPixelRatio(PIXEL_RATIO);
const pixelPass = new PixelPass();
// Seuil au-dessus du blanc : seuls le ciel et les reflets du soleil brillent, pas les sprites.
const bloom = new UnrealBloomPass(new THREE.Vector2(1, 1), 0.2, 0.5, 1.3);
composer.addPass(pixelPass);
composer.addPass(bloom);
composer.addPass(new OutputPass());
composer.addPass(createGradePass());

let current = null;
let overworld = null;
let state = null;

function resize() {
  const w = window.innerWidth;
  const h = window.innerHeight;
  renderer.setSize(w, h, false);
  pixelPass.pixelSize = Math.max(1, Math.round((h * PIXEL_RATIO) / TARGET_LINES));
  composer.setSize(w, h);
  current?.resize(w / h);
}
window.addEventListener('resize', resize);

function show(view) {
  current = view;
  pixelPass.scene = view.scene;
  pixelPass.camera = view.camera;
  resize();
}

const fade = (to, ms) => {
  const from = parseFloat(flash.style.opacity || 0);
  return animate(ms, (t) => { flash.style.opacity = from + (to - from) * t; });
};

let inBattle = false;
/** Combat contre une équipe adverse ; trainer = { id, title, name, … } ou null (sauvage). */
async function startBattle({ enemyTeam, trainer = null }) {
  if (inBattle) return;
  inBattle = true;
  overworld?.pause(true);
  await fade(1, 250);
  const battle = await createBattle({
    hud, state, enemyTeam, trainer,
    onEnd: async (result) => {
      await fade(1, 300);
      battle.dispose();
      inBattle = false;
      if (result === 'win' && trainer) state.defeated.push(trainer.id);
      if (result === 'lose') healParty(state);
      saveGame(state);
      if (overworld) {
        await overworld.refreshFollower();
        overworld.pause(false);
        show(overworld);
        playMusic('town');
      }
      await fade(0, 400);
      if (result === 'lose') await overworld?.respawn();
    },
  });
  show(battle);
  await fade(0, 400);
}

const trainerBattle = (id) => {
  const data = NPCS[id];
  return startBattle({ enemyTeam: data.team.map(([species, level]) => createMon(species, level)), trainer: { id, ...data } });
};

let last = performance.now();
renderer.setAnimationLoop((now) => {
  const dt = Math.min((now - last) / 1000, 0.05);
  last = now;
  windTime.value += dt;
  current?.update(dt);
  if (current?.focus) {
    pixelPass.focusDistance = current.focus.distance;
    pixelPass.focusRange = current.focus.range;
  }
  if (current) composer.render(dt);
});

loadingManager.onProgress = (_url, loaded, total) => {
  loading.querySelector('.bar span').style.width = `${(loaded / total) * 100}%`;
};

async function boot() {
  await loadGameData();
  const params = new URLSearchParams(location.search);
  if (params.has('new')) clearSave();
  state = loadGame() ?? newGame();
  await Promise.all([
    ...Object.values(MAPS).map((m) => loadGLTF(m.file)),
    loadGLTF('/assets/scenes/battle-forest.glb'),
  ]);
  overworld = await createOverworld({
    hud, state,
    onEncounter: (mon) => startBattle({ enemyTeam: [mon] }),
    onTrainer: trainerBattle,
    onChange: () => saveGame(state),
    onNewGame: () => {
      clearSave();
      location.replace(location.pathname);
    },
  });
  loading.classList.add('done');
  setTimeout(() => loading.remove(), 600);

  // Raccourcis de test : ?scene=battle&enemy=506&level=4 (sauvage) ou ?trainer=NPC_Youngster.
  if (params.get('scene') === 'battle') {
    startBattle({ enemyTeam: [createMon(Number(params.get('enemy') ?? 504), Number(params.get('level') ?? 4))] });
  } else if (NPCS[params.get('trainer')]) {
    trainerBattle(params.get('trainer'));
  } else {
    show(overworld);
    playMusic('town');
  }
  // Accès depuis la console du navigateur pour tester.
  window.game = { state, startBattle, trainerBattle, createMon, get view() { return current; } };
}

boot().catch((err) => {
  console.error(err);
  loading.querySelector('p').textContent = `Erreur de chargement : ${err.message}`;
});
