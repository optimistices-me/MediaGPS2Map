let startTime = null;
let endTime = null;
let initialStartTime = null;
let initialEndTime = null;
let isDragging = false;
let currentHandle = null;

function initTimeRange() {
    const timestamps = currentPoints.map(p => new Date(p.timestamp).getTime());
    let minTimestamp = Infinity;
    let maxTimestamp = -Infinity;
    for (let t of timestamps) {
        if (t < minTimestamp) minTimestamp = t;
        if (t > maxTimestamp) maxTimestamp = t;
    }

    initialStartTime = minTimestamp;
    initialEndTime = maxTimestamp;
    startTime = minTimestamp;
    endTime = maxTimestamp;

    const minDate = new Date(minTimestamp).toISOString().slice(0, 16);
    const maxDate = new Date(maxTimestamp).toISOString().slice(0, 16);
    document.getElementById('start-time').value = minDate;
    document.getElementById('end-time').value = maxDate;
    document.getElementById('single-date').value = new Date(minTimestamp).toISOString().slice(0, 10);

    const handleStart = document.getElementById('timeline-handle-start');
    const handleEnd = document.getElementById('timeline-handle-end');
    handleStart.style.left = '0%';
    handleEnd.style.left = '100%';

    document.getElementById('start-time').min = minDate;
    document.getElementById('start-time').max = maxDate;
    document.getElementById('end-time').min = minDate;
    document.getElementById('end-time').max = maxDate;
    document.getElementById('single-date').min = new Date(minTimestamp).toISOString().slice(0, 10);
    document.getElementById('single-date').max = new Date(maxTimestamp).toISOString().slice(0, 10);
}

function getActiveTimeRange() {
    const isSingleMode = document.getElementById('modeSingle').checked;
    let start, end;
    if (isSingleMode) {
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

function filterPointsByTime(points, start, end) {
    const startTime = new Date(start);
    const endTime = new Date(end);
    return points.filter(point => {
        const pointTime = new Date(point.timestamp);
        return pointTime >= startTime && pointTime <= endTime;
    });
}

function refreshAllLayers(points) {
    updateHeatmapWithCurrentParams(points);
    renderTracks(points);
}

function refreshSidebarData(points) {
    updateSidebar({
        points: points,
        addresses: [],
        total_count: currentPoints.length
    });
}

function updateTimeRange() {
    const range = getActiveTimeRange();
    if (!range) return;

    if (isTrackLocked) {
        const filteredPoints = filterPointsByTime(currentPoints, range.start, range.end);
        refreshAllLayers(filteredPoints);
        refreshSidebarData(filteredPoints);
        return Promise.resolve();
    }

    const bounds = map.getBounds();
    const params = new URLSearchParams({
        bounds: `${bounds.getSouth()},${bounds.getWest()},${bounds.getNorth()},${bounds.getEast()}`,
        start: range.start,
        end: range.end,
        zoom: map.getZoom()
    });

    const fetchPromise = fetch(`/data?${params}`)
        .then(response => response.json())
        .then(data => {
            currentPoints = data.points;
            refreshAllLayers(currentPoints);
            updateSidebar(data);
        });

    if (isAnimationPlaying) {
        stopAnimation();
        startAnimation();
    }

    return fetchPromise;
}

function initTimeline() {
    const timelineContainer = document.getElementById('timeline-container');
    const timeline = document.getElementById('timeline');
    const handleStart = document.getElementById('timeline-handle-start');
    const handleEnd = document.getElementById('timeline-handle-end');

    timelineContainer.addEventListener('mousedown', (e) => {
        isDragging = true;
        const rect = timeline.getBoundingClientRect();
        const clickX = e.clientX - rect.left;
        const percent = clickX / rect.width;

        if (Math.abs(percent * 100 - parseFloat(handleStart.style.left)) < 10) {
            currentHandle = handleStart;
        } else if (Math.abs(percent * 100 - parseFloat(handleEnd.style.left)) < 10) {
            currentHandle = handleEnd;
        }
    });

    document.addEventListener('mousemove', (e) => {
        if (isDragging && currentHandle) {
            const rect = timeline.getBoundingClientRect();
            const x = Math.max(0, Math.min(e.clientX - rect.left, rect.width));
            const percent = (x / rect.width) * 100;

            currentHandle.style.left = `${percent}%`;
            const currentTime = startTime + (percent / 100) * (endTime - startTime);

            if (currentHandle === handleStart) {
                const newStartTime = new Date(currentTime);
                document.getElementById('start-time').value = newStartTime.toISOString().slice(0, 16);
            } else {
                const newEndTime = new Date(currentTime);
                document.getElementById('end-time').value = newEndTime.toISOString().slice(0, 16);
            }
        }
    });

    document.addEventListener('mouseup', () => {
        isDragging = false;
        currentHandle = null;
        updateTimeRange();
    });

    document.getElementById('start-time').addEventListener('change', updateTimeRange);
    document.getElementById('end-time').addEventListener('change', updateTimeRange);

    document.getElementById('single-date').addEventListener('change', updateTimeRange);

    const tabRange = document.querySelector('.date-mode-tabs .speed-tab[for="modeRange"]');
    const tabSingle = document.querySelector('.date-mode-tabs .speed-tab[for="modeSingle"]');

    document.getElementById('modeRange').addEventListener('change', function () {
        tabRange.classList.add('active');
        tabSingle.classList.remove('active');
        document.getElementById('range-date-picker').style.display = 'flex';
        document.getElementById('single-date-picker').style.display = 'none';
        document.getElementById('timeline-container').style.display = 'block';
        updateTimeRange();
    });

    document.getElementById('modeSingle').addEventListener('change', function () {
        tabSingle.classList.add('active');
        tabRange.classList.remove('active');
        document.getElementById('single-date-picker').style.display = 'flex';
        document.getElementById('range-date-picker').style.display = 'none';
        document.getElementById('timeline-container').style.display = 'none';
        updateTimeRange();
    });

    document.getElementById('reset-time').addEventListener('click', () => {
        document.getElementById('start-time').value = new Date(initialStartTime).toISOString().slice(0, 16);
        document.getElementById('end-time').value = new Date(initialEndTime).toISOString().slice(0, 16);

        handleStart.style.left = '0%';
        handleEnd.style.left = '100%';

        startTime = initialStartTime;
        endTime = initialEndTime;

        updateTimeRange();
    });

    document.getElementById('reset-time-single').addEventListener('click', () => {
        document.getElementById('single-date').value = new Date(initialStartTime).toISOString().slice(0, 10);
        updateTimeRange();
    });
}
