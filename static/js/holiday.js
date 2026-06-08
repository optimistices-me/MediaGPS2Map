let holidayEnabled = false;

function initHoliday() {
    document.getElementById('holidaySwitch').addEventListener('change', function (e) {
        holidayEnabled = e.target.checked;
        if (holidayEnabled) {
            loadHolidayData();
        } else {
            document.getElementById('holiday-list').innerHTML = '';
        }
    });
}

function loadHolidayData() {
    const listEl = document.getElementById('holiday-list');
    listEl.innerHTML = '<div style="padding:5px;color:#666;">正在加载节假日数据...</div>';

    fetch('/api/holidays')
        .then(response => response.json())
        .then(data => {
            const holidays = data.holidays || [];
            if (holidays.length === 0) {
                listEl.innerHTML = '<div style="padding:5px;color:#666;">未检测到节假日轨迹</div>';
                return;
            }

            listEl.innerHTML = '';
            holidays.forEach(h => {
                const btn = document.createElement('button');
                btn.className = 'holiday-btn';
                btn.textContent = `${h.name}: ${h.start} ~ ${h.end} (${h.photo_count}张)`;
                btn.title = `官方假期: ${h.official_start} ~ ${h.official_end}`;
                btn.addEventListener('click', () => {
                    document.getElementById('start-time').value = h.start + 'T00:00';
                    document.getElementById('end-time').value = h.end + 'T23:59';

                    const handleStart = document.getElementById('timeline-handle-start');
                    const handleEnd = document.getElementById('timeline-handle-end');
                    handleStart.style.left = '0%';
                    handleEnd.style.left = '100%';

                    updateTimeRange().then(() => {
                        document.getElementById('animationSwitch').checked = true;
                        isAnimationPlaying = true;
                        startAnimation();
                    });
                });
                listEl.appendChild(btn);
            });
        })
        .catch(error => {
            console.error('节假日数据加载失败:', error);
            listEl.innerHTML = '<div style="padding:5px;color:#c00;">加载失败，请重试</div>';
        });
}
