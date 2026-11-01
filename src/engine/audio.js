// Les navigateurs bloquent le son tant que le joueur n'a ni cliqué ni appuyé sur une touche.
const MUSIC = {
  town: '/assets/audio/music/town-theme.mp3',
  battle: '/assets/audio/music/battle-theme-a.mp3',
};
const SFX = '/assets/audio/sfx';

let unlocked = false;
let current = null;
let wanted = null;
const tracks = {};

function unlock() {
  if (unlocked) return;
  unlocked = true;
  if (wanted) playMusic(wanted);
}
window.addEventListener('pointerdown', unlock);
window.addEventListener('keydown', unlock);

export function playMusic(name) {
  wanted = name;
  if (current && current !== tracks[name]) current.pause();
  if (!unlocked) return;
  tracks[name] ??= Object.assign(new Audio(MUSIC[name]), { loop: true, volume: 0.35 });
  current = tracks[name];
  current.currentTime = 0;
  current.play().catch(() => {});
}

export function playSound(url, volume = 0.6) {
  if (!unlocked) return;
  const audio = new Audio(encodeURI(url));
  audio.volume = volume;
  audio.play().catch(() => {});
}

// Bruit de pas selon le sol (fichiers Kenney footstep_<matière>_00x.ogg).
const FOOTSTEPS = { grass: 'grass', tallgrass: 'grass', dirt: 'carpet', stone: 'concrete', floor: 'wood' };

export const sounds = {
  cry: (id) => playSound(`/assets/pokemon/cries/${id}.ogg`, 0.5),
  hit: () => playSound(`${SFX}/kenney_impact-sounds/Audio/impactPunch_heavy_00${Math.floor(Math.random() * 5)}.ogg`),
  select: () => playSound(`${SFX}/kenney_interface-sounds/Audio/click_002.ogg`, 0.5),
  back: () => playSound(`${SFX}/kenney_interface-sounds/Audio/back_001.ogg`, 0.5),
  buy: () => playSound(`${SFX}/kenney_rpg-audio/Audio/handleCoins.ogg`, 0.6),
  door: () => playSound(`${SFX}/kenney_rpg-audio/Audio/doorOpen_1.ogg`, 0.5),
  heal: () => playSound(`${SFX}/kenney_interface-sounds/Audio/confirmation_002.ogg`, 0.6),
  step: (surface = 'grass') => playSound(
    `${SFX}/kenney_impact-sounds/Audio/footstep_${FOOTSTEPS[surface] ?? 'grass'}_00${Math.floor(Math.random() * 5)}.ogg`, 0.15),
  rustle: () => playSound(`${SFX}/kenney_rpg-audio/Audio/cloth${1 + Math.floor(Math.random() * 4)}.ogg`, 0.25),
};
