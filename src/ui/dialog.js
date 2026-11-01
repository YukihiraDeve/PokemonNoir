import { sounds } from '../engine/audio.js';

const ADVANCE_KEYS = new Set(['Space', 'Enter', 'NumpadEnter']);
const CHAR_MS = 22;

/** Boîte de dialogue du monde : le texte s'écrit lettre par lettre, Espace/Entrée/clic pour avancer. */
export class Dialog {
  constructor(container) {
    this.root = Object.assign(document.createElement('div'), {
      className: 'dlg',
      innerHTML: '<span class="dlg-speaker"></span><p></p><span class="dlg-next">▼</span>',
    });
    this.speaker = this.root.querySelector('.dlg-speaker');
    this.text = this.root.querySelector('p');
    this.queue = Promise.resolve();
    container.append(this.root);
  }

  get open() {
    return this.root.classList.contains('visible');
  }

  /**
   * Affiche une suite de répliques et attend que le joueur les fasse défiler. Deux appels
   * simultanés s'enchaînent au lieu de se mélanger.
   */
  say(lines, speaker = '') {
    this.queue = this.queue.then(async () => {
      this.speaker.textContent = speaker;
      this.speaker.hidden = !speaker;
      this.root.classList.add('visible');
      for (const line of [lines].flat()) await this.line(line);
      this.root.classList.remove('visible');
    });
    return this.queue;
  }

  line(text) {
    return new Promise((resolve) => {
      let shown = 0;
      this.root.classList.remove('ready');
      const timer = setInterval(() => {
        shown += 1;
        this.text.textContent = text.slice(0, shown);
        if (shown >= text.length) finishTyping();
      }, CHAR_MS);
      const finishTyping = () => {
        clearInterval(timer);
        shown = text.length;
        this.text.textContent = text;
        this.root.classList.add('ready');
      };
      const advance = (e) => {
        if (e.type === 'keydown' && !ADVANCE_KEYS.has(e.code)) return;
        e.preventDefault();
        e.stopImmediatePropagation();
        if (shown < text.length) return finishTyping();
        window.removeEventListener('keydown', advance, true);
        this.root.removeEventListener('pointerdown', advance);
        sounds.select();
        resolve();
      };
      // Laisse passer la touche qui a ouvert le dialogue avant d'écouter.
      setTimeout(() => {
        window.addEventListener('keydown', advance, true);
        this.root.addEventListener('pointerdown', advance);
      }, 120);
    });
  }

  dispose() {
    this.root.remove();
  }
}
