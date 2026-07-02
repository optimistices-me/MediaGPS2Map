/**
 * requestAnimationFrame-based playback along sorted trajectory points.
 * @module animation
 */

import { state } from './state.js';
import { toUTC8 } from './geo_utils.js';

const infoTime = document.getElementById('infoTime');
const infoLocation = document.getElementById('infoLocation');

let isProgressDragging = false;

function animateSegment(from, to, duration, onStep, onEnd) {
  const start = performance.now();

  function step(now) {
    if (state.isPaused) return;
    const t = Math.min((now - start) / duration, 1);
    const lat = from.lat + (to.lat - from.lat) * t;
    const lng = from.lng + (to.lng - from.lng) * t;
    onStep({ lat, lng });
    if (t < 1) {
      requestAnimationFrame(step);
    } else {
      onEnd();
    }
  }

  requestAnimationFrame(step);
}

function playNext(idx) {
  if (idx >= state.animationPoints.length - 1) return;

  const curr = state.animationPoints[idx];
  const next = state.animationPoints[idx + 1];
  const delta = new Date(next.timestamp) - new Date(curr.timestamp);

  const duration =
    document.getElementById('modeRatio')?.checked
      ? delta / parseInt(document.getElementById('animationRatio').value, 10)
      : 1000 / parseInt(document.getElementById('animationSpeed').value, 10);

  animateSegment(
    curr,
    next,
    duration,
    (pos) => state.animationMarker.setLatLng([pos.lat, pos.lng]),
    () => {
      const pct = Math.round(((idx + 1) / state.animationPoints.length) * 100);
      if (!isProgressDragging) {
        document.getElementById('animationTimeProgress').value = pct;
        document.getElementById('progressLabel').textContent = pct + '%';
      }
      infoTime.textContent = toUTC8(next.timestamp);
      infoLocation.textContent = next.address || '未知地址';
      state.currentAnimationIndex = idx + 1;
      if (!state.isPaused) playNext(idx + 1);
    }
  );
}

/** Begin playback. */
export function startAnimation() {
  document.getElementById('animationInfo').style.display = 'block';

  const range = getActiveTimeRange();
  if (!range) return;

  const startTime = new Date(range.start);
  const endTime = new Date(range.end);

  state.animationPoints = (state.currentPoints || [])
    .filter((pt) => {
      const t = new Date(pt.timestamp);
      return t >= startTime && t <= endTime;
    })
    .sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));

  if (state.animationPoints.length === 0) return;

  state.currentAnimationIndex = 0;

  if (!state.animationMarker) {
    state.animationMarker = L.circleMarker([0, 0], {
      radius: 8,
      fillColor: '#0000FF',
      color: '#0000FF',
      weight: 2,
      opacity: 1,
      fillOpacity: 0.8,
    }).addTo(state.map);
  }

  state.isPaused = false;
  playNext(0);
}

/** Stop and clean up. */
export function stopAnimation() {
  document.getElementById('animationInfo').style.display = 'none';
  if (state.animationMarker) {
    state.map.removeLayer(state.animationMarker);
    state.animationMarker = null;
  }
  state.animationPoints = [];
  state.currentAnimationIndex = 0;
}

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

/** Bind animation UI controls. */
export function initAnimation() {
  const progEl = document.getElementById('animationTimeProgress');

  progEl.addEventListener('mousedown', () => (isProgressDragging = true));
  progEl.addEventListener('mouseup', () => (isProgressDragging = false));
  progEl.addEventListener('input', (e) => {
    state.isPaused = true;
    const pct = e.target.value / 100;
    state.currentAnimationIndex = Math.floor(
      pct * (state.animationPoints.length - 1)
    );
    if (state.animationPoints.length > 0) {
      const pt = state.animationPoints[state.currentAnimationIndex];
      state.animationMarker.setLatLng([pt.lat, pt.lng]);
    }
    document.getElementById('progressLabel').textContent =
      Math.round(pct * 100) + '%';
  });

  document.getElementById('btnPlay').addEventListener('click', () => {
    state.isPaused = false;
    playNext(state.currentAnimationIndex);
  });
  document.getElementById('btnPause').addEventListener('click', () => {
    state.isPaused = true;
  });
  document.getElementById('btnRewind').addEventListener('click', () => {
    state.isPaused = true;
    state.currentAnimationIndex = Math.max(
      0,
      state.currentAnimationIndex -
        Math.floor(state.animationPoints.length * 0.05)
    );
    const pt = state.animationPoints[state.currentAnimationIndex];
    state.animationMarker?.setLatLng([pt.lat, pt.lng]);
    progEl.value = Math.round(
      (state.currentAnimationIndex / (state.animationPoints.length - 1)) * 100
    );
    document.getElementById('progressLabel').textContent = progEl.value + '%';
  });
  document.getElementById('btnForward').addEventListener('click', () => {
    state.isPaused = true;
    state.currentAnimationIndex = Math.min(
      state.animationPoints.length - 1,
      state.currentAnimationIndex +
        Math.floor(state.animationPoints.length * 0.05)
    );
    const pt = state.animationPoints[state.currentAnimationIndex];
    state.animationMarker?.setLatLng([pt.lat, pt.lng]);
    progEl.value = Math.round(
      (state.currentAnimationIndex / (state.animationPoints.length - 1)) * 100
    );
    document.getElementById('progressLabel').textContent = progEl.value + '%';
  });
  document.getElementById('btnStop').addEventListener('click', () => {
    state.isPaused = true;
    stopAnimation();
    document.getElementById('animationSwitch').checked = false;
    state.isAnimationPlaying = false;
    progEl.value = 0;
    document.getElementById('progressLabel').textContent = '0%';
  });
}
