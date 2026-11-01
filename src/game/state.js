import { createMon, healMon, serializeMon, restoreMon } from './pokemon.js';

const SAVE_KEY = 'pokemon3d-save';
const SAVE_VERSION = 1;
export const MAX_PARTY = 6;

/** Nouvelle partie : Vipélierre, quelques Poké Balls et Potions. */
export function newGame() {
  return {
    party: [createMon(495, 5)],
    box: [],
    bag: { 'poke-ball': 5, potion: 3 },
    money: 1000,
    defeated: [],
    respawn: 'start', // 'center' une fois le Centre Pokémon d'Arabelle visité
  };
}

// La sauvegarde est locale au navigateur ; elle peut être indisponible (navigation privée).
export function saveGame(state) {
  try {
    localStorage.setItem(SAVE_KEY, JSON.stringify({
      version: SAVE_VERSION,
      party: state.party.map(serializeMon),
      box: state.box.map(serializeMon),
      bag: state.bag,
      money: state.money,
      defeated: state.defeated,
      respawn: state.respawn,
    }));
  } catch {
    // Pas de stockage : la partie continue sans sauvegarde.
  }
}

export function loadGame() {
  try {
    const saved = JSON.parse(localStorage.getItem(SAVE_KEY));
    if (!saved || saved.version !== SAVE_VERSION || !saved.party?.length) return null;
    return {
      party: saved.party.map(restoreMon),
      box: saved.box.map(restoreMon),
      bag: saved.bag,
      money: saved.money,
      defeated: saved.defeated,
      respawn: saved.respawn ?? 'start',
    };
  } catch {
    return null;
  }
}

export function clearSave() {
  try {
    localStorage.removeItem(SAVE_KEY);
  } catch {
    // Rien à effacer.
  }
}

/** Range un Pokémon capturé : dans l'équipe s'il reste de la place, sinon au PC. */
export function storeCaught(state, mon) {
  if (state.party.length < MAX_PARTY) {
    state.party.push(mon);
    return 'party';
  }
  state.box.push(mon);
  return 'box';
}

export function healParty(state) {
  for (const mon of state.party) healMon(mon);
}

export const firstAlive = (party) => party.findIndex((mon) => mon.hp > 0);
