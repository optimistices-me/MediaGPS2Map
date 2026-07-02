/**
 * Daily trajectory polylines with arrowhead markers.
 * @module tracks
 */

import { state } from './state.js';

/**
 * Deterministic HSL colour derived from a date string.
 * @param {string} dateStr  e.g. "2025-04-01"
 * @returns {string}
 */
function getColorForDate(dateStr) {
  const hash = dateStr.split('-').reduce((acc, cur) => acc + parseInt(cur, 10), 0);
  return `hsl(${(hash * 137) % 360}, 70%, 50%)`;
}

/** Remove all existing track layers from the map. */
export function clearTracks() {
  state.trackLayers.forEach((layer) => state.map.removeLayer(layer));
  state.trackLayers = [];
}

/** Render per-day trajectory polylines from the current points. */
export function renderTracks() {
  clearTracks();
  if (state.showMode !== 'trajectory') return;

  const bounds = state.map.getBounds();

  // Group visible points by day
  const dailyGroups = (state.currentPoints || []).reduce(
    (acc, pt) => {
      if (bounds.contains([pt.lat, pt.lng])) {
        const date = pt.timestamp.split('T')[0];
        if (!acc[date]) acc[date] = [];
        acc[date].push(pt);
      }
      return acc;
    },
    /** @type {Record<string, Array>} */ ({})
  );

  Object.entries(dailyGroups).forEach(([date, pts]) => {
    if (pts.length < 2) return;

    const sorted = pts.sort(
      (a, b) => new Date(a.timestamp) - new Date(b.timestamp)
    );

    const polyline = L.polyline(
      sorted.map((p) => [p.lat, p.lng]),
      {
        color: getColorForDate(date),
        weight: 3,
        arrowheads: { frequency: '50px', size: '15px', fill: true, yawn: 60 },
      }
    );

    polyline.addTo(state.map);
    state.trackLayers.push(polyline);
  });
}

/** Inverse of updateHeatmap — clears and re-renders tracks. */
export function updateTracks() {
  renderTracks();
}
