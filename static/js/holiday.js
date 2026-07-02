/**
 * Holiday detection popover — fetches /api/holidays and renders clickable buttons.
 * @module holiday
 */

import { updateTimeRange } from './timeline.js';
import { startAnimation } from './animation.js';

/** Bind holiday button. */
export function initHoliday() {
  document.getElementById('holidayBtn').addEventListener('click', () => {
    const popover = document.getElementById('holiday-popover');
    if (popover.style.display === 'block') {
      popover.style.display = 'none';
    } else {
      loadHolidayData();
      popover.style.display = 'block';
    }
  });

  document.addEventListener('click', (e) => {
    const popover = document.getElementById('holiday-popover');
    const btn = document.getElementById('holidayBtn');
    if (popover.style.display === 'block' && !popover.contains(e.target) && e.target !== btn) {
      popover.style.display = 'none';
    }
  });
}

async function loadHolidayData() {
  const listEl = document.getElementById('holiday-list');
  listEl.innerHTML = '<div style="padding:5px;color:#666;">正在加载…</div>';

  try {
    const resp = await fetch('/api/holidays');
    const data = await resp.json();
    const holidays = data.holidays || [];

    if (!holidays.length) {
      listEl.innerHTML = '<div style="padding:5px;color:#666;">未检测到节假日轨迹</div>';
      return;
    }

    listEl.innerHTML = '';
    holidays.forEach((h) => {
      const btn = document.createElement('button');
      btn.className = 'holiday-btn';
      btn.textContent = `${h.name}: ${h.start} ~ ${h.end} (${h.photo_count}张)`;
      btn.title = `官方假期: ${h.official_start} ~ ${h.official_end}`;
      btn.addEventListener('click', async (e) => {
        e.stopPropagation();
        document.getElementById('start-time').value = h.start + 'T00:00';
        document.getElementById('end-time').value = h.end + 'T23:59';
        document.getElementById('holiday-popover').style.display = 'none';
        await updateTimeRange();
        document.getElementById('animationSwitch').checked = true;
        // Will be handled by switch change event
      });
      listEl.appendChild(btn);
    });
  } catch (err) {
    listEl.innerHTML = '<div style="padding:5px;color:#c00;">加载失败</div>';
  }
}
