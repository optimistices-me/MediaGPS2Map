/**
 * Heatmap layer (Leaflet.heat) controls and gradient management.
 * @module heatmap
 */

import { state } from './state.js';

/** @type {import('./state.js').HeatmapParams} */
const params = {
  radius: 4,
  blur: 2,
  minOpacity: 0.4,
  gradient: {
    0.1: 'rgba(0, 0, 255, 0.9)',
    0.5: 'rgba(255, 255, 0, 0.6)',
    1.0: 'rgba(255, 0, 0, 0.2)',
  },
};

function hexToRgb(hex) {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `${r}, ${g}, ${b}`;
}

/** Re-create or update the heatmap layer from current state points. */
export function updateHeatmap() {
  const pts = (state.currentPoints || []).map((p) => [p.lat, p.lng, 1]);

  params.radius = parseInt(document.getElementById('radius').value, 10);
  params.blur = parseInt(document.getElementById('blur').value, 10);
  params.minOpacity = parseFloat(document.getElementById('minOpacity').value);
  params.gradient = {
    0.1: `rgba(${hexToRgb(document.getElementById('lowColor').value)}, ${parseFloat(document.getElementById('lowOpacity').value)})`,
    0.5: `rgba(${hexToRgb(document.getElementById('midColor').value)}, ${parseFloat(document.getElementById('midOpacity').value)})`,
    1.0: `rgba(${hexToRgb(document.getElementById('highColor').value)}, ${parseFloat(document.getElementById('highOpacity').value)})`,
  };

  if (state.heatmapLayer) {
    state.heatmapLayer.setLatLngs(pts);
    state.heatmapLayer.setOptions(params);
  } else {
    state.heatmapLayer = L.heatLayer(pts, params).addTo(state.map);
  }
}

/** Wire up heatmap control inputs. */
export function initHeatmap() {
  const bind = (id, event = 'input') => {
    const el = document.getElementById(id);
    if (el) el.addEventListener(event, updateHeatmap);
  };

  bind('radius');
  bind('blur');
  bind('minOpacity');
  bind('radius-value');
  bind('blur-value');
  bind('minOpacity-value');
  bind('lowColor');
  bind('midColor');
  bind('highColor');
  bind('lowOpacity');
  bind('midOpacity');
  bind('highOpacity');
}
