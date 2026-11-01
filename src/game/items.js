/** Objets utilisables. `rate` : bonus de capture des Balls ; `heal` : PV rendus par les potions. */
export const ITEMS = {
  'poke-ball': { name: 'Poké Ball', kind: 'ball', rate: 1, price: 200 },
  'great-ball': { name: 'Super Ball', kind: 'ball', rate: 1.5, price: 600 },
  'ultra-ball': { name: 'Hyper Ball', kind: 'ball', rate: 2, price: 1200 },
  'premier-ball': { name: 'Honor Ball', kind: 'ball', rate: 1, price: 0 },
  potion: { name: 'Potion', kind: 'heal', heal: 20, price: 300 },
  'super-potion': { name: 'Super Potion', kind: 'heal', heal: 50, price: 700 },
  'hyper-potion': { name: 'Hyper Potion', kind: 'heal', heal: 200, price: 1200 },
};

export const itemIcon = (key) => `/assets/items/${key}.png`;

/** Articles vendus au comptoir du Centre Pokémon d'Arabelle, dans l'ordre d'affichage. */
export const SHOP_STOCK = ['poke-ball', 'great-ball', 'ultra-ball', 'potion', 'super-potion', 'hyper-potion'];

/** Objets du sac encore disponibles, dans l'ordre du tableau ITEMS. */
export const bagEntries = (bag, kind) =>
  Object.keys(ITEMS)
    .filter((key) => bag[key] > 0 && (!kind || ITEMS[key].kind === kind))
    .map((key) => ({ key, ...ITEMS[key], count: bag[key] }));

export function useHealItem(bag, key, mon) {
  const item = ITEMS[key];
  if (!bag[key] || item.kind !== 'heal' || mon.hp <= 0 || mon.hp >= mon.maxHp) return 0;
  bag[key] -= 1;
  const healed = Math.min(item.heal, mon.maxHp - mon.hp);
  mon.hp += healed;
  return healed;
}

/**
 * Tentative de capture (formule de la 5e génération, sans statut).
 * Renvoie le nombre de secousses (0 à 3) et si le Pokémon est capturé.
 */
export function captureRoll(mon, rate) {
  const a = Math.floor(((3 * mon.maxHp - 2 * mon.hp) * mon.species.captureRate * rate) / (3 * mon.maxHp));
  if (a >= 255) return { shakes: 3, caught: true };
  const b = Math.floor(65536 / (255 / Math.max(1, a)) ** 0.1875);
  let shakes = 0;
  while (shakes < 3 && Math.random() * 65536 < b) shakes++;
  return { shakes, caught: shakes === 3 };
}
