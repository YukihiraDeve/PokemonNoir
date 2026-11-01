import * as THREE from 'three';
import { Pass, FullScreenQuad } from 'three/addons/postprocessing/Pass.js';

/**
 * Rend la scène dans une image réduite (pixelSize) puis l'agrandit sans lissage : les
 * sprites et textures gardent leurs pixels, la 3D reste nette grâce au MSAA.
 * Dans la même passe :
 * - un liseré sombre sur les silhouettes (détecté dans le tampon de profondeur) ;
 * - un flou de profondeur façon « HD-2D » : net autour de focusDistance ± focusRange,
 *   de plus en plus flou devant et derrière.
 * Pas de second rendu des normales (comme RenderPixelatedPass) : il ignorerait la
 * transparence des feuillages et dessinerait des carrés autour des bouquets de feuilles.
 */
export class PixelPass extends Pass {
  constructor(pixelSize = 2) {
    super();
    this.scene = null;
    this.camera = null;
    this.pixelSize = pixelSize;
    this.outline = 0.22;
    this.focusDistance = 10;
    this.focusRange = 6;
    this.maxBlur = 4; // rayon max du flou, en pixels de l'image réduite
    this.target = new THREE.WebGLRenderTarget(1, 1, {
      type: THREE.HalfFloatType,
      minFilter: THREE.NearestFilter,
      magFilter: THREE.NearestFilter,
      samples: 4,
      depthTexture: new THREE.DepthTexture(1, 1),
    });
    this.material = new THREE.ShaderMaterial({
      uniforms: {
        tColor: { value: null },
        tDepth: { value: null },
        texel: { value: new THREE.Vector2() },
        cameraNear: { value: 0.1 },
        cameraFar: { value: 100 },
        outline: { value: 0 },
        focusDistance: { value: 0 },
        focusRange: { value: 1 },
        maxBlur: { value: 0 },
      },
      vertexShader: /* glsl */ `
        varying vec2 vUv;
        void main() {
          vUv = uv;
          gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        }`,
      fragmentShader: /* glsl */ `
        #include <packing>
        uniform sampler2D tColor;
        uniform sampler2D tDepth;
        uniform vec2 texel;
        uniform float cameraNear;
        uniform float cameraFar;
        uniform float outline;
        uniform float focusDistance;
        uniform float focusRange;
        uniform float maxBlur;
        varying vec2 vUv;

        float viewDepth(vec2 uv) {
          return -perspectiveDepthToViewZ(texture2D(tDepth, uv).x, cameraNear, cameraFar);
        }

        // 0 = net, 1 = flou maximal.
        float blurAmount(float z) {
          return clamp((abs(z - focusDistance) - focusRange) / (focusRange * 1.5), 0.0, 1.0);
        }

        // Le pixel est sur le bord d'un objet si un voisin est nettement plus loin.
        float edge(float z, vec2 offset) {
          return clamp((viewDepth(vUv + offset) - z) / z - 0.08, 0.0, 1.0);
        }

        void main() {
          vec4 color = texture2D(tColor, vUv);
          float z = viewDepth(vUv);
          float blur = blurAmount(z);

          if (blur > 0.01) {
            // Disque de 16 échantillons en spirale (angle d'or).
            vec3 sum = color.rgb;
            float weight = 1.0;
            for (int i = 0; i < 16; i++) {
              float r = sqrt((float(i) + 0.5) / 16.0) * blur * maxBlur;
              float a = float(i) * 2.39996;
              vec2 uv = vUv + vec2(cos(a), sin(a)) * r * texel;
              // Un objet net au premier plan ne doit pas baver sur le fond flou.
              float w = (viewDepth(uv) < z - 0.5 && blurAmount(viewDepth(uv)) < 0.3) ? 0.0 : 1.0;
              sum += texture2D(tColor, uv).rgb * w;
              weight += w;
            }
            color.rgb = sum / weight;
          }

          float e = edge(z, vec2(texel.x, 0.0)) + edge(z, vec2(-texel.x, 0.0))
                  + edge(z, vec2(0.0, texel.y)) + edge(z, vec2(0.0, -texel.y));
          color.rgb *= 1.0 - outline * clamp(e * 6.0, 0.0, 1.0) * (1.0 - blur);
          gl_FragColor = color;
        }`,
    });
    this.quad = new FullScreenQuad(this.material);
  }

  setSize(width, height) {
    const w = Math.max(1, Math.floor(width / this.pixelSize));
    const h = Math.max(1, Math.floor(height / this.pixelSize));
    this.target.setSize(w, h);
    this.material.uniforms.texel.value.set(1 / w, 1 / h);
  }

  render(renderer, writeBuffer) {
    if (!this.scene || !this.camera) return;
    renderer.setRenderTarget(this.target);
    renderer.clear();
    renderer.render(this.scene, this.camera);

    const u = this.material.uniforms;
    u.tColor.value = this.target.texture;
    u.tDepth.value = this.target.depthTexture;
    u.cameraNear.value = this.camera.near;
    u.cameraFar.value = this.camera.far;
    u.outline.value = this.outline;
    u.focusDistance.value = this.focusDistance;
    u.focusRange.value = this.focusRange;
    u.maxBlur.value = this.maxBlur;
    renderer.setRenderTarget(this.renderToScreen ? null : writeBuffer);
    this.quad.render(renderer);
  }

  dispose() {
    this.target.dispose();
    this.material.dispose();
    this.quad.dispose();
  }
}
