import type { BalancerMode } from '../services/loadBalancer';

type Props = {
  onSelect: (menu: string) => void;
  selected: string | null;
  isStressOn: boolean;
  isLoading?: boolean;
  mode: BalancerMode;
  onChangeMode: (mode: BalancerMode) => Promise<void>;
};

const Sidebar = ({
  onSelect,
  selected,
  isStressOn,
  isLoading = false,
  mode,
  onChangeMode,
}: Props) => {
  return (
    <aside className="flex h-full w-60 flex-col bg-gray-900 p-4 text-white shadow-lg">
      <h2 className="mb-6 text-xl font-bold">Menu</h2>

      <button
        onClick={() => onSelect('overview')}
        className={`rounded px-4 py-2 text-left transition hover:bg-gray-700 ${
          selected === 'overview' ? 'bg-blue-600' : ''
        }`}
      >
        Overview
      </button>

      <div className="mt-6">
        <h3 className="mb-2 text-sm font-semibold">Load Balancing Mode</h3>

        <label className="mb-2 block">
          <input
            type="radio"
            name="mode"
            value="round_robin"
            checked={mode === 'round_robin'}
            onChange={() => void onChangeMode('round_robin')}
            className="mr-2"
          />
          Round Robin
        </label>

        <label className="mb-2 block">
          <input
            type="radio"
            name="mode"
            value="latency"
            checked={mode === 'latency'}
            onChange={() => void onChangeMode('latency')}
            className="mr-2"
          />
          Latency
        </label>

        <label className="block">
          <input
            type="radio"
            name="mode"
            value="none"
            checked={mode === 'none'}
            onChange={() => void onChangeMode('none')}
            className="mr-2"
          />
          Direct Backend
        </label>
      </div>

      <button
        onClick={() => onSelect('test')}
        disabled={isLoading}
        className={`mt-6 rounded px-4 py-2 text-left font-bold text-white transition ${
          isStressOn ? 'bg-gray-600 hover:bg-gray-700' : 'bg-red-500 hover:bg-red-600'
        } ${isLoading ? 'cursor-not-allowed opacity-50' : ''}`}
      >
        {isLoading
          ? 'Processing...'
          : isStressOn
            ? 'Stop Stress Test'
            : 'Start Stress Test'}
      </button>
    </aside>
  );
};

export default Sidebar;
