export const LOAD_BALANCER_BASE_URL = 'http://localhost:8000';
export const BACKEND_BASE_URL = 'http://localhost:5000';

export const buildModeUrl = (mode: 'round_robin' | 'latency') =>
  `${LOAD_BALANCER_BASE_URL}/set_mode/${mode}`;

export const buildCpuToggleUrl = (mode: 'round_robin' | 'latency' | 'none') =>
  mode === 'none'
    ? `${BACKEND_BASE_URL}/cpu/toggle`
    : `${LOAD_BALANCER_BASE_URL}/cpu/toggle`;
