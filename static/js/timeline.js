/**
 * Dual-handle time range slider, single-day date picker, and mode toggle.
 * @module timeline
 */

import { state } from './state.js';
import { renderTracks } from './tracks.js';
import { updateHeatmap } from './heatmap.js';
import { updateSidebar } from './sidebar.js';
import { startAnimation, stopAnimation } from './animation.js';

/** Initialise min/max timestamps from currentPoints and reset UI. */
export function initTimeRange() {
  const timestamps = (state.currentPoints || []).map(
    (p) => new Date(p.timestamp).getTime()
  );
  if (!timestamps.length) return;

  const min = Math.min(...timestamps);
  const max = Math.max(...timestamps);
  state.initialStartTime = min;
  state.initialEndTime = max;

  const fmt = (t) => new Date(t).toISOString().slice(0, 16);
  const fmtDate = (t) => new Date(t).toISOString().slice(0, 10);

  document.getElementById('start-time').value = fmt(min);
  document.getElementById('end-time').value = fmt(max);
  document.getElementById('single-date').value = fmtDate(min);
  document.getElementById('start-time').min = fmt(min);
  document.getElementById('start-time').max = fmt(max);
  document.getElementById('end-time').min = fmt(min);
  document.getElementById('end-time').max = fmt(max);
  document.getElementById('single-date').min = fmtDate(min);
  document.getElementById('single-date').max = fmtDate(max);

  document.getElementById('timeline-handle-start').style.left = '0%';
  document.getElementById('timeline-handle-end').style.left = '100%';
}

/** Get the active time range from whichever mode is selected. */
export function getActiveTimeRange() {
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

/**
 * Reload data (or filter locally if track is locked) when time range changes.
 * @returns {Promise<void>}
 */
export async function updateTimeRange() {
  const range = getActiveTimeRange();
  if (!range) return;

  // Local filtering when track is locked
  if (state.isTrackLocked) {
    const filtered = (state.currentPoints || []).filter((pt) => {
      const t = new Date(pt.timestamp);
      return t >= new Date(range.start) && t <= new Date(range.end);
    });
    state.currentPoints = filtered;
    updateHeatmap();
    renderTracks();
    updateSidebar({ points: filtered, addresses: [], total_count: filtered.length });
    return;
  }

  // Fetch from server
  const bounds = state.map.getBounds();
  const params = new URLSearchParams({
    bounds: `${bounds.getSouth()},${bounds.getWest()},${bounds.getNorth()},${bounds.getEast()}`,
    start: range.start,
    end: range.end,
    zoom: state.map.getZoom(),
  });

  const resp = await fetch(`/data?${params}`);
  const data = await resp.json();

  state.currentPoints = data.points;
  updateHeatmap();
  renderTracks();
  updateSidebar(data);

  if (state.isAnimationPlaying) {
    stopAnimation();
    startAnimation();
  }
}

/** Bind all timeline-related UI controls. */
export function initTimeline() {
  const handleStart = document.getElementById('timeline-handle-start');
  const handleEnd = document.getElementById('timeline-handle-end');
  const timeline = document.getElementById('timeline');
  let isDragging = false;
  let currentHandle = null;

  document.getElementById('timeline-container').addEventListener('mousedown', (e) => {
    isDragging = true;
    const rect = timeline.getBoundingClientRect();
    const pct = (e.clientX - rect.left) / rect.width;
    if (Math.abs(pct * 100 - parseFloat(handleStart.style.left)) < 10) {
      currentHandle = handleStart;
    } else if (Math.abs(pct * 100 - parseFloat(handleEnd.style.left)) < 10) {
      currentHandle = handleEnd;
    }
  });

  document.addEventListener('mousemove', (e) => {
    if (!isDragging || !currentHandle) return;
    const rect = timeline.getBoundingClientRect();
    const x = Math.max(0, Math.min(e.clientX - rect.left, rect.width));
    const pct = (x / rect.width) * 100;
    currentHandle.style.left = `${pct}%`;

    const base = state.initialStartTime || 0;
    const range = (state.initialEndTime || 0) - base;
    const currentTime = base + (pct / 100) * range;

    if (currentHandle === handleStart) {
      document.getElementById('start-time').value = new Date(currentTime).toISOString().slice(0, 16);
    } else {
      document.getElementById('end-time').value = new Date(currentTime).toISOString().slice(0, 16);
    }
  });

  document.addEventListener('mouseup', () => {
    if (!isDragging) return;
    isDragging = false;
    currentHandle = null;
    updateTimeRange();
  });

  document.getElementById('start-time').addEventListener('change', updateTimeRange);
  document.getElementById('end-time').addEventListener('change', updateTimeRange);
  document.getElementById('single-date').addEventListener('change', updateTimeRange);

  // Range / Single-day mode tabs
  const tabRange = document.querySelector('.date-mode-tabs .speed-tab[for="modeRange"]');
  const tabSingle = document.querySelector('.date-mode-tabs .speed-tab[for="modeSingle"]');
  document.getElementById('modeRange').addEventListener('change', () => {
    tabRange.classList.add('active');
    tabSingle.classList.remove('active');
    document.getElementById('range-date-picker').style.display = 'flex';
    document.getElementById('single-date-picker').style.display = 'none';
    document.getElementById('timeline-container').style.display = 'block';
    updateTimeRange();
  });
  document.getElementById('modeSingle').addEventListener('change', () => {
    tabSingle.classList.add('active');
    tabRange.classList.remove('active');
    document.getElementById('single-date-picker').style.display = 'flex';
    document.getElementById('range-date-picker').style.display = 'none';
    document.getElementById('timeline-container').style.display = 'none';
    updateTimeRange();
  });

  // Reset buttons
  document.getElementById('reset-time').addEventListener('click', () => {
    document.getElementById('start-time').value = new Date(state.initialStartTime).toISOString().slice(0, 16);
    document.getElementById('end-time').value = new Date(state.initialEndTime).toISOString().slice(0, 16);
    handleStart.style.left = '0%';
    handleEnd.style.left = '100%';
    updateTimeRange();
  });

  document.getElementById('reset-time-single').addEventListener('click', () => {
    document.getElementById('single-date').value = new Date(state.initialStartTime).toISOString().slice(0, 10);
    updateTimeRange();
  });
}
