import { typeInfo, expForLevel } from '../game/pokemon.js';
import { bagEntries, itemIcon } from '../game/items.js';
import { MAX_PARTY } from '../game/state.js';
import { sounds } from '../engine/audio.js';
import { wait } from '../engine/tween.js';

const el = (tag, className, html = '') => Object.assign(document.createElement(tag), { className, innerHTML: html });
const BALL = itemIcon('poke-ball');
const BACK = '<button class="bh-move bh-back" data-back="1">RETOUR</button>';

function panel(side) {
  return el('div', `bh-panel bh-${side}`, `
    <div class="bh-name"><span class="bh-type"></span><span class="bh-label"></span><span class="bh-level"></span></div>
    <div class="bh-hp"><span class="bh-hp-tag">PV</span><div class="bh-bar"><div class="bh-fill"></div></div></div>
    ${side === 'player' ? '<div class="bh-hp-text"></div><div class="bh-exp"><div class="bh-exp-fill"></div></div>' : ''}`);
}

const hpLevel = (ratio) => (ratio > 0.5 ? 'high' : ratio > 0.2 ? 'mid' : 'low');

/** Rangée de Poké Balls : une par Pokémon (grisée s'il est K.O.), cercles vides ensuite. */
const ballRow = (team, max = MAX_PARTY) =>
  Array.from({ length: max }, (_, i) => {
    if (i >= team.length) return '<span class="bh-empty"></span>';
    return `<img src="${BALL}" alt="" class="${team[i].hp > 0 ? '' : 'ko'}">`;
  }).join('');

/** Interface de combat (HTML par-dessus le rendu 3D), dans l'esprit de la référence. */
export class BattleHud {
  constructor(container) {
    this.root = el('div', 'battle-hud', `
      <div class="bh-band-top"></div>
      <div class="bh-band-corner"></div>
      <div class="bh-message"><p></p></div>
      <div class="bh-party"></div>
      <div class="bh-enemy-party"></div>
      <div class="bh-actions">
        <button class="bh-act bh-fight" data-action="fight"><span>ATTAQUE !</span></button>
        <button class="bh-act bh-bag" data-action="bag"><span>SAC</span></button>
        <button class="bh-act bh-run" data-action="run"><span>FUITE</span></button>
        <button class="bh-act bh-pkmn" data-action="pokemon"><span>POKéMON</span></button>
      </div>
      <div class="bh-moves"></div>
      <div class="bh-sheet"></div>`);
    this.enemyPanel = panel('enemy');
    this.playerPanel = panel('player');
    this.root.append(this.enemyPanel, this.playerPanel);
    this.message = this.root.querySelector('.bh-message p');
    this.menus = {
      main: this.root.querySelector('.bh-actions'),
      moves: this.root.querySelector('.bh-moves'),
      sheet: this.root.querySelector('.bh-sheet'),
    };
    this.party = this.root.querySelector('.bh-party');
    this.enemyParty = this.root.querySelector('.bh-enemy-party');
    container.append(this.root);
    this.showMenu(null);
  }

  setMon(side, mon) {
    const p = side === 'enemy' ? this.enemyPanel : this.playerPanel;
    p.querySelector('.bh-label').textContent = mon.species.name.fr.toUpperCase();
    p.querySelector('.bh-level').textContent = `N.${mon.level}`;
    const t = typeInfo(mon.species.types[0]);
    p.querySelector('.bh-type').style.background = t.color;
    p.querySelector('.bh-type').title = t.name.fr;
    this.setHp(side, mon, false);
    if (side === 'player') this.setExp(mon, false);
  }

  /** Affiche ou masque le panneau d'un camp. */
  showPanel(side, visible) {
    (side === 'enemy' ? this.enemyPanel : this.playerPanel).classList.toggle('hidden', !visible);
  }

  setHp(side, mon, animated = true) {
    const p = side === 'enemy' ? this.enemyPanel : this.playerPanel;
    const ratio = mon.hp / mon.maxHp;
    const fill = p.querySelector('.bh-fill');
    fill.style.transition = animated ? 'width 0.6s linear, background-color 0.3s' : 'none';
    fill.style.width = `${ratio * 100}%`;
    fill.dataset.level = hpLevel(ratio);
    const text = p.querySelector('.bh-hp-text');
    if (text) text.textContent = `${mon.hp}/${mon.maxHp}`;
  }

  setExp(mon, animated = true) {
    const lo = expForLevel(mon, mon.level);
    const hi = expForLevel(mon, Math.min(100, mon.level + 1));
    const fill = this.playerPanel.querySelector('.bh-exp-fill');
    fill.style.transition = animated ? 'width 0.8s ease-out' : 'none';
    fill.style.width = `${hi > lo ? ((mon.exp - lo) / (hi - lo)) * 100 : 100}%`;
  }

  setParty(party) {
    this.party.innerHTML = ballRow(party);
  }

  /** Équipe du dresseur adverse (null pour un Pokémon sauvage). */
  setEnemyParty(team) {
    this.enemyParty.innerHTML = team ? ballRow(team, team.length) : '';
    this.enemyParty.classList.toggle('visible', Boolean(team));
  }

  async say(text, ms = 1100) {
    this.message.parentElement.classList.add('visible');
    this.message.textContent = text;
    await wait(ms);
  }

  /** Affiche un menu ('main', 'moves', 'sheet') ou aucun (null). */
  showMenu(which) {
    for (const [name, node] of Object.entries(this.menus)) node.classList.toggle('visible', name === which);
  }

  renderMoves(mon) {
    this.menus.moves.innerHTML = mon.moves.map((m, i) => {
      const t = typeInfo(m.type);
      return `<button class="bh-move" data-move="${i}" style="--type:${t.color}" ${m.ppLeft ? '' : 'disabled'}>
        <span class="bh-move-name">${m.name.fr}</span>
        <span class="bh-move-info"><em>${t.name.fr}</em> PP ${m.ppLeft}/${m.pp}</span></button>`;
    }).join('') + BACK;
  }

  renderBag(bag) {
    const entries = bagEntries(bag);
    this.menus.sheet.innerHTML = `<h3>SAC</h3>${entries.map((it) => `
      <button class="bh-row" data-item="${it.key}">
        <img src="${itemIcon(it.key)}" alt=""><span class="bh-row-name">${it.name}</span><span>×${it.count}</span>
      </button>`).join('') || '<p class="bh-empty-text">Le sac est vide.</p>'}${BACK}`;
  }

  renderParty(party, active, forced) {
    this.menus.sheet.innerHTML = `<h3>${forced ? 'QUEL POKéMON ENVOYER ?' : 'ÉQUIPE'}</h3>${party.map((mon, i) => {
      const ratio = mon.hp / mon.maxHp;
      const status = i === active ? 'AU COMBAT' : mon.hp > 0 ? '' : 'K.O.';
      return `<button class="bh-row" data-mon="${i}" ${status ? 'disabled' : ''}>
        <img src="/assets/pokemon/icons/${mon.species.id}.png" alt="">
        <span class="bh-row-name">${mon.species.name.fr} <small>N.${mon.level}</small></span>
        <span class="bh-row-hp"><span class="bh-bar"><span class="bh-fill" data-level="${hpLevel(ratio)}" style="width:${ratio * 100}%"></span></span>
        <small>${status || `${mon.hp}/${mon.maxHp}`}</small></span>
      </button>`;
    }).join('')}${forced ? '' : BACK}`;
  }

  /** Attend un clic dans le HUD ; handler(button) renvoie une valeur pour terminer, sinon undefined. */
  waitClick(handler) {
    return new Promise((resolve) => {
      const onClick = (e) => {
        const button = e.target.closest('button');
        if (!button || button.disabled) return;
        const result = handler(button);
        if (result === undefined) return;
        this.root.removeEventListener('click', onClick);
        this.showMenu(null);
        resolve(result);
      };
      this.root.addEventListener('click', onClick);
    });
  }

  /**
   * Choix du joueur pour ce tour :
   * { action: 'move', move } | { action: 'item', key } | { action: 'switch', index } | { action: 'run' }
   */
  chooseAction(mon, { party, active, bag }) {
    this.renderMoves(mon);
    this.showMenu('main');
    return this.waitClick((button) => {
      const { action, move, item, mon: index, back } = button.dataset;
      sounds[back ? 'back' : 'select']();
      // Navigation entre menus : on reste en attente (undefined).
      if (back) this.showMenu('main');
      else if (action === 'fight') this.showMenu('moves');
      else if (action === 'bag') {
        this.renderBag(bag);
        this.showMenu('sheet');
      } else if (action === 'pokemon') {
        this.renderParty(party, active, false);
        this.showMenu('sheet');
      }
      // Choix définitifs.
      else if (action === 'run') return { action: 'run' };
      else if (move !== undefined) return { action: 'move', move: mon.moves[+move] };
      else if (item) return { action: 'item', key: item };
      else if (index !== undefined) return { action: 'switch', index: +index };
      return undefined;
    });
  }

  /** Remplacement obligatoire après un K.O. */
  choosePokemon(party, active) {
    this.renderParty(party, active, true);
    this.showMenu('sheet');
    return this.waitClick((button) => {
      if (button.dataset.mon === undefined) return undefined;
      sounds.select();
      return +button.dataset.mon;
    });
  }

  dispose() {
    this.root.remove();
  }
}
