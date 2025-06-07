import { useState } from 'react';
import Sidebar from '../components/Sidebar';
import Overview from '../components/Overview';

const Dashboard = () => {
    const [activeMenu, setActiveMenu] = useState<string | null>('overview');
    const [status, setStatus] = useState('상태: 대기 중');
    const [isStressOn, setIsStressOn] = useState(false);
    const [isLoading, setIsLoading] = useState(false);
    const [mode, setMode] = useState<'round_robin' | 'latency' | 'none'>('round_robin');

    const handleMenuClick = (menu: string) => {
        if (menu === 'test') {
            toggleStressTest();
        } else {
            setActiveMenu(menu);
        }
    };

    const handleChangeMode = async (newMode: 'round_robin' | 'latency' | 'none') => {
        setMode(newMode);
        if (newMode === 'none') {
            setStatus('📛 로드밸런서 사용 안 함');
            return;
        }

        try {
            const res = await fetch(`http://localhost:8081/set_mode/${newMode}`);
            if (res.ok) {
                setStatus(`✅ 모드 변경됨: ${newMode}`);
            } else {
                setStatus('❌ 모드 변경 실패');
            }
        } catch (err) {
            console.error(err);
            setStatus('⚠️ 모드 변경 중 에러 발생');
        }
    };

    const toggleStressTest = async () => {
        setIsLoading(true);
        try {
            setStatus(isStressOn ? '⏳ 부하 중지 중...' : `⚡ 부하 시작 중 (${mode} 모드)...`);

            if (mode !== 'none') {
                const modeRes = await fetch(`http://localhost:8081/set_mode/${mode}`);
                if (!modeRes.ok) {
                    setStatus('❌ 로드밸런서 모드 설정 실패');
                    return;
                }
            }

            const res = await fetch(
                mode === 'none'
                    ? 'http://localhost:5000/cpu/toggle'
                    : 'http://localhost:8081/load',
                { method: 'POST' }
            );

            const text = await res.text();

            if (text === 'started') {
                setIsStressOn(true);
                setStatus(`🔥 부하 시작됨 (${mode} 모드)`);
            } else if (text === 'stopped') {
                setIsStressOn(false);
                setStatus('🧊 부하 중지됨');
            } else {
                setStatus('⚠️ 알 수 없는 응답');
            }
        } catch (err) {
            console.error(err);
            setStatus('❌ 부하 테스트 중 에러 발생');
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
            <main className="flex-1 p-8 overflow-y-auto">
                <div className="bg-white p-6 rounded shadow">
                    {activeMenu === 'overview' && <Overview />}
                    <p className="text-sm text-gray-500 mt-4">{status}</p>
                </div>
            </main>
        </div>
    );
};

export default Dashboard;
