import { loadJSON } from '../engine/assets.js';

export const STAT_NAMES = {
  atk: 'Attaque', def: 'Défense', spa: 'Attaque Spé.', spd: 'Défense Spé.', spe: 'Vitesse',
  acc: 'Précision', eva: 'Esquive',
};

let data = null;

export async function loadGameData() {
  const [pokemon, moves, types, growth] = await Promise.all([
    loadJSON('/data/pokemon.json'),
    loadJSON('/data/moves.json'),
    loadJSON('/data/types.json'),
    loadJSON('/data/growth-rates.json'),
  ]);
  data = {
    pokedex: new Map(pokemon.map((p) => [p.id, p])),
    moves,
    chart: types.chart,
    types: Object.fromEntries(types.types.map((t) => [t.key, t])),
    growth,
  };
  return data;
}

export const typeInfo = (key) => data.types[key];
export const species = (id) => data.pokedex.get(id);

/** Expérience totale requise pour atteindre `level`. */
export const expForLevel = (mon, level) => data.growth[mon.species.growthRate][level - 1];

function computeStats(mon) {
  const { stats } = mon.species;
  const stat = (base) => Math.floor(((2 * base + 15) * mon.level) / 100) + 5;
  const maxHp = Math.floor(((2 * stats.hp + 15) * mon.level) / 100) + mon.level + 10;
  mon.hp += maxHp - (mon.maxHp ?? maxHp);
  mon.maxHp = maxHp;
  for (const k of ['atk', 'def', 'spa', 'spd', 'spe']) mon[k] = stat(stats[k]);
}

const toMove = (id) => ({ ...data.moves[id], ppLeft: data.moves[id].pp });

/** Crée un Pokémon (IV fixes à 15, pas d'EV) avec ses 4 dernières attaques apprises. */
export function createMon(id, level) {
  const sp = species(id);
  const known = [...new Set(sp.learnset.levelUp.filter(([l]) => l <= level).map(([, m]) => m))];
  const mon = { species: sp, level, hp: 0, exp: 0, moves: known.slice(-4).map(toMove) };
  computeStats(mon);
  mon.hp = mon.maxHp;
  mon.exp = expForLevel(mon, level);
  resetStages(mon);
  return mon;
}

export function resetStages(mon) {
  mon.stages = { atk: 0, def: 0, spa: 0, spd: 0, spe: 0, acc: 0, eva: 0 };
}

const stageMultiplier = (s) => (s >= 0 ? (2 + s) / 2 : 2 / (2 - s));
const effective = (mon, stat) => mon[stat] * stageMultiplier(mon.stages[stat]);

export function typeEffectiveness(moveType, defender) {
  return defender.species.types.reduce((m, t) => m * (data.chart[moveType]?.[t] ?? 1), 1);
}

/** Résout une attaque. Renvoie ce qui s'est passé, sans rien afficher. */
export function useMove(attacker, defender, move) {
  move.ppLeft = Math.max(0, move.ppLeft - 1);
  const accuracy = move.accuracy ? move.accuracy * stageMultiplier(attacker.stages.acc - defender.stages.eva) : 100;
  if (Math.random() * 100 >= accuracy) return { missed: true };

  const result = { damage: 0, effectiveness: 1, critical: false, statChanges: [] };
  if (move.category !== 'status' && move.power) {
    const [a, d] = move.category === 'physical' ? ['atk', 'def'] : ['spa', 'spd'];
    const base = Math.floor(Math.floor((Math.floor((2 * attacker.level) / 5) + 2) * move.power
      * effective(attacker, a) / effective(defender, d)) / 50) + 2;
    const stab = attacker.species.types.includes(move.type) ? 1.5 : 1;
    result.effectiveness = typeEffectiveness(move.type, defender);
    result.critical = Math.random() < 1 / 16;
    const random = 0.85 + Math.random() * 0.15;
    if (result.effectiveness > 0) {
      result.damage = Math.max(1, Math.floor(base * stab * result.effectiveness * (result.critical ? 1.5 : 1) * random));
    }
    result.damage = Math.min(result.damage, defender.hp);
    defender.hp -= result.damage;
  }

  const changes = move.meta.statChanges;
  if (changes.length && (move.category === 'status' || Math.random() * 100 < move.meta.statChance)) {
    const target = move.target === 'user' ? attacker : defender;
    for (const { stat, change } of changes) {
      const before = target.stages[stat];
      target.stages[stat] = Math.max(-6, Math.min(6, before + change));
      result.statChanges.push({ target, stat, change, blocked: before === target.stages[stat] });
    }
  }
  return result;
}

/** Expérience gagnée en battant `defeated` (formule simplifiée des jeux). */
export const expReward = (defeated) => Math.floor((defeated.species.baseExp * defeated.level) / 7);

/** Ajoute de l'expérience ; renvoie les niveaux gagnés et les attaques apprises. */
export function gainExp(mon, amount) {
  mon.exp += amount;
  const events = [];
  while (mon.level < 100 && mon.exp >= expForLevel(mon, mon.level + 1)) {
    mon.level += 1;
    computeStats(mon);
    events.push({ level: mon.level });
    for (const [lvl, id] of mon.species.learnset.levelUp) {
      if (lvl === mon.level && mon.moves.length < 4 && !mon.moves.some((m) => m.id === id)) {
        mon.moves.push(toMove(id));
        events.push({ learned: data.moves[id] });
      }
    }
  }
  return events;
}

export function healMon(mon) {
  mon.hp = mon.maxHp;
  for (const move of mon.moves) move.ppLeft = move.pp;
}

export const serializeMon = (mon) => ({
  id: mon.species.id, level: mon.level, exp: mon.exp, hp: mon.hp,
  moves: mon.moves.map((m) => [m.id, m.ppLeft]),
});

export function restoreMon(saved) {
  const mon = createMon(saved.id, saved.level);
  mon.exp = saved.exp;
  mon.hp = Math.min(saved.hp, mon.maxHp);
  mon.moves = saved.moves.filter(([id]) => data.moves[id]).map(([id, pp]) => ({ ...data.moves[id], ppLeft: pp }));
  return mon;
}
