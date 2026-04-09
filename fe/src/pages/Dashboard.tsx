import { useState } from 'react';

import Overview from '../components/Overview';
import Sidebar from '../components/Sidebar';
import { setBalancerMode, toggleCpuStress, type BalancerMode } from '../services/loadBalancer';

const Dashboard = () => {
  const [activeMenu, setActiveMenu] = useState<string | null>('overview');
  const [status, setStatus] = useState('Status: idle');
  const [isStressOn, setIsStressOn] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [mode, setMode] = useState<BalancerMode>('round_robin');

  const handleMenuClick = (menu: string) => {
    if (menu === 'test') {
      void handleStressToggle();
      return;
    }

    setActiveMenu(menu);
  };

  const handleChangeMode = async (newMode: BalancerMode) => {
    setMode(newMode);

    if (newMode === 'none') {
      setStatus('Load balancer bypass enabled');
      return;
    }

    try {
      const response = await setBalancerMode(newMode);
      if (response.ok) {
        setStatus(`Load balancing mode changed to ${newMode}`);
      } else {
        setStatus('Failed to change load balancing mode');
      }
    } catch (error) {
      console.error(error);
      setStatus('Error while changing load balancing mode');
    }
  };

  const handleStressToggle = async () => {
    setIsLoading(true);

    try {
      setStatus(
        isStressOn
          ? 'Stopping stress test...'
          : `Starting stress test (${mode} mode)...`,
      );

      if (mode !== 'none') {
        const modeResponse = await setBalancerMode(mode);
        if (!modeResponse.ok) {
          setStatus('Failed to configure load balancer mode');
          return;
        }
      }

      const response = await toggleCpuStress(mode);
      const responseText = await response.text();
      console.log('Stress response:', responseText);

      if (responseText === 'started' || responseText === 'ok') {
        setIsStressOn(true);
        setStatus(`Stress test started (${mode} mode)`);
      } else if (responseText === 'stopped') {
        setIsStressOn(false);
        setStatus('Stress test stopped');
      } else {
        setStatus(`Unexpected response: ${responseText}`);
      }
    } catch (error) {
      console.error(error);
      setStatus('Error while running stress test');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex h-screen bg-gray-50">
      <Sidebar
        onSelect={handleMenuClick}
        selected={activeMenu}
        isStressOn={isStressOn}
        isLoading={isLoading}
        mode={mode}
        onChangeMode={handleChangeMode}
      />
      <main className="flex-1 overflow-y-auto p-8">
        <div className="rounded bg-white p-6 shadow">
          {activeMenu === 'overview' && <Overview />}
          <p className="mt-4 text-sm text-gray-500">{status}</p>
        </div>
      </main>
    </div>
  );
};

export default Dashboard;
