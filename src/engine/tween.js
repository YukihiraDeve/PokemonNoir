export const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

/** Appelle step(t) avec t de 0 à 1 pendant `ms` millisecondes, puis résout la promesse. */
export function animate(ms, step) {
  return new Promise((resolve) => {
    const start = performance.now();
    const frame = (now) => {
      const t = Math.min(1, (now - start) / ms);
      step(t);
      if (t < 1) requestAnimationFrame(frame);
      else resolve();
    };
    requestAnimationFrame(frame);
  });
}

export const easeOut = (t) => 1 - (1 - t) ** 3;
export const easeInOut = (t) => (t < 0.5 ? 4 * t ** 3 : 1 - (-2 * t + 2) ** 3 / 2);
