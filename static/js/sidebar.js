/**
 * Sidebar panel: statistics, frequent locations, lock-track, speed controls.
 * @module sidebar
 */

import { state } from './state.js';
import { wgs84ToGcj02 } from './geo_utils.js';
import { startAnimation, stopAnimation } from './animation.js';
import { setDisplayMode } from './main.js';

const addressCache = new Map();
const MAX_CACHE = 200;

/** Update stats UI from a data response. */
export function updateSidebar(data) {
  const points = data.points || [];
  const totalCount = data.total_count !== undefined ? data.total_count : points.length;

  document.getElementById('file-count').textContent = totalCount;

  if (points.length > 0) {
    const times = points.map((p) => new Date(p.timestamp).getTime());
    const min = new Date(Math.min(...times)).toLocaleString();
    const max = new Date(Math.max(...times)).toLocaleString();
    document.getElementById('time-range').textContent = `${min} - ${max}`;
  } else {
    document.getElementById('time-range').textContent = '无';
  }

  // Debounced frequent-location analysis
  clearTimeout(window._freqTimeout);
  window._freqTimeout = setTimeout(() => analyzeFrequentLocations(points), 300);
}

/**
 * Grid-cluster visible points and show top-5 locations via AMap reverse geocoding.
 * @param {Array} points
 */
async function analyzeFrequentLocations(points) {
  const listEl = document.getElementById('sample-locations');
  if (!points.length) {
    listEl.innerHTML = '<li>当前区域无数据</li>';
    return;
  }

  const bounds = state.map.getBounds();
  const visible = points.filter((p) => bounds.contains([p.lat, p.lng]));
  if (!visible.length) {
    listEl.innerHTML = '<li>当前显示区域无数据</li>';
    return;
  }

  const gridSize = 0.005;
  const clusters = {};
  visible.forEach((p) => {
    const k = `${Math.floor(p.lat / gridSize) * gridSize},${Math.floor(p.lng / gridSize) * gridSize}`;
    if (!clusters[k]) {
      clusters[k] = { lat: 0, lng: 0, count: 0 };
    }
    clusters[k].lat += p.lat;
    clusters[k].lng += p.lng;
    clusters[k].count++;
  });

  const top = Object.values(clusters)
    .sort((a, b) => b.count - a.count)
    .slice(0, 5);

  // Average cluster centres
  top.forEach((c) => {
    c.lat /= c.count;
    c.lng /= c.count;
  });

  listEl.innerHTML = '<li>正在分析常去位置...</li>';

  const results = await Promise.all(
    top.map(async (loc) => {
      const key = `${loc.lat.toFixed(3)},${loc.lng.toFixed(3)}`;
      const cached = addressCache.get(key);
      if (cached) return { ...cached, count: loc.count };

      try {
        const [gcjLat, gcjLng] = wgs84ToGcj02(loc.lat, loc.lng);
        const resp = await fetch(`/api/regeo?lng=${gcjLng}&lat=${gcjLat}`);
        const data = await resp.json();
        let address = `经度 ${loc.lat.toFixed(4)}, 纬度 ${loc.lng.toFixed(4)}`;
        if (data.status === '1' && data.regeocode?.formatted_address) {
          address = data.regeocode.formatted_address;
          if (address.length > 30) address = address.slice(0, 30) + '…';
        }
        const result = { address, count: loc.count };
        addressCache.set(key, result);
        if (addressCache.size > MAX_CACHE) {
          const first = addressCache.keys().next().value;
          addressCache.delete(first);
        }
        return result;
      } catch {
        return { address: `经度 ${loc.lat.toFixed(4)}, 纬度 ${loc.lng.toFixed(4)}`, count: loc.count };
      }
    })
  );

  listEl.innerHTML = results
    .map((r) => `<li>${r.address} <span style="color: #666;">(${r.count}次)</span></li>`)
    .join('');
}

/** Wire sidebar controls (lock, speed, animation toggle). */
export function initSidebar() {
  document.getElementById('lockTrackSwitch').addEventListener('change', (e) => {
    state.isTrackLocked = e.target.checked;
  });

  const syncSpeed = () => {
    const slider = document.getElementById('animationSpeed');
    const number = document.getElementById('animationSpeed-value');
    number.value = slider.value;
    if (state.isAnimationPlaying) {
      stopAnimation();
      startAnimation();
    }
  };

  document.getElementById('animationSpeed').addEventListener('input', syncSpeed);
  document.getElementById('animationSpeed-value').addEventListener('input', (e) => {
    document.getElementById('animationSpeed').value = e.target.value;
    if (state.isAnimationPlaying) {
      stopAnimation();
      startAnimation();
    }
  });

  // Speed mode tabs
  document.getElementById('modeFPS').addEventListener('change', () => {
    document.querySelector('.speed-tab[for="modeFPS"]').classList.add('active');
    document.querySelector('.speed-tab[for="modeRatio"]').classList.remove('active');
    document.getElementById('speed-fps').style.display = 'flex';
    document.getElementById('speed-ratio').style.display = 'none';
  });
  document.getElementById('modeRatio').addEventListener('change', () => {
    document.querySelector('.speed-tab[for="modeRatio"]').classList.add('active');
    document.querySelector('.speed-tab[for="modeFPS"]').classList.remove('active');
    document.getElementById('speed-ratio').style.display = 'flex';
    document.getElementById('speed-fps').style.display = 'none';
  });

  document.getElementById('animationSwitch').addEventListener('change', (e) => {
    if (e.target.checked && state.showMode !== 'trajectory') {
      setDisplayMode('trajectory');
    }
    state.isAnimationPlaying = e.target.checked;
    if (state.isAnimationPlaying) startAnimation();
    else stopAnimation();
  });
}

// setDisplayMode is imported from main.js
