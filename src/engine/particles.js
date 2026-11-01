import * as THREE from 'three';
import { loadTexture } from './assets.js';
import { animate } from './tween.js';

const PNG = '/assets/vfx/kenney_particle-pack/PNG (Transparent)';

// Effet d'impact par type d'attaque : texture Kenney + couleur.
const EFFECTS = {
  fire: ['flame_02', 0xff8a2a], water: ['circle_05', 0x4aa8ff], grass: ['twirl_02', 0x7be04a],
  electric: ['spark_04', 0xffe14a], ice: ['star_06', 0xbff4ff], poison: ['smoke_04', 0xb05ad8],
  psychic: ['magic_03', 0xff6fae], ghost: ['magic_05', 0x8a6ad8], dark: ['smoke_07', 0x5a4060],
  fairy: ['star_08', 0xffa6d8], dragon: ['flame_05', 0x7a52ff], bug: ['star_03', 0xb8d020],
  flying: ['twirl_01', 0xe6eeff], fighting: ['star_04', 0xff9a6a], rock: ['dirt_02', 0xc8a868],
  ground: ['dirt_03', 0xd8b070], steel: ['spark_02', 0xdadaf0], normal: ['star_01', 0xffffff],
};

export class Particles {
  constructor(scene) {
    this.scene = scene;
    this.items = [];
  }

  async burst(position, type, { count = 14, spread = 1.6, life = 0.7, size = 0.9 } = {}) {
    const [file, color] = EFFECTS[type] ?? EFFECTS.normal;
    const map = await loadTexture(`${PNG}/${file}.png`);
    for (let i = 0; i < count; i++) {
      const sprite = new THREE.Sprite(new THREE.SpriteMaterial({
        map, color, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
      }));
      sprite.position.copy(position);
      const dir = new THREE.Vector3(Math.random() - 0.5, Math.random() * 0.8 + 0.2, Math.random() - 0.5).normalize();
      this.items.push({ sprite, velocity: dir.multiplyScalar(spread * (0.6 + Math.random())), age: 0, life, size });
      this.scene.add(sprite);
    }
  }

  /** Boule d'énergie qui file de `from` à `to` (attaques spéciales). */
  async projectile(from, to, type, ms = 420) {
    const [file, color] = EFFECTS[type] ?? EFFECTS.normal;
    const map = await loadTexture(`${PNG}/${file}.png`);
    const sprite = new THREE.Sprite(new THREE.SpriteMaterial({
      map, color, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
    }));
    sprite.scale.setScalar(1.1);
    this.scene.add(sprite);
    await animate(ms, (t) => {
      sprite.position.lerpVectors(from, to, t);
      sprite.position.y += Math.sin(t * Math.PI) * 0.8;
      sprite.material.rotation = t * 8;
    });
    this.scene.remove(sprite);
    sprite.material.dispose();
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
      p.sprite.position.addScaledVector(p.velocity, dt);
      p.velocity.y -= dt * 1.5;
      p.sprite.scale.setScalar(p.size * (0.5 + t));
      p.sprite.material.opacity = 1 - t;
      p.sprite.material.rotation += dt * 3;
      return true;
    });
  }
}
