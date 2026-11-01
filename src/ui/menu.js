import { typeInfo } from '../game/pokemon.js';
import { ITEMS, bagEntries, itemIcon, useHealItem } from '../game/items.js';
import { sounds } from '../engine/audio.js';

const hpLevel = (ratio) => (ratio > 0.5 ? 'high' : ratio > 0.2 ? 'mid' : 'low');

/**
 * Menu du monde (Échap ou X) : équipe (changer le Pokémon de tête, soigner) et sac.
 * onChange() est appelé après chaque modification (sauvegarde, Pokémon qui suit le joueur).
 */
export class GameMenu {
  constructor(container, state, { onChange, onNewGame }) {
    this.state = state;
    this.onChange = onChange;
    this.tab = 'team';
    this.pendingItem = null;
    this.root = Object.assign(document.createElement('div'), { className: 'gm' });
    this.root.addEventListener('click', (e) => this.onClick(e, onNewGame));
    container.append(this.root);
  }

  get open() {
    return this.root.classList.contains('visible');
  }

  toggle(force = !this.open) {
    this.pendingItem = null;
    this.tab = 'team';
    this.root.classList.toggle('visible', force);
    if (force) this.render();
    sounds[force ? 'select' : 'back']();
  }

  render() {
    const { party, bag, money, box } = this.state;
    const team = party.map((mon, i) => {
      const ratio = mon.hp / mon.maxHp;
      const types = mon.species.types.map((t) => {
        const info = typeInfo(t);
        return `<span class="gm-type" style="background:${info.color}">${info.name.fr}</span>`;
      }).join('');
      const action = this.pendingItem
        ? `<button data-heal="${i}" ${mon.hp > 0 && mon.hp < mon.maxHp ? '' : 'disabled'}>Soigner</button>`
        : i > 0 ? `<button data-lead="${i}">En tête</button>` : '<span class="gm-lead">Vous suit</span>';
      return `<div class="gm-card">
        <img src="/assets/pokemon/icons/${mon.species.id}.png" alt="">
        <div class="gm-info">
          <strong>${mon.species.name.fr}</strong> <small>N.${mon.level}</small>
          <div class="gm-types">${types}</div>
          <div class="gm-hp"><span class="bh-bar"><span class="bh-fill" data-level="${hpLevel(ratio)}" style="width:${ratio * 100}%"></span></span>
          <small>${mon.hp > 0 ? `${mon.hp}/${mon.maxHp}` : 'K.O.'}</small></div>
        </div>
        ${action}
      </div>`;
    }).join('');
    const items = bagEntries(bag).map((it) => `<div class="gm-item">
      <img src="${itemIcon(it.key)}" alt=""><span>${it.name}</span><span>×${it.count}</span>
      ${it.kind === 'heal' ? `<button data-use="${it.key}">Utiliser</button>` : ''}
    </div>`).join('') || '<p>Le sac est vide.</p>';

    this.root.innerHTML = `
      <div class="gm-head">
        <button class="gm-tab ${this.tab === 'team' ? 'active' : ''}" data-tab="team">ÉQUIPE</button>
        <button class="gm-tab ${this.tab === 'bag' ? 'active' : ''}" data-tab="bag">SAC</button>
        <span class="gm-money">${money.toLocaleString('fr-FR')} ₽</span>
        <button class="gm-close" data-close="1">✕</button>
      </div>
      ${this.pendingItem ? `<p class="gm-hint">Sur quel Pokémon utiliser ${ITEMS[this.pendingItem].name} ?</p>` : ''}
      <div class="gm-body">${this.tab === 'team' ? team : items}</div>
      <div class="gm-foot">
        <span>${box.length ? `${box.length} Pokémon au PC` : ''}</span>
        <button class="gm-new" data-new="1">Nouvelle partie</button>
      </div>`;
  }

  onClick(e, onNewGame) {
    const b = e.target.closest('button');
    if (!b || b.disabled) return;
    const { tab, lead, use, heal } = b.dataset;
    if (b.dataset.close) return this.toggle(false);
    if (b.dataset.new) {
      if (window.confirm('Effacer la sauvegarde et recommencer ?')) onNewGame();
      return undefined;
    }
    sounds.select();
    if (tab) {
      this.tab = tab;
      this.pendingItem = null;
    } else if (lead) {
      const [mon] = this.state.party.splice(+lead, 1);
      this.state.party.unshift(mon);
      this.onChange();
    } else if (use) {
      this.pendingItem = use;
      this.tab = 'team';
    } else if (heal) {
      useHealItem(this.state.bag, this.pendingItem, this.state.party[+heal]);
      if (!this.state.bag[this.pendingItem]) this.pendingItem = null;
      this.onChange();
    }
    return this.render();
  }

  dispose() {
    this.root.remove();
  }
}
