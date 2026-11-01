import * as THREE from 'three';
import { windTime, grassPushers } from './world.js';

const SEGMENTS = 4;
const MASK_CELL = 0.15; // résolution (m) du masque des chemins
const ROOT = new THREE.Color('#263d0d');
const MID = new THREE.Color('#4a7419');
const TIP = new THREE.Color('#a9c75c');

/**
 * Brin d'herbe de 1 m : ruban effilé en 4 segments, légèrement incurvé vers l'avant, couleur
 * sombre à la racine et claire à la pointe. L'instance règle largeur (x) et hauteur (y, z).
 * Normales tournées vers le ciel : le brin est éclairé comme le sol, sans faces noires.
 */
function bladeGeometry() {
  const positions = [];
  const colors = [];
  const indices = [];
  for (let i = 0; i < SEGMENTS; i++) {
    const t = i / SEGMENTS;
    const half = 0.5 * (1 - t) ** 0.8;
    const lean = t * t * 0.3;
    const c = t < 0.5 ? ROOT.clone().lerp(MID, t * 2) : MID.clone().lerp(TIP, (t - 0.5) * 2);
    positions.push(-half, t, lean, half, t, lean);
    colors.push(c.r, c.g, c.b, c.r, c.g, c.b);
  }
  positions.push(0, 1, 0.3);
  colors.push(TIP.r, TIP.g, TIP.b);
  for (let i = 0; i < SEGMENTS - 1; i++) {
    const a = i * 2;
    indices.push(a, a + 1, a + 2, a + 1, a + 3, a + 2);
  }
  const last = (SEGMENTS - 1) * 2;
  indices.push(last, last + 1, SEGMENTS * 2);

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  geometry.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));
  geometry.setAttribute('normal', new THREE.Float32BufferAttribute(
    Array.from({ length: positions.length / 3 }, () => [0, 1, 0]).flat(), 3));
  geometry.setIndex(indices);
  return geometry;
}

/** Vent et passage du joueur appliqués à chaque brin, en repère monde. */
function bladeMaterial() {
  const material = new THREE.MeshStandardMaterial({
    vertexColors: true, side: THREE.DoubleSide, roughness: 0.8, metalness: 0,
  });
  material.onBeforeCompile = (shader) => {
    shader.uniforms.windTime = windTime;
    shader.uniforms.grassPushers = grassPushers;
    shader.vertexShader = `uniform float windTime;\nuniform vec3 grassPushers[2];\n${shader.vertexShader}`.replace(
      '#include <project_vertex>',
      `mat4 bladeMatrix = modelMatrix * instanceMatrix;
      vec4 bladeWorld = bladeMatrix * vec4(transformed, 1.0);
      vec3 bladeRoot = (bladeMatrix * vec4(0.0, 0.0, 0.0, 1.0)).xyz;
      float bladeHeight = length(bladeMatrix[1].xyz);
      float bend = position.y * position.y * bladeHeight; // la pointe bouge, pas la racine

      float gust = sin(windTime * 1.8 + bladeRoot.x * 0.6 + bladeRoot.z * 0.45)
                 + 0.5 * sin(windTime * 3.4 + bladeRoot.x * 1.7 + bladeRoot.z * 0.9);
      bladeWorld.xz += vec2(0.55, 0.3) * gust * bend * 0.12;

      // Les brins se couchent en s'écartant du joueur et de son Pokémon.
      for (int i = 0; i < 2; i++) {
        vec2 away = bladeRoot.xz - grassPushers[i].xz;
        float dist = length(away);
        float push = 1.0 - smoothstep(0.15, 0.9, dist);
        bladeWorld.xz += away / max(dist, 0.001) * push * bend * 0.9;
        bladeWorld.y -= push * bend * 0.45;
      }
      vec4 mvPosition = viewMatrix * bladeWorld;
      gl_Position = projectionMatrix * mvPosition;`,
    );
  };
  material.customProgramCacheKey = () => 'grass-blade';
  return material;
}

/** Masque vu de dessus des surfaces sans herbe (chemins, terrains de combat, place pavée). */
function bareMask(meshes, rect) {
  const w = Math.ceil((rect.maxX - rect.minX) / MASK_CELL);
  const h = Math.ceil((rect.maxZ - rect.minZ) / MASK_CELL);
  const mask = new Uint8Array(w * h);
  const a = new THREE.Vector3();
  const b = new THREE.Vector3();
  const c = new THREE.Vector3();
  for (const mesh of meshes) {
    mesh.updateMatrixWorld(true);
    const pos = mesh.geometry.attributes.position;
    const index = mesh.geometry.index;
    const count = index ? index.count : pos.count;
    const vertex = (k, out) => out.fromBufferAttribute(pos, index ? index.getX(k) : k).applyMatrix4(mesh.matrixWorld);
    for (let k = 0; k < count; k += 3) {
      vertex(k, a);
      vertex(k + 1, b);
      vertex(k + 2, c);
      const x0 = Math.max(0, Math.floor((Math.min(a.x, b.x, c.x) - rect.minX) / MASK_CELL));
      const x1 = Math.min(w - 1, Math.ceil((Math.max(a.x, b.x, c.x) - rect.minX) / MASK_CELL));
      const z0 = Math.max(0, Math.floor((Math.min(a.z, b.z, c.z) - rect.minZ) / MASK_CELL));
      const z1 = Math.min(h - 1, Math.ceil((Math.max(a.z, b.z, c.z) - rect.minZ) / MASK_CELL));
      const area = (b.x - a.x) * (c.z - a.z) - (c.x - a.x) * (b.z - a.z);
      if (Math.abs(area) < 1e-9) continue;
      for (let zi = z0; zi <= z1; zi++) {
        const pz = rect.minZ + (zi + 0.5) * MASK_CELL;
        for (let xi = x0; xi <= x1; xi++) {
          const px = rect.minX + (xi + 0.5) * MASK_CELL;
          const u = ((b.x - px) * (c.z - pz) - (c.x - px) * (b.z - pz)) / area;
          const v2 = ((c.x - px) * (a.z - pz) - (a.x - px) * (c.z - pz)) / area;
          if (u >= -0.02 && v2 >= -0.02 && u + v2 <= 1.02) mask[zi * w + xi] = 1;
        }
      }
    }
  }
  return (x, z) => {
    const xi = Math.floor((x - rect.minX) / MASK_CELL);
    const zi = Math.floor((z - rect.minZ) / MASK_CELL);
    return xi >= 0 && zi >= 0 && xi < w && zi < h && mask[zi * w + xi] === 1;
  };
}

/**
 * Fait pousser des brins d'herbe sur le sol d'un niveau exporté de Blender (herbes hautes).
 * fields : [{ rect: {minX,maxX,minZ,maxZ}, density (brins/m²), height: [min,max], width: [min,max],
 * edge?: lisière (m) au bord du rectangle, fade?(x, z) → 0..1 (lisière calculée ailleurs), skip?(x, z) }].
 * Pas d'herbe sur les chemins (Path*, Pad*), ni dans les boîtes `solids` (bâtiments).
 * heightAt(x, z) : hauteur du sol.
 */
export function growGrass(level, { fields, solids = [], heightAt = () => 0 }) {
  const bare = [];
  level.traverse((obj) => {
    if (obj.isMesh && /^(Path|Pad)/.test(obj.name)) bare.push(obj);
  });
  const all = fields.reduce((r, f) => ({
    minX: Math.min(r.minX, f.rect.minX), maxX: Math.max(r.maxX, f.rect.maxX),
    minZ: Math.min(r.minZ, f.rect.minZ), maxZ: Math.max(r.maxZ, f.rect.maxZ),
  }), { minX: Infinity, maxX: -Infinity, minZ: Infinity, maxZ: -Infinity });
  const isBare = bareMask(bare, all);
  const inSolid = (x, z) => solids.some((b) => x > b.min.x && x < b.max.x && z > b.min.z && z < b.max.z);

  const total = fields.reduce((n, f) => n + Math.round((f.rect.maxX - f.rect.minX) * (f.rect.maxZ - f.rect.minZ) * f.density), 0);
  const mesh = new THREE.InstancedMesh(bladeGeometry(), bladeMaterial(), total);
  mesh.receiveShadow = true;
  mesh.castShadow = false;
  const matrix = new THREE.Matrix4();
  const quaternion = new THREE.Quaternion();
  const euler = new THREE.Euler();
  const position = new THREE.Vector3();
  const scale = new THREE.Vector3();
  const tint = new THREE.Color();
  const rand = (lo, hi) => lo + Math.random() * (hi - lo);
  let n = 0;
  for (const f of fields) {
    const count = Math.round((f.rect.maxX - f.rect.minX) * (f.rect.maxZ - f.rect.minZ) * f.density);
    for (let i = 0; i < count; i++) {
      const x = rand(f.rect.minX, f.rect.maxX);
      const z = rand(f.rect.minZ, f.rect.maxZ);
      if (isBare(x, z) || inSolid(x, z) || (f.skip && f.skip(x, z))) continue;
      // Lisière irrégulière : moins de brins et plus courts près du bord du champ.
      const toEdge = Math.min(x - f.rect.minX, f.rect.maxX - x, z - f.rect.minZ, f.rect.maxZ - z);
      const fade = f.fade ? f.fade(x, z) : f.edge ? Math.min(1, toEdge / f.edge) : 1;
      if (Math.random() > 0.25 + 0.75 * fade) continue;
      const h = rand(...f.height) * (0.45 + 0.55 * fade);
      position.set(x, heightAt(x, z) - 0.02, z);
      quaternion.setFromEuler(euler.set(rand(-0.15, 0.15), rand(0, Math.PI * 2), rand(-0.15, 0.15)));
      scale.set(rand(...f.width), h, h);
      mesh.setMatrixAt(n, matrix.compose(position, quaternion, scale));
      // Variations de teinte : certains brins plus jaunes, d'autres plus sombres.
      const k = Math.random();
      mesh.setColorAt(n, tint.setRGB(rand(0.8, 1.05) + k * 0.12, rand(0.85, 1.05), rand(0.75, 0.95)));
      n++;
    }
  }
  mesh.count = n;
  mesh.instanceMatrix.needsUpdate = true;
  mesh.instanceColor.needsUpdate = true;
  mesh.computeBoundingSphere();
  mesh.name = 'GrassBlades';
  return mesh;
}

/**
 * Champs d'herbes hautes à partir des cases « H » d'une grille : un rectangle par groupe de
 * cases, lisière fondue là où une case touche autre chose que des herbes hautes.
 */
export function tallGrassFields(tiles, base) {
  const isTall = (c, r) => tiles.at(c, r) === 'H';
  const seen = new Set();
  const fields = [];
  for (const start of tiles.cells('H')) {
    const key = (c, r) => `${c},${r}`;
    if (seen.has(key(start.c, start.r))) continue;
    // Groupe de cases voisines → rectangle englobant.
    const box = { minC: start.c, maxC: start.c, minR: start.r, maxR: start.r };
    const queue = [start];
    seen.add(key(start.c, start.r));
    while (queue.length) {
      const { c, r } = queue.pop();
      Object.assign(box, { minC: Math.min(box.minC, c), maxC: Math.max(box.maxC, c), minR: Math.min(box.minR, r), maxR: Math.max(box.maxR, r) });
      for (const [dc, dr] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
        if (isTall(c + dc, r + dr) && !seen.has(key(c + dc, r + dr))) {
          seen.add(key(c + dc, r + dr));
          queue.push({ c: c + dc, r: r + dr });
        }
      }
    }
    const nw = tiles.box(box.minC, box.minR);
    const se = tiles.box(box.maxC, box.maxR);
    fields.push({
      ...base,
      rect: { minX: nw.minX, maxX: se.maxX, minZ: nw.minZ, maxZ: se.maxZ },
      skip: (x, z) => tiles.tileAt(x, z) !== 'H',
      fade(x, z) {
        // Distance au bord de la case du côté où la voisine n'est pas une herbe haute.
        const [c, r] = tiles.cell(x, z);
        const b = tiles.box(c, r);
        let d = Infinity;
        if (!isTall(c - 1, r)) d = Math.min(d, x - b.minX);
        if (!isTall(c + 1, r)) d = Math.min(d, b.maxX - x);
        if (!isTall(c, r - 1)) d = Math.min(d, z - b.minZ);
        if (!isTall(c, r + 1)) d = Math.min(d, b.maxZ - z);
        return Math.min(1, d / base.edge);
      },
    });
  }
  return fields;
}

// Fleurs pixel art (une lettre = une couleur, « . » = transparent).
const FLOWER_SPRITES = {
  pink: { rows: ['..pp....', '.pPPp.pp', '.pPyPpPP', '..pPpPyP', '..g.pPPp', '.gg..gp.', '..g.g...', '...g....'],
    colors: { p: '#e27cb6', P: '#ffc6e6', y: '#fff0a0', g: '#4f9a34' } },
  white: { rows: ['..ww....', '.wWWw.ww', '.wWyWwWW', '..wWwWyW', '..g.wWWw', '.gg..gw.', '..g.g...', '...g....'],
    colors: { w: '#d9dcd2', W: '#ffffff', y: '#ffd24a', g: '#3f8a2c' } },
};

function flowerTexture({ rows, colors }) {
  const canvas = Object.assign(document.createElement('canvas'), { width: 8, height: 8 });
  const g = canvas.getContext('2d');
  rows.forEach((row, y) => [...row].forEach((ch, x) => {
    if (!colors[ch]) return;
    g.fillStyle = colors[ch];
    g.fillRect(x, y, 1, 1);
  }));
  const texture = new THREE.CanvasTexture(canvas);
  texture.magFilter = THREE.NearestFilter;
  texture.minFilter = THREE.NearestFilter;
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

/** Deux plans croisés : la touffe de fleurs se voit de partout. Normales vers le ciel. */
function crossedQuads(size) {
  const a = new THREE.PlaneGeometry(size, size);
  a.translate(0, size / 2, 0);
  const b = a.clone().rotateY(Math.PI / 2);
  const geometry = new THREE.BufferGeometry();
  for (const name of ['position', 'uv']) {
    const merged = new Float32Array([...a.attributes[name].array, ...b.attributes[name].array]);
    geometry.setAttribute(name, new THREE.BufferAttribute(merged, name === 'uv' ? 2 : 3));
  }
  geometry.setAttribute('normal', new THREE.Float32BufferAttribute(
    Array.from({ length: geometry.attributes.position.count }, () => [0, 1, 0]).flat(), 3));
  const offset = a.attributes.position.count;
  const front = [...a.index.array, ...[...b.index.array].map((i) => i + offset)];
  // Chaque face aussi dans l'autre sens : vue de dos, la normale reste vers le ciel (avec
  // DoubleSide, three.js la retournerait et la moitié des fleurs serait dans l'ombre).
  const back = [];
  for (let i = 0; i < front.length; i += 3) back.push(front[i], front[i + 2], front[i + 1]);
  geometry.setIndex([...front, ...back]);
  return geometry;
}

/**
 * Fleurs des cases « F » (champ rose dense), « f » (quelques fleurs roses) et « w » (fleurs
 * blanches de Renouet). Renvoie un groupe de deux InstancedMesh (rose, blanc).
 */
export function growFlowers(tiles, { heightAt }) {
  const group = new THREE.Group();
  group.name = 'Flowers';
  const plans = [
    { sprite: 'pink', letters: { F: 16, f: 2.5 } },
    { sprite: 'white', letters: { w: 10 } },
  ];
  const matrix = new THREE.Matrix4();
  const quaternion = new THREE.Quaternion();
  const position = new THREE.Vector3();
  const scale = new THREE.Vector3();
  const up = new THREE.Vector3(0, 1, 0);
  for (const { sprite, letters } of plans) {
    const cells = tiles.cells(Object.keys(letters).join(''));
    const area = tiles.tile * tiles.tile;
    const total = cells.reduce((n, cell) => n + Math.ceil(letters[cell.ch] * area), 0);
    if (!total) continue;
    const mesh = new THREE.InstancedMesh(crossedQuads(0.3), new THREE.MeshLambertMaterial({
      map: flowerTexture(FLOWER_SPRITES[sprite]), alphaTest: 0.5,
    }), total);
    mesh.receiveShadow = true;
    let n = 0;
    for (const cell of cells) {
      const count = Math.round(letters[cell.ch] * area * (0.7 + Math.random() * 0.6));
      for (let i = 0; i < count && n < total; i++) {
        const x = cell.x + (Math.random() - 0.5) * tiles.tile;
        const z = cell.z + (Math.random() - 0.5) * tiles.tile;
        const s = 0.8 + Math.random() * 0.6;
        position.set(x, heightAt(x, z) - 0.02, z);
        quaternion.setFromAxisAngle(up, Math.random() * Math.PI);
        mesh.setMatrixAt(n++, matrix.compose(position, quaternion, scale.set(s, s, s)));
      }
    }
    mesh.count = n;
    mesh.instanceMatrix.needsUpdate = true;
    mesh.computeBoundingSphere();
    group.add(mesh);
  }
  return group;
}
