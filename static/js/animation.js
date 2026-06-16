let animationMarker = null;
let animationInterval = null;
let animationPoints = [];
let currentAnimationIndex = 0;
let isAnimationPlaying = false;
let isPaused = false;
let playbackRate = 1;

let isProgressDragging = false;

const infoBox = document.getElementById('animationInfo');
const infoTime = document.getElementById('infoTime');
const infoLocation = document.getElementById('infoLocation');

function animateSegment(from, to, duration, onStep, onEnd) {
    const start = performance.now();
    function step(now) {
        const t = Math.min((now - start) / duration, 1);
        const lat = from.lat + (to.lat - from.lat) * t;
        const lng = from.lng + (to.lng - from.lng) * t;
        onStep({ lat, lng });
        if (t < 1 && !isPaused) requestAnimationFrame(step);
        else onEnd();
    }
    requestAnimationFrame(step);
}

function playNext(idx) {
    if (idx >= animationPoints.length - 1) return;
    const curr = animationPoints[idx];
    const next = animationPoints[idx + 1];
    const delta = new Date(next.timestamp) - new Date(curr.timestamp);
    const duration = document.getElementById('modeRatio').checked
        ? delta / parseInt(document.getElementById('animationRatio').value)
        : (1000 / parseInt(document.getElementById('animationSpeed').value));

    animateSegment(curr, next, duration,
        pos => animationMarker.setLatLng([pos.lat, pos.lng]),
        () => {
            const pct = Math.round(((idx + 1) / animationPoints.length) * 100);
            const progEl = document.getElementById('animationTimeProgress');
            if (!isProgressDragging) {
                progEl.value = pct;
                document.getElementById('progressLabel').textContent = pct + '%';
            }
            infoTime.textContent = toUTC8(next.timestamp);
            infoLocation.textContent = next.address || '未知地址';

            currentAnimationIndex = idx + 1;
            if (!isPaused) playNext(idx + 1);
        }
    );
}

function startAnimation() {
    infoBox.style.display = 'block';

    const range = getActiveTimeRange();
    if (!range) return;

    const startTime = new Date(range.start);
    const endTime = new Date(range.end);

    animationPoints = currentPoints
        .filter(point => {
            const pointTime = new Date(point.timestamp);
            return pointTime >= startTime && pointTime <= endTime;
        })
        .sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));

    if (animationPoints.length === 0) return;

    currentAnimationIndex = 0;

    if (!animationMarker) {
        animationMarker = L.circleMarker([0, 0], {
            radius: 8,
            fillColor: '#0000FF',
            color: '#0000FF',
            weight: 2,
            opacity: 1,
            fillOpacity: 0.8
        }).addTo(map);
    }

    isPaused = false;
    playNext(0);
}

function stopAnimation() {
    infoBox.style.display = 'none';
    if (animationInterval) {
        clearInterval(animationInterval);
        animationInterval = null;
    }

    if (animationMarker) {
        map.removeLayer(animationMarker);
        animationMarker = null;
    }

    animationPoints = [];
    currentAnimationIndex = 0;
}

function initAnimation() {
    const progEl = document.getElementById('animationTimeProgress');

    progEl.addEventListener('mousedown', () => isProgressDragging = true);
    progEl.addEventListener('mouseup', () => isProgressDragging = false);

    progEl.addEventListener('input', e => {
        isPaused = true;
        const pct = e.target.value / 100;
        currentAnimationIndex = Math.floor(pct * (animationPoints.length - 1));
        if (animationPoints.length > 0) {
            const pt = animationPoints[currentAnimationIndex];
            animationMarker.setLatLng([pt.lat, pt.lng]);
        }
        document.getElementById('progressLabel').textContent = Math.round(pct * 100) + '%';
    });

    document.getElementById('btnPlay').addEventListener('click', () => {
        isPaused = false;
        playNext(currentAnimationIndex);
    });
    document.getElementById('btnPause').addEventListener('click', () => {
        isPaused = true;
    });
    document.getElementById('btnRewind').addEventListener('click', () => {
        isPaused = true;
        currentAnimationIndex = Math.max(0, currentAnimationIndex - Math.floor(animationPoints.length * 0.05));
        if (animationPoints.length > 0) {
            const pt = animationPoints[currentAnimationIndex];
            animationMarker.setLatLng([pt.lat, pt.lng]);
        }
        progEl.value = Math.round((currentAnimationIndex / (animationPoints.length - 1)) * 100);
        document.getElementById('progressLabel').textContent = progEl.value + '%';
    });
    document.getElementById('btnForward').addEventListener('click', () => {
        isPaused = true;
        currentAnimationIndex = Math.min(animationPoints.length - 1,
            currentAnimationIndex + Math.floor(animationPoints.length * 0.05));
        if (animationPoints.length > 0) {
            const pt = animationPoints[currentAnimationIndex];
            animationMarker.setLatLng([pt.lat, pt.lng]);
        }
        progEl.value = Math.round((currentAnimationIndex / (animationPoints.length - 1)) * 100);
        document.getElementById('progressLabel').textContent = progEl.value + '%';
    });

    document.getElementById('btnStop').addEventListener('click', () => {
        isPaused = true;
        stopAnimation();
        document.getElementById('animationSwitch').checked = false;
        isAnimationPlaying = false;
        progEl.value = 0;
        document.getElementById('progressLabel').textContent = '0%';
    });
}
