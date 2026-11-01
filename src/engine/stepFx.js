import * as THREE from 'three';

// Petits sprites pixel art dessinés à la volée (une lettre = une couleur, « . » = vide).
const SHAPES = {
  leaf: {
    rows: ['..oo..', '.oggo.', 'oglggo', 'ogggo.', '.ogo..', '..o...'],
    colors: { o: '#2f4d14', g: '#5f8f28', l: '#9fbf55' },
  },
  blade: {
    rows: ['.l', 'og', 'og', 'og', 'o.'],
    colors: { o: '#33521a', g: '#6a9a2e', l: '#a9c75c' },
  },
  dust: {
    rows: ['..dd..', '.dlld.', 'dllldd', 'dlldd.', '.ddd..'],
    colors: { d: 'rgba(150,104,58,0.75)', l: 'rgba(196,150,96,0.85)' },
  },
};

function pixelTexture({ rows, colors }) {
  const canvas = Object.assign(document.createElement('canvas'), { width: rows[0].length, height: rows.length });
  const g = canvas.getContext('2d');
  rows.forEach((row, y) => [...row].forEach((c, x) => {
    if (!colors[c]) return;
    g.fillStyle = colors[c];
    g.fillRect(x, y, 1, 1);
  }));
  const texture = new THREE.CanvasTexture(canvas);
  texture.magFilter = THREE.NearestFilter;
  texture.minFilter = THREE.NearestFilter;
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

/**
 * Effets de pas : brins d'herbe qui sautent, feuilles qui volent dans les herbes hautes,
 * petite poussière sur la terre. Surfaces : 'grass', 'tallgrass', 'dirt', 'stone', 'floor'.
 */
export class StepFx {
  constructor(scene) {
    this.scene = scene;
    this.items = [];
    this.textures = Object.fromEntries(Object.entries(SHAPES).map(([k, v]) => [k, pixelTexture(v)]));
  }

  spawn(position, shape, { size, up, spread, life, gravity = 7, grow = 0, rise = 0.25 }) {
    const sprite = new THREE.Sprite(new THREE.SpriteMaterial({
      map: this.textures[shape], transparent: true, depthWrite: false,
      // Légèrement atténué : les sprites ne sont pas éclairés, l'herbe autour l'est.
      color: shape === 'dust' ? 0xffffff : 0xe2ead8,
    }));
    const angle = Math.random() * Math.PI * 2;
    const r = Math.random() * spread;
    sprite.position.set(position.x + Math.cos(angle) * r * 0.4, position.y + rise, position.z + Math.sin(angle) * r * 0.4);
    sprite.scale.setScalar(size);
    sprite.material.rotation = Math.random() * Math.PI * 2;
    this.scene.add(sprite);
    this.items.push({
      sprite, age: 0, life, gravity, grow, size,
      velocity: new THREE.Vector3(Math.cos(angle) * r, up * (0.7 + Math.random() * 0.6), Math.sin(angle) * r),
      spin: (Math.random() - 0.5) * 10,
    });
  }

  /** Un pas sur `surface` ; `strength` réduit l'effet (ex. 0.5 pour le Pokémon qui suit). */
  step(position, surface, { running = false, strength = 1 } = {}) {
    // Discret : l'herbe se couche déjà au passage, les particules ne font que souligner le pas.
    const chance = (p) => Math.random() < p * strength * (running ? 1.3 : 1);
    if (surface === 'tallgrass') {
      if (chance(0.9)) this.spawn(position, 'blade', { size: 0.08 + Math.random() * 0.04, up: 1.6, spread: 0.6, life: 0.6, rise: 0.5 });
      if (chance(0.35)) this.spawn(position, 'leaf', { size: 0.08 + Math.random() * 0.03, up: 1.4, spread: 0.6, life: 0.7, rise: 0.5 });
    } else if (surface === 'grass') {
      if (chance(0.25)) this.spawn(position, 'blade', { size: 0.07, up: 1.0, spread: 0.4, life: 0.4, rise: 0.08 });
    } else if (surface === 'dirt' || (surface === 'stone' && running)) {
      if (chance(running ? 0.8 : 0.5)) {
        this.spawn(position, 'dust', { size: 0.14, up: 0.3, spread: 0.3, life: 0.5, gravity: 0, grow: 0.4, rise: 0.05 });
      }
    }
  }

  update(dt) {
    this.items = this.items.filter((p) => {
      p.age += dt;
      const t = p.age / p.life;
      if (t >= 1) {
        this.scene.remove(p.sprite);
        p.sprite.material.dispose();
        return false;
      }
      p.velocity.y -= p.gravity * dt;
      p.velocity.multiplyScalar(1 - dt * 1.5); // freinage de l'air
      p.sprite.position.addScaledVector(p.velocity, dt);
      p.sprite.material.rotation += p.spin * dt;
      p.sprite.scale.setScalar(p.size * (1 + p.grow * t));
      p.sprite.material.opacity = t < 0.65 ? 1 : 1 - (t - 0.65) / 0.35;
      return true;
    });
  }

  clear() {
    for (const p of this.items) {
      this.scene.remove(p.sprite);
      p.sprite.material.dispose();
    }
    this.items = [];
  }
}
