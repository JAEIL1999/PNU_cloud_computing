import { buildCpuToggleUrl, buildModeUrl } from '../config/endpoints';

export type BalancerMode = 'round_robin' | 'latency' | 'none';

export async function setBalancerMode(mode: Exclude<BalancerMode, 'none'>) {
  return fetch(buildModeUrl(mode));
}

export async function toggleCpuStress(mode: BalancerMode) {
  return fetch(buildCpuToggleUrl(mode), { method: 'POST' });
}
