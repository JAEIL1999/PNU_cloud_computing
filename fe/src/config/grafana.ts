const GRAFANA_DASHBOARD_BASE_URL =
  'http://localhost:3001/d-solo/b13ea432-f40d-4f78-8a44-232d990877b0/pnu-cloud-computing?orgId=1&from=now-5m&to=now&timezone=browser&refresh=5s&__feature.dashboardSceneSolo';

export const GRAFANA_PANELS = [
  {
    id: 1,
    title: 'HTTP Requests',
  },
  {
    id: 3,
    title: 'CPU Usage',
  },
  {
    id: 2,
    title: 'Server Count',
  },
];

export const buildGrafanaPanelUrl = (panelId: number) =>
  `${GRAFANA_DASHBOARD_BASE_URL}&panelId=${panelId}`;
