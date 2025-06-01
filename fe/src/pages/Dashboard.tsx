import { useState } from 'react';
import Sidebar from '../components/Sidebar';
import Overview from '../components/Overview';

const Dashboard = () => {
    const [activeMenu, setActiveMenu] = useState<string | null>('overview');
    const [status, setStatus] = useState('상태: 대기 중');
    const [isStressOn, setIsStressOn] = useState(false);

    const handleMenuClick = (menu: string) => {
        if (menu === 'test') {
            toggleStressTest();
        } else {
            setActiveMenu(menu);
        }
    };

    const toggleStressTest = async () => {
        try {
            const res = await fetch('http://localhost:5000/cpu/toggle', {
                method: 'POST',
            });
            const text = await res.text();

            if (text === 'started') {
                setIsStressOn(true);
                setStatus('🔥 부하 시작됨');
            } else if (text === 'stopped') {
                setIsStressOn(false);
                setStatus('🧊 부하 중지됨');
            } else {
                setStatus('⚠️ 알 수 없는 응답');
            }
        } catch (err) {
            setStatus('❌ 에러 발생');
            console.error(err);
        }
    };

    return (
        <div className="flex h-screen bg-gray-50">
            <Sidebar
                onSelect={handleMenuClick}
                selected={activeMenu}
                isStressOn={isStressOn}
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
