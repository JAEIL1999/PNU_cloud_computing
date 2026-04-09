import { GRAFANA_PANELS, buildGrafanaPanelUrl } from '../config/grafana';

const Overview = () => {
  return (
    <div className="flex flex-col items-center space-y-8">
      {GRAFANA_PANELS.map((panel) => (
        <iframe
          key={panel.id}
          src={buildGrafanaPanelUrl(panel.id)}
          className="h-64 w-full max-w-4xl rounded border-none"
          title={panel.title}
        />
      ))}
    </div>
  );
};

export default Overview;
