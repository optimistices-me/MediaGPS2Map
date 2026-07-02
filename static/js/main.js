/**
 * GPS2Map — Main entry point.
 * Initialises the map, wires up all modules, and starts data loading.
 * @module main
 */

import { state } from './state.js';
import { wgs84ToGcj02, toUTC8 } from './geo_utils.js';
import { initHeatmap, updateHeatmap } from './heatmap.js';
import { renderTracks } from './tracks.js';
import { initAnimation, startAnimation, stopAnimation } from './animation.js';
import { initTimeRange, initTimeline, updateTimeRange } from './timeline.js';
import { initSidebar, updateSidebar } from './sidebar.js';
import { initHoliday } from './holiday.js';

// ---------------------------------------------------------------------------
// Map initialisation
// ---------------------------------------------------------------------------

state.map = L.map('map').setView([30, 120], 3);

const osmLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(state.map);
const amapLayer = L.tileLayer(
  'https://webrd0{s}.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}',
  { subdomains: ['1', '2', '3', '4'], maxZoom: 18 }
);

// ---------------------------------------------------------------------------
// Data loading
// ---------------------------------------------------------------------------

let debounceTimeout = null;

function loadDataForBounds(bounds, shouldUpdateTimeRange) {
  if (state.isTrackLocked) return;

  const params = new URLSearchParams({
    bounds: `${bounds.getSouth()},${bounds.getWest()},${bounds.getNorth()},${bounds.getEast()}`,
    start: document.getElementById('start-time').value,
    end: document.getElementById('end-time').value,
    zoom: state.map.getZoom(),
  });

  fetch(`/data?${params}`)
    .then((r) => r.json())
    .then((data) => {
      state.currentPoints = data.points;
      if (shouldUpdateTimeRange) initTimeRange();
      updateHeatmap();
      renderTracks();
      updateSidebar(data);
    });
}

// ---------------------------------------------------------------------------
// Map events
// ---------------------------------------------------------------------------

state.map.on('moveend', () => {
  clearTimeout(debounceTimeout);
  debounceTimeout = setTimeout(() => {
    if (!state.isTrackLocked) loadDataForBounds(state.map.getBounds(), false);
  }, 200);
});

state.map.on('click', (e) => {
  const { lat, lng } = e.latlng;
  const range = getActiveTimeRange();
  let search = state.currentPoints;
  if (range) {
    const s = new Date(range.start);
    const en = new Date(range.end);
    search = state.currentPoints.filter((p) => {
      const t = new Date(p.timestamp);
      return t >= s && t <= en;
    });
  }

  let closest = null;
  let minDist = Infinity;
  search.forEach((p) => {
    const d = Math.hypot(p.lat - lat, p.lng - lng);
    if (d < minDist) {
      minDist = d;
      closest = p;
    }
  });

  if (!closest) return;

  const [gcjLat, gcjLng] = wgs84ToGcj02(closest.lat, closest.lng);
  fetch(`/api/regeo?lng=${gcjLng}&lat=${gcjLat}`)
    .then((r) => r.json())
    .then((data) => {
      let address = '';
      if (data.status === '1' && data.regeocode?.formatted_address) {
        address = data.regeocode.formatted_address;
      }
      L.popup()
        .setLatLng([closest.lat, closest.lng])
        .setContent(
          `<b>文件路径:</b> ${closest.path}<br>` +
          `<b>拍摄时间:</b> ${toUTC8(closest.timestamp)}<br>` +
          (closest.altitude ? `<b>海拔:</b> ${closest.altitude}米<br>` : '') +
          `<b>地址:</b> ${address}`
        )
        .openOn(state.map);
    });
});

// ---------------------------------------------------------------------------
// Display mode toggle (heatmap / trajectory)
// ---------------------------------------------------------------------------

export function setDisplayMode(mode) {
  state.showMode = mode;
  document.getElementById('displayModeSwitch').checked = mode === 'heatmap';
  document.querySelectorAll('.mode-toggle .mode-label').forEach((l) =>
    l.classList.toggle('active', l.dataset.mode === mode)
  );
  document.getElementById('trajectory-card').style.display =
    mode === 'trajectory' ? 'block' : 'none';
  renderTracks();
}

document.querySelectorAll('.mode-toggle .mode-label').forEach((label) => {
  label.addEventListener('click', () => setDisplayMode(label.dataset.mode));
});

document.getElementById('displayModeSwitch').addEventListener('change', (e) => {
  setDisplayMode(e.target.checked ? 'heatmap' : 'trajectory');
});

setDisplayMode('heatmap');

// ---------------------------------------------------------------------------
// Map source (OSM / AMap)
// ---------------------------------------------------------------------------

document.getElementById('mapOSM').addEventListener('change', () => {
  document.querySelector('.map-source-tabs .speed-tab[for="mapOSM"]').classList.add('active');
  document.querySelector('.map-source-tabs .speed-tab[for="mapAmap"]').classList.remove('active');
  state.map.removeLayer(amapLayer);
  state.map.addLayer(osmLayer);
});

document.getElementById('mapAmap').addEventListener('change', () => {
  document.querySelector('.map-source-tabs .speed-tab[for="mapAmap"]').classList.add('active');
  document.querySelector('.map-source-tabs .speed-tab[for="mapOSM"]').classList.remove('active');
  state.map.removeLayer(osmLayer);
  state.map.addLayer(amapLayer);
});

// ---------------------------------------------------------------------------
// Sidebar resize
// ---------------------------------------------------------------------------

const sb = document.getElementById('sidebar');
const handle = document.getElementById('resizeHandle');
let resizing = false;
let startX, startWidth;

handle.addEventListener('mousedown', (e) => {
  resizing = true;
  startX = e.clientX;
  startWidth = sb.offsetWidth;
  handle.classList.add('active');
  document.body.style.userSelect = 'none';
  document.body.style.cursor = 'ew-resize';
  e.preventDefault();
});

document.addEventListener('mousemove', (e) => {
  if (!resizing) return;
  const newWidth = startWidth + (startX - e.clientX);
  sb.style.width = `${Math.min(520, Math.max(280, newWidth))}px`;
});

document.addEventListener('mouseup', () => {
  if (!resizing) return;
  resizing = false;
  handle.classList.remove('active');
  document.body.style.userSelect = '';
  document.body.style.cursor = '';
  state.map.invalidateSize();
});

// ---------------------------------------------------------------------------
// Sub-module init
// ---------------------------------------------------------------------------

initHeatmap();
initTimeline();
initAnimation();
initSidebar();
initHoliday();

// Local helper used by click handler
function getActiveTimeRange() {
  const isSingle = document.getElementById('modeSingle')?.checked;
  let start, end;
  if (isSingle) {
    const dateStr = document.getElementById('single-date').value;
    if (!dateStr) return null;
    start = dateStr + 'T00:00';
    end = dateStr + 'T23:59';
  } else {
    start = document.getElementById('start-time').value;
    end = document.getElementById('end-time').value;
  }
  return { start, end };
}

// Kick off data load
loadDataForBounds(state.map.getBounds(), true);
