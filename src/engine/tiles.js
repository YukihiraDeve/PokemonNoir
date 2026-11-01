import * as THREE from 'three';

/**
 * Grille de cases exportée par tools/blender/build_scenes.py (une case Noir & Blanc = 1,25 m) :
 * Arabelle au nord, puis la Route 1 et Renouet. Repère Three.js : la colonne c couvre
 * x ∈ [originX + c·tile, +tile], la ligne r couvre z ∈ [originZ + r·tile, +tile] (les lignes
 * descendent vers le sud, comme sur les captures).
 *
 * Lettres : T forêt, . herbe, S sable, H herbes hautes, F/f fleurs roses, w fleurs blanches,
 * W eau, C falaise ou talus, l contrebas, R escalier en bois, B bâtiment ; à Arabelle, P dalles,
 * K muret ou rambarde, X sol fermé, E escalier de pierre.
 * Hauteurs (`heights`) : par case, un nombre si elle est plate, sinon ses quatre coins
 * [nord-ouest, nord-est, sud-ouest, sud-est] (pentes, escaliers). Entre deux cases de niveaux
 * différents, le décor dresse un mur et une case infranchissable empêche d'y tomber.
 */
export function createTileMap(data) {
  const { tile, originX, originZ, cols, rows, grid, heights } = data;
  const blocking = new Set(data.blocking);
  const cell = (x, z) => [Math.floor((x - originX) / tile), Math.floor((z - originZ) / tile)];
  const inside = (c, r) => c >= 0 && r >= 0 && c < cols && r < rows;
  const at = (c, r) => (inside(c, r) ? grid[r][c] : null);

  return {
    tile,
    cols,
    rows,
    town: data.town ?? 0, // lignes d'Arabelle, en haut de la grille
    originX,
    originZ,
    cell,
    at,
    tileAt: (x, z) => at(...cell(x, z)),
    /** Rectangle (x, z) d'une case, pour les collisions. */
    box: (c, r) => ({ minX: originX + c * tile, maxX: originX + (c + 1) * tile, minZ: originZ + r * tile, maxZ: originZ + (r + 1) * tile }),
    // À l'est et à l'ouest de la grille, c'est la forêt ; au nord et au sud, les bornes de la carte.
    blocked: (c, r) => r >= 0 && r < rows && (!inside(c, r) || blocking.has(grid[r][c])),
    /** Hauteur du sol : interpolée entre les coins de la case (0 hors de la grille). */
    heightAt(x, z) {
      const fc = (x - originX) / tile;
      const fr = (z - originZ) / tile;
      if (fc < 0 || fr < 0 || fc >= cols || fr >= rows) return 0;
      const h = heights[Math.floor(fr)][Math.floor(fc)];
      if (typeof h === 'number') return h;
      const t = fc - Math.floor(fc);
      const u = fr - Math.floor(fr);
      const top = THREE.MathUtils.lerp(h[0], h[1], t);
      const bottom = THREE.MathUtils.lerp(h[2], h[3], t);
      return THREE.MathUtils.lerp(top, bottom, u);
    },
    /** Toutes les cases portant une des lettres, avec leur centre (x, z). */
    cells(letters) {
      const out = [];
      for (let r = 0; r < rows; r++) {
        for (let c = 0; c < cols; c++) {
          if (letters.includes(grid[r][c])) out.push({ c, r, ch: grid[r][c], x: originX + (c + 0.5) * tile, z: originZ + (r + 0.5) * tile });
        }
      }
      return out;
    },
  };
}
