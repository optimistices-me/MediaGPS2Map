let heatmapLayer = null;
let currentHeatmapParams = {
    radius: 4,
    blur: 2,
    minOpacity: 0.4,
    gradient: {
        0.1: 'rgba(0, 0, 255, 0.9)',
        0.5: 'rgba(255, 255, 0, 0.6)',
        1.0: 'rgba(255, 0, 0, 0.2)'
    }
};

function hexToRgb(hex) {
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    return `${r}, ${g}, ${b}`;
}

function updateHeatmapWithCurrentParams(points) {
    const pts = (points || currentPoints).map(p => [p.lat, p.lng, 1]);
    if (heatmapLayer) {
        heatmapLayer.setLatLngs(pts);
    } else {
        heatmapLayer = L.heatLayer(pts, {
            radius: currentHeatmapParams.radius,
            blur: currentHeatmapParams.blur,
            minOpacity: currentHeatmapParams.minOpacity,
            gradient: currentHeatmapParams.gradient
        }).addTo(map);
    }
}

function updateHeatmap() {
    currentHeatmapParams = {
        radius: parseInt(document.getElementById('radius').value),
        blur: parseInt(document.getElementById('blur').value),
        minOpacity: parseFloat(document.getElementById('minOpacity').value),
        gradient: {
            0.1: `rgba(${hexToRgb(document.getElementById('lowColor').value)}, ${parseFloat(document.getElementById('lowOpacity').value)})`,
            0.5: `rgba(${hexToRgb(document.getElementById('midColor').value)}, ${parseFloat(document.getElementById('midOpacity').value)})`,
            1.0: `rgba(${hexToRgb(document.getElementById('highColor').value)}, ${parseFloat(document.getElementById('highOpacity').value)})`
        }
    };

    const pts = currentPoints.map(p => [p.lat, p.lng, 1]);
    if (heatmapLayer) {
        heatmapLayer.setLatLngs(pts);
        heatmapLayer.setOptions({
            radius: currentHeatmapParams.radius,
            blur: currentHeatmapParams.blur,
            minOpacity: currentHeatmapParams.minOpacity,
            gradient: currentHeatmapParams.gradient
        });
    } else {
        updateHeatmapWithCurrentParams();
    }
}

function updateHeatmapFromInput(event) {
    const id = event.target.id;
    const value = event.target.value;

    if (id === 'radius-value') {
        document.getElementById('radius').value = value;
    } else if (id === 'blur-value') {
        document.getElementById('blur').value = value;
    } else if (id === 'minOpacity-value') {
        document.getElementById('minOpacity').value = value;
    }

    updateHeatmap();
}

function initHeatmap() {
    document.getElementById('radius').addEventListener('input', updateHeatmap);
    document.getElementById('blur').addEventListener('input', updateHeatmap);
    document.getElementById('minOpacity').addEventListener('input', updateHeatmap);

    document.getElementById('radius-value').addEventListener('input', updateHeatmapFromInput);
    document.getElementById('blur-value').addEventListener('input', updateHeatmapFromInput);
    document.getElementById('minOpacity-value').addEventListener('input', updateHeatmapFromInput);

    document.getElementById('lowColor').addEventListener('input', updateHeatmap);
    document.getElementById('midColor').addEventListener('input', updateHeatmap);
    document.getElementById('highColor').addEventListener('input', updateHeatmap);
    document.getElementById('lowOpacity').addEventListener('input', updateHeatmap);
    document.getElementById('midOpacity').addEventListener('input', updateHeatmap);
    document.getElementById('highOpacity').addEventListener('input', updateHeatmap);
}
