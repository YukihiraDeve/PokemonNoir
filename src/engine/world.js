import * as THREE from 'three';
import { loadHDR } from './assets.js';

const SKY = '/assets/environment/hdri/kloofendal_48d_partly_cloudy_puresky_1k.hdr';
// Feuillage du kit un peu plus vert et saturé, comme sur la référence.
const FOLIAGE_TINT = new THREE.Color(0.95, 1.25, 0.7);
// Balancement au vent (déplacement par mètre de hauteur) : arbres et petites plantes.
const WIND = { tree: 0.01, plant: 0.045 };
// Lumière bleutée des vitrages éclairés, telle qu'elle retombe sur le sol.
const WINDOW_LIGHT = new THREE.Color(0x9fd2ff).multiplyScalar(0.55);

/** Temps partagé par tous les feuillages animés (incrémenté par la boucle de jeu). */
export const windTime = { value: 0 };

/**
 * Positions qui écartent la végétation basse (le joueur et son Pokémon), mises à jour par la
 * carte à chaque image. Loin de tout par défaut.
 */
export const grassPushers = { value: [new THREE.Vector3(1e4, 0, 1e4), new THREE.Vector3(1e4, 0, 1e4)] };

function addWind(material, strength) {
  material.onBeforeCompile = (shader) => {
    shader.uniforms.windTime = windTime;
    shader.uniforms.grassPushers = grassPushers;
    shader.vertexShader = `uniform float windTime;\nuniform vec3 grassPushers[2];\n${shader.vertexShader}`
      .replace(
        '#include <begin_vertex>',
        `#include <begin_vertex>
        vec4 windWorld = modelMatrix * vec4(position, 1.0);
        float windGust = sin(windTime * 1.7 + windWorld.x * 0.35 + windWorld.z * 0.27)
                       + 0.4 * sin(windTime * 3.1 + windWorld.z * 0.9);
        float windHeight = max(position.y, 0.0) * ${strength.toFixed(4)};
        transformed.xz += vec2(1.0, 0.6) * windGust * windHeight;`,
      )
      // En repère monde : les plantes basses se couchent en s'écartant de ceux qui passent.
      // Les houppiers des arbres, bien plus hauts que le pied de leur modèle, ne bougent pas.
      .replace(
        '#include <project_vertex>',
        `vec4 pushWorld = modelMatrix * vec4(transformed, 1.0);
        float pushHeight = clamp(pushWorld.y - modelMatrix[3].y, 0.0, 2.0);
        for (int i = 0; i < 2; i++) {
          vec2 away = pushWorld.xz - grassPushers[i].xz;
          float dist = length(away);
          float influence = (1.0 - smoothstep(0.25, 1.15, dist)) * (1.0 - smoothstep(1.3, 2.0, pushHeight));
          float bend = influence * min(pushHeight, 1.2);
          pushWorld.xz += away / max(dist, 0.001) * bend * 0.45;
          pushWorld.y -= bend * 0.25;
        }
        vec4 mvPosition = viewMatrix * pushWorld;
        gl_Position = projectionMatrix * mvPosition;`,
      );
  };
  material.customProgramCacheKey = () => `wind-${strength}`;
}

/** Eau (étangs, mer) : bleu profond, reflets du ciel, petites vagues qui scintillent. */
/**
 * Eau : texture de vagues pixel art (celle du .glb) qui dérive lentement, reflets du ciel
 * ondulés par des normales animées.
 */
function waterMaterial(map) {
  const material = new THREE.MeshStandardMaterial({
    map, roughness: 0.25, metalness: 0.05, transparent: true, opacity: 0.92,
  });
  material.onBeforeCompile = (shader) => {
    shader.uniforms.windTime = windTime;
    shader.vertexShader = `varying vec3 vWaterPos;\n${shader.vertexShader}`.replace(
      '#include <worldpos_vertex>',
      `#include <worldpos_vertex>
      vWaterPos = (modelMatrix * vec4(transformed, 1.0)).xyz;`,
    );
    shader.fragmentShader = `uniform float windTime;\nvarying vec3 vWaterPos;\n${shader.fragmentShader}`.replace(
      '#include <map_fragment>',
      `vec4 sampledDiffuseColor = texture2D(map, vMapUv + vec2(windTime * 0.012, windTime * 0.007));
      diffuseColor *= sampledDiffuseColor;`,
    ).replace(
      '#include <normal_fragment_maps>',
      `#include <normal_fragment_maps>
      vec2 waterUv = vWaterPos.xz;
      normal = normalize(normal + vec3(
        sin(waterUv.x * 1.3 + windTime * 1.4) * 0.07 + sin(waterUv.y * 2.3 - windTime * 1.1) * 0.05,
        0.0,
        cos(waterUv.y * 1.6 + windTime * 1.2) * 0.07 + sin((waterUv.x + waterUv.y) * 2.9 + windTime * 2.0) * 0.03));`,
    );
  };
  material.customProgramCacheKey = () => 'water';
  return material;
}

/** Soleil chaud aux ombres légèrement adoucies + ciel HDR pour le fond et les reflets. */
export async function addLighting(scene, { shadowExtent = 30 } = {}) {
  const sky = await loadHDR(SKY);
  scene.background = sky;
  scene.environment = sky;
  scene.environmentIntensity = 0.25;
  scene.fog = new THREE.Fog(0x9fc29a, 45, 150);

  const hemi = new THREE.HemisphereLight(0xcfe6ff, 0x2f4a1c, 0.75);
  const sun = new THREE.DirectionalLight(0xffe6bf, 4.2);
  sun.castShadow = true;
  sun.shadow.mapSize.set(2048, 2048);
  Object.assign(sun.shadow.camera, {
    left: -shadowExtent, right: shadowExtent, top: shadowExtent, bottom: -shadowExtent, near: 1, far: 150,
  });
  sun.shadow.radius = 4;
  sun.shadow.bias = -0.0004;
  sun.shadow.normalBias = 0.04;
  scene.add(hemi, sun, sun.target);
  return { sun, hemi };
}

/** Réglages communs aux scènes exportées de Blender (une seule fois par modèle). */
export function prepareLevel(root) {
  if (root.userData.prepared) return;
  root.userData.prepared = true;
  const done = new Set();
  let water = null;
  root.traverse((obj) => {
    if (!obj.isMesh) return;
    if (/^Water/.test(obj.name)) {
      water ??= waterMaterial(obj.material.map);
      obj.material = water;
      obj.castShadow = false;
      obj.receiveShadow = true;
      return;
    }
    if (/^Glow/.test(obj.name)) {
      // Lumière des fenêtres posée au sol : ajoutée à ce qui est dessous, sans ombre ni profondeur.
      const { map } = obj.material;
      map.magFilter = THREE.LinearFilter;
      map.minFilter = THREE.LinearFilter;
      map.needsUpdate = true;
      obj.material = new THREE.MeshBasicMaterial({
        map, color: WINDOW_LIGHT, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
      });
      obj.renderOrder = 2;
      obj.castShadow = false;
      obj.receiveShadow = false;
      return;
    }
    if (/^Foam/.test(obj.name)) {
      // Liseré d'écume posé sur l'eau : dessiné après elle, sans masquer ce qui est dessous.
      Object.assign(obj.material, { transparent: true, depthWrite: false });
      obj.renderOrder = 1;
      obj.castShadow = false;
      return;
    }
    const flat = /^(Ground|Pad|Path)/.test(obj.name);
    obj.castShadow = !flat;
    obj.receiveShadow = true;
    for (const mat of [obj.material].flat()) {
      if (done.has(mat)) continue;
      done.add(mat);
      if (/^Leaves/.test(mat.name)) mat.color.multiply(FOLIAGE_TINT);
      if (/^Leaves_(NormalTree|Pine|TwistedTree)/.test(mat.name)) addWind(mat, WIND.tree);
      else if (/^(Leaves|Grass|Flowers)$/.test(mat.name)) addWind(mat, WIND.plant);
      if (mat.alphaTest > 0) mat.alphaTest = 0.5;
    }
  });
}

/** Rectangle (x, z) d'un repère vide exporté de Blender : position ± échelle. */
export function markerRect(node) {
  const p = node.getWorldPosition(new THREE.Vector3());
  return { minX: p.x - node.scale.x, maxX: p.x + node.scale.x, minZ: p.z - node.scale.z, maxZ: p.z + node.scale.z };
}

export const inRect = (r, x, z) => x >= r.minX && x <= r.maxX && z >= r.minZ && z <= r.maxZ;
