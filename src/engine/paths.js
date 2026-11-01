import * as THREE from 'three';
import { loadPixelTexture } from './assets.js';

const SAND = '/assets/environment/textures/sand.png';
const SLABS = '/assets/environment/textures/slabs.png';
const RES = 8;          // pixels du masque par case
const BLUR = 0.42;      // flou en cases : rayon des coins arrondis
const PAVED = 'PBKXE';  // cases dallées d'Arabelle (lignes `town` du haut de la grille)

/**
 * Masques vus de dessus, floutés : rouge = chemins de sable (cases « S »), vert = dalles
 * d'Arabelle. 1 au milieu de la zone, 0 en dehors, 0,5 sur le bord : les angles droits de la
 * grille deviennent des courbes.
 */
function groundMasks(tiles, town) {
  const w = tiles.cols * RES;
  const h = tiles.rows * RES;
  const layers = [new Float32Array(w * h), new Float32Array(w * h)];
  for (let y = 0; y < h; y++) {
    const r = Math.floor(y / RES);
    for (let x = 0; x < w; x++) {
      const ch = tiles.at(Math.floor(x / RES), r);
      layers[0][y * w + x] = ch === 'S' ? 1 : 0;
      layers[1][y * w + x] = r < town && PAVED.includes(ch) ? 1 : 0;
    }
  }
  // Trois flous en boîte ≈ un flou gaussien ; bords prolongés.
  const radius = Math.round(BLUR * RES);
  const tmp = new Float32Array(w * h);
  const pass = (src, dst, horizontal) => {
    const [n, m] = horizontal ? [w, h] : [h, w];
    for (let j = 0; j < m; j++) {
      const at = (i) => src[horizontal ? j * w + Math.min(n - 1, Math.max(0, i)) : Math.min(n - 1, Math.max(0, i)) * w + j];
      let sum = 0;
      for (let i = -radius; i <= radius; i++) sum += at(i);
      for (let i = 0; i < n; i++) {
        dst[horizontal ? j * w + i : i * w + j] = sum / (2 * radius + 1);
        sum += at(i + radius + 1) - at(i - radius);
      }
    }
  };
  for (const a of layers) {
    for (let k = 0; k < 3; k++) {
      pass(a, tmp, true);
      pass(tmp, a, false);
    }
  }
  const data = new Uint8Array(w * h * 2);
  for (let i = 0; i < w * h; i++) {
    data[i * 2] = Math.round(layers[0][i] * 255);
    data[i * 2 + 1] = Math.round(layers[1][i] * 255);
  }
  const texture = new THREE.DataTexture(data, w, h, THREE.RGFormat);
  texture.magFilter = THREE.LinearFilter;
  texture.minFilter = THREE.LinearFilter;
  texture.needsUpdate = true;
  return {
    texture,
    origin: new THREE.Vector2(tiles.originX, tiles.originZ),
    size: new THREE.Vector2(tiles.cols * tiles.tile, tiles.rows * tiles.tile),
  };
}

/**
 * Peint le sol du niveau comme dans les jeux Noir et Blanc, à partir de la grille :
 * - chemins de sable aux formes arrondies, bord irrégulier où des brins d'herbe empiètent sur
 *   le sable, liseré un peu plus sombre ;
 * - à Arabelle, dalles claires ; l'herbe s'y arrête en festons, sur une bande de terre beige.
 * Remplace le matériau des sols d'herbe (Ground*, matériau « Ground_Grass »). `town` : nombre de
 * lignes d'Arabelle en haut de la grille.
 */
export async function paintPaths(level, tiles, town = 0) {
  const [sand, slabs] = await Promise.all([loadPixelTexture(SAND), loadPixelTexture(SLABS)]);
  for (const t of [sand, slabs]) t.wrapS = t.wrapT = THREE.RepeatWrapping;
  const mask = groundMasks(tiles, town);
  let material = null;
  level.traverse((obj) => {
    if (!obj.isMesh || obj.material.name !== 'Ground_Grass') return;
    material ??= pathMaterial(obj.material, sand, slabs, mask);
    obj.material = material;
  });
}

function pathMaterial(grass, sand, slabs, mask) {
  const material = grass.clone();
  material.onBeforeCompile = (shader) => {
    Object.assign(shader.uniforms, {
      sandMap: { value: sand },
      slabsMap: { value: slabs },
      pathMask: { value: mask.texture },
      pathOrigin: { value: mask.origin },
      pathSize: { value: mask.size },
    });
    shader.vertexShader = `varying vec2 vPathPos;\n${shader.vertexShader}`.replace(
      '#include <worldpos_vertex>',
      `#include <worldpos_vertex>
      vPathPos = (modelMatrix * vec4(transformed, 1.0)).xz;`,
    );
    shader.fragmentShader = `uniform sampler2D sandMap;
      uniform sampler2D slabsMap;
      uniform sampler2D pathMask;
      uniform vec2 pathOrigin;
      uniform vec2 pathSize;
      varying vec2 vPathPos;
      float pathHash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
      float pathNoise(vec2 p) {
        vec2 i = floor(p);
        vec2 f = fract(p);
        f = f * f * (3.0 - 2.0 * f);
        return mix(mix(pathHash(i), pathHash(i + vec2(1.0, 0.0)), f.x),
                   mix(pathHash(i + vec2(0.0, 1.0)), pathHash(i + vec2(1.0, 1.0)), f.x), f.y);
      }
      ${shader.fragmentShader}`.replace(
      '#include <map_fragment>',
      `#include <map_fragment>
      vec2 masks = texture2D(pathMask, (vPathPos - pathOrigin) / pathSize).rg;
      float blade = dot(diffuseColor.rgb, vec3(0.3, 0.6, 0.1));
      vec3 sandColor = texture2D(sandMap, vMapUv).rgb;
      // Chemins : bord ondulé (trois octaves de bruit : méandres, festons, grain) ; les brins
      // clairs de l'herbe mordent sur le sable.
      float wobble = pathNoise(vPathPos * 0.35) * 0.45 + pathNoise(vPathPos * 0.9) * 0.35 + pathNoise(vPathPos * 3.1) * 0.2;
      float pathE = masks.r + (wobble - 0.5) * 0.42 - (blade - 0.2) * 0.45;
      float sandAmount = smoothstep(0.47, 0.53, pathE);
      // Liseré plus sombre côté sable, ombre douce côté herbe.
      float rim = smoothstep(0.45, 0.55, pathE) * (1.0 - smoothstep(0.55, 0.72, pathE));
      float shade = smoothstep(0.3, 0.48, pathE) * (1.0 - sandAmount);
      diffuseColor.rgb = mix(diffuseColor.rgb * (1.0 - shade * 0.25), sandColor * (1.0 - rim * 0.18), sandAmount);
      // Dalles d'Arabelle : l'herbe s'arrête en festons serrés sur une bande de terre beige,
      // puis viennent les dalles (une tous les 2,5 m, alignées sur les cases).
      float scallop = pathNoise(vPathPos * 2.6) * 0.65 + pathNoise(vPathPos * 0.8) * 0.35;
      float paveE = masks.g + (scallop - 0.5) * 0.34 - (blade - 0.2) * 0.3;
      float soil = smoothstep(0.42, 0.48, paveE);
      float slab = smoothstep(0.56, 0.62, paveE);
      float edgeShade = smoothstep(0.25, 0.44, paveE) * (1.0 - soil);
      vec3 slabColor = texture2D(slabsMap, vMapUv * 1.2).rgb;
      diffuseColor.rgb *= 1.0 - edgeShade * 0.22;
      diffuseColor.rgb = mix(diffuseColor.rgb, sandColor * vec3(1.06, 1.03, 0.95), soil);
      diffuseColor.rgb = mix(diffuseColor.rgb, slabColor, slab);`,
    );
  };
  material.customProgramCacheKey = () => 'ground-paths';
  return material;
}
