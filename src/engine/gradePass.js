import { ShaderPass } from 'three/addons/postprocessing/ShaderPass.js';

/** Étalonnage final (après OutputPass, donc en sRGB) : saturation, contraste, teinte chaude, vignette. */
export function createGradePass({ saturation = 1.12, contrast = 1.06, warmth = 0.03, vignette = 0.28 } = {}) {
  return new ShaderPass({
    uniforms: {
      tDiffuse: { value: null },
      saturation: { value: saturation },
      contrast: { value: contrast },
      warmth: { value: warmth },
      vignette: { value: vignette },
    },
    vertexShader: /* glsl */ `
      varying vec2 vUv;
      void main() {
        vUv = uv;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      }`,
    fragmentShader: /* glsl */ `
      uniform sampler2D tDiffuse;
      uniform float saturation;
      uniform float contrast;
      uniform float warmth;
      uniform float vignette;
      varying vec2 vUv;

      void main() {
        vec3 c = texture2D(tDiffuse, vUv).rgb;
        float luma = dot(c, vec3(0.2126, 0.7152, 0.0722));
        c = mix(vec3(luma), c, saturation);
        c = (c - 0.5) * contrast + 0.5;
        c *= vec3(1.0 + warmth, 1.0, 1.0 - warmth);
        float d = distance(vUv, vec2(0.5));
        c *= 1.0 - vignette * smoothstep(0.35, 0.85, d);
        gl_FragColor = vec4(clamp(c, 0.0, 1.0), 1.0);
      }`,
  });
}
