/**
 * Shared application state.
 * Imported by all modules instead of relying on global variables.
 */

export const state = {
  map: null,
  currentPoints: [],
  heatmapLayer: null,
  trackLayers: [],
  showMode: /** @type {'heatmap'|'trajectory'} */ ('heatmap'),
  isTrackLocked: false,
  isAnimationPlaying: false,
  isPaused: false,
  animationPoints: [],
  currentAnimationIndex: 0,
  animationMarker: null,

  /** Data cache bounds (min/max timestamps from last load) */
  initialStartTime: null,
  initialEndTime: null,
};
