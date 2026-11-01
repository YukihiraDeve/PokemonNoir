import { ITEMS, SHOP_STOCK, itemIcon } from '../game/items.js';
import { sounds } from '../engine/audio.js';

const MAX_QUANTITY = 99;
// Comme dans les jeux : une Honor Ball offerte pour 10 Poké Balls achetées d'un coup.
const BONUS_THRESHOLD = 10;

/** Boutique : choisir une quantité par article et payer avec l'argent gagné en combat. */
export class Shop {
  constructor(container, state) {
    this.state = state;
    this.quantities = {};
    this.message = '';
    this.root = Object.assign(document.createElement('div'), { className: 'gm shop' });
    this.root.addEventListener('click', (e) => this.onClick(e));
    this.onKey = (e) => {
      if (this.open && (e.code === 'Escape' || e.code === 'KeyX')) {
        e.stopImmediatePropagation();
        this.close();
      }
    };
    window.addEventListener('keydown', this.onKey, true);
    container.append(this.root);
  }

  get open() {
    return this.root.classList.contains('visible');
  }

  /** Ouvre la boutique ; la promesse se résout à la fermeture. */
  show() {
    this.quantities = Object.fromEntries(SHOP_STOCK.map((key) => [key, 1]));
    this.message = 'Que désirez-vous ?';
    this.root.classList.add('visible');
    this.render();
    return new Promise((resolve) => { this.resolve = resolve; });
  }

  close() {
    this.root.classList.remove('visible');
    sounds.back();
    this.resolve?.();
  }

  render() {
    const { money, bag } = this.state;
    const rows = SHOP_STOCK.map((key) => {
      const item = ITEMS[key];
      const qty = this.quantities[key];
      const total = item.price * qty;
      return `<div class="shop-row">
        <img src="${itemIcon(key)}" alt="">
        <span class="shop-name">${item.name}<small>Sac : ${bag[key] ?? 0}</small></span>
        <span class="shop-price">${item.price} ₽</span>
        <span class="shop-qty">
          <button data-minus="${key}" ${qty <= 1 ? 'disabled' : ''}>−</button>
          <b>${qty}</b>
          <button data-plus="${key}" ${qty >= MAX_QUANTITY ? 'disabled' : ''}>+</button>
        </span>
        <button class="shop-buy" data-buy="${key}" ${total > money ? 'disabled' : ''}>${total} ₽</button>
      </div>`;
    }).join('');
    this.root.innerHTML = `
      <div class="gm-head">
        <span class="gm-tab active">BOUTIQUE</span>
        <span class="gm-money">${money.toLocaleString('fr-FR')} ₽</span>
        <button class="gm-close" data-close="1">✕</button>
      </div>
      <p class="gm-hint">${this.message}</p>
      <div class="gm-body">${rows}</div>
      <div class="gm-foot"><span>Échap pour sortir</span></div>`;
  }

  onClick(e) {
    const b = e.target.closest('button');
    if (!b || b.disabled) return;
    const { minus, plus, buy } = b.dataset;
    if (b.dataset.close) return this.close();
    if (minus) this.quantities[minus] -= 1;
    if (plus) this.quantities[plus] += 1;
    if (buy) this.buy(buy);
    else sounds.select();
    return this.render();
  }

  buy(key) {
    const item = ITEMS[key];
    const qty = this.quantities[key];
    const total = item.price * qty;
    if (total > this.state.money) return;
    this.state.money -= total;
    this.state.bag[key] = (this.state.bag[key] ?? 0) + qty;
    this.message = `Vous achetez ${qty} × ${item.name} pour ${total} ₽. Merci !`;
    if (key === 'poke-ball' && qty >= BONUS_THRESHOLD) {
      this.state.bag['premier-ball'] = (this.state.bag['premier-ball'] ?? 0) + 1;
      this.message += ' En cadeau : une Honor Ball !';
    }
    this.quantities[key] = 1;
    sounds.buy();
    this.onBuy?.();
  }

  dispose() {
    window.removeEventListener('keydown', this.onKey, true);
    this.root.remove();
  }
}
