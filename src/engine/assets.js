import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { HDRLoader } from 'three/addons/loaders/HDRLoader.js';

export const loadingManager = new THREE.LoadingManager();

const gltfLoader = new GLTFLoader(loadingManager);
const textureLoader = new THREE.TextureLoader(loadingManager);
const hdrLoader = new HDRLoader(loadingManager);
const cache = new Map();

// Chaque ressource n'est chargée qu'une fois, même si plusieurs scènes la demandent.
function once(key, load) {
  if (!cache.has(key)) cache.set(key, load());
  return cache.get(key);
}

export const loadJSON = (url) => once(url, () => fetch(url).then((r) => r.json()));

export const loadGLTF = (url) => once(url, () => gltfLoader.loadAsync(url));

export const loadHDR = (url) =>
  once(url, async () => {
    const texture = await hdrLoader.loadAsync(url);
    texture.mapping = THREE.EquirectangularReflectionMapping;
    return texture;
  });

/** Texture pixel art : pas de lissage, pas de mipmaps. */
export const loadPixelTexture = (url) =>
  once(url, async () => {
    const texture = await textureLoader.loadAsync(encodeURI(url));
    texture.colorSpace = THREE.SRGBColorSpace;
    texture.magFilter = THREE.NearestFilter;
    texture.minFilter = THREE.NearestFilter;
    texture.generateMipmaps = false;
    return texture;
  });

/** Texture d'effet (particules) : filtrage lissé. */
export const loadTexture = (url) =>
  once(url, async () => {
    const texture = await textureLoader.loadAsync(encodeURI(url));
    texture.colorSpace = THREE.SRGBColorSpace;
    return texture;
  });
