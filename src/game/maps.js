/**
 * Cartes du monde, chacune exportée de Blender (tools/blender/build_scenes.py).
 * `outdoor` : ciel et soleil ; sinon intérieur sur fond noir avec une caméra plus proche.
 * `label` : nom affiché en entrant (les extérieurs utilisent leurs zones Area_*).
 * `grid` : grille de cases (collisions, relief, herbes hautes, fleurs ; voir engine/tiles.js).
 */
export const MAPS = {
  'route-01': { file: '/assets/scenes/route-01.glb', grid: '/assets/scenes/route-01.json', outdoor: true },
  center: { file: '/assets/scenes/center.glb', outdoor: false, label: 'CENTRE POKéMON' },
};
