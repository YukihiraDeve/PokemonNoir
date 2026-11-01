import * as THREE from 'three';
import { loadJSON, loadPixelTexture } from './assets.js';

/**
 * Billboard découpé dans une planche de sprites. Le point d'origine est sous les pieds :
 * il suffit de le poser au sol. Projette une ombre qui suit la silhouette du sprite et
 * reçoit celles du décor.
 */
export class SheetSprite extends THREE.Mesh {
  constructor(texture, { frameW, frameH, cols, rows, pixelScale }) {
    const map = texture.clone();
    map.repeat.set(1 / cols, 1 / rows);
    const width = frameW * pixelScale;
    const height = frameH * pixelScale;
    const geometry = new THREE.PlaneGeometry(width, height);
    geometry.translate(0, height / 2, 0);
    // Normales vers le ciel : le sprite est éclairé comme le sol à ses pieds (soleil, ombre
    // des arbres). La part émissive garde les couleurs lisibles même à l'ombre.
    const normals = geometry.attributes.normal;
    for (let i = 0; i < normals.count; i++) normals.setXYZ(i, 0, 1, 0);
    // Couleur atténuée : au soleil, le sprite retrouve ses couleurs d'origine sans dépasser
    // le blanc (sinon le bloom le fait flasher).
    const material = new THREE.MeshLambertMaterial({
      map, alphaTest: 0.5, side: THREE.DoubleSide, color: new THREE.Color(0.6, 0.6, 0.6),
      emissive: 0xffffff, emissiveMap: map, emissiveIntensity: 0.22,
    });
    // Tourné vers la caméra qui regarde vers le bas, le haut du sprite bascule vers l'arrière et
    // s'enfoncerait dans un mur derrière le personnage. Chaque pixel prend donc la profondeur
    // qu'aurait un panneau vertical dressé à l'aplomb des pieds (un peu avancé vers la caméra) :
    // le sprite reste caché par ce qui se trouve devant lui, jamais par ce qui est derrière.
    // Cette profondeur varie linéairement à l'écran : on l'interpole sans correction de
    // perspective (valeur × w, puis ÷ w).
    material.onBeforeCompile = (shader) => {
      shader.vertexShader = `varying float vSpriteDepthW;\nvarying float vSpriteW;\n${shader.vertexShader}`.replace(
        '#include <project_vertex>',
        `#include <project_vertex>
        vec3 spriteFoot = (modelMatrix * vec4(0.0, 0.0, 0.0, 1.0)).xyz;
        vec3 spriteFwd = spriteFoot - cameraPosition;
        spriteFwd.y = 0.0;
        spriteFwd = normalize(spriteFwd);
        vec3 spriteRay = (modelMatrix * vec4(transformed, 1.0)).xyz - cameraPosition;
        float spriteT = (dot(spriteFoot - cameraPosition, spriteFwd) - 0.3) / dot(spriteRay, spriteFwd);
        vec4 uprightClip = projectionMatrix * viewMatrix * vec4(cameraPosition + spriteRay * spriteT, 1.0);
        vSpriteDepthW = uprightClip.z / uprightClip.w * gl_Position.w;
        vSpriteW = gl_Position.w;`,
      );
      shader.fragmentShader = `varying float vSpriteDepthW;\nvarying float vSpriteW;\n${shader.fragmentShader}`.replace(
        '#include <dithering_fragment>',
        `#include <dithering_fragment>
        gl_FragDepth = vSpriteDepthW / vSpriteW * 0.5 + 0.5;`,
      );
    };
    material.customProgramCacheKey = () => 'sheet-sprite';
    super(geometry, material);
    this.receiveShadow = true;
    this.customDepthMaterial = new THREE.MeshDepthMaterial({
      depthPacking: THREE.RGBADepthPacking,
      map,
      alphaTest: 0.5,
    });
    this.castShadow = true;
    this.cols = cols;
    this.rows = rows;
    this.size = new THREE.Vector2(width, height);
    this.setFrame(0, 0);
  }

  setFrame(col, row) {
    this.material.map.offset.set(col / this.cols, 1 - (row + 1) / this.rows);
  }

  /** Miroir horizontal (les sprites de face regardent vers la gauche). */
  setFlipped(flipped) {
    this.scale.x = Math.abs(this.scale.x) * (flipped ? -1 : 1);
  }

  /** Face à la caméra, en restant ancré par les pieds. */
  faceCamera(camera) {
    this.quaternion.copy(camera.quaternion);
  }

  dispose() {
    this.geometry.dispose();
    this.material.map.dispose();
    this.material.dispose();
    this.customDepthMaterial.dispose();
  }
}

/** Pokémon animé à partir des planches générées depuis les GIF Noir & Blanc. */
export class PokemonSprite extends SheetSprite {
  static async create(id, variant, pixelScale) {
    const index = await loadJSON('/assets/pokemon/sprites/index.json');
    const meta = index[id][variant];
    const texture = await loadPixelTexture(`/assets/pokemon/sprites/${variant}/${id}.png`);
    return new PokemonSprite(texture, meta, pixelScale);
  }

  constructor(texture, meta, pixelScale) {
    const rows = Math.ceil(meta.durations.length / meta.cols);
    super(texture, { frameW: meta.w, frameH: meta.h, cols: meta.cols, rows, pixelScale });
    this.durations = meta.durations;
    this.frame = 0;
    this.elapsed = 0;
    this.speed = 1;
  }

  update(dt) {
    this.elapsed += dt * 1000 * this.speed;
    while (this.elapsed >= this.durations[this.frame]) {
      this.elapsed -= this.durations[this.frame];
      this.frame = (this.frame + 1) % this.durations.length;
    }
    this.setFrame(this.frame % this.cols, Math.floor(this.frame / this.cols));
  }
}

/** Personnage du monde : 4 frames par ligne, une ligne par animation (walk-down, run-left…). */
export class CharacterSprite extends SheetSprite {
  static async create(name, pixelScale) {
    const index = await loadJSON('/assets/characters/overworld/index.json');
    const meta = index[name];
    const texture = await loadPixelTexture(`/assets/characters/overworld/${name}.png`);
    return new CharacterSprite(texture, meta, pixelScale);
  }

  constructor(texture, meta, pixelScale) {
    super(texture, { frameW: meta.w, frameH: meta.h, cols: meta.cols, rows: meta.rows.length, pixelScale });
    this.rowNames = meta.rows;
    this.facing = 'down';
    this.moving = false;
    this.running = false;
    this.elapsed = 0;
  }

  update(dt) {
    const kind = this.running && this.rowNames.includes(`run-${this.facing}`) ? 'run' : 'walk';
    const row = this.rowNames.indexOf(`${kind}-${this.facing}`);
    let col = 0;
    if (this.moving) {
      this.elapsed += dt * (kind === 'run' ? 12 : 8);
      col = Math.floor(this.elapsed) % this.cols;
    } else {
      this.elapsed = 0;
    }
    this.setFrame(col, row);
  }
}
