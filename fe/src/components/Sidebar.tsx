type Props = {
    onSelect: (menu: string) => void;
    selected: string | null;
    isStressOn: boolean;
    isLoading?: boolean;
    mode: 'round_robin' | 'latency';
    onChangeMode: (mode: 'round_robin' | 'latency') => Promise<void>;
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
        <aside className="w-60 h-full bg-gray-900 text-white flex flex-col p-4 shadow-lg">
            <h2 className="text-xl font-bold mb-6">📁 메뉴</h2>

            <button
                onClick={() => onSelect('overview')}
                className={`text-left px-4 py-2 rounded hover:bg-gray-700 transition ${
                    selected === 'overview' ? 'bg-blue-600' : ''
                }`}
            >
                📊 전체 대시보드
            </button>

            {/* 라디오 버튼으로 모드 선택 */}
            <div className="mt-6">
                <h3 className="text-sm font-semibold mb-2">로드밸런싱 모드</h3>
                <label className="block mb-2">
                    <input
                        type="radio"
                        name="mode"
                        value="round_robin"
                        checked={mode === 'round_robin'}
                        onChange={() => onChangeMode('round_robin')}
                        className="mr-2"
                    />
                    🔄 라운드로빈
                </label>
                <label className="block">
                    <input
                        type="radio"
                        name="mode"
                        value="latency"
                        checked={mode === 'latency'}
                        onChange={() => onChangeMode('latency')}
                        className="mr-2"
                    />
                    🚀 레이턴시
                </label>
            </div>

            <button
                onClick={() => onSelect('test')}
                disabled={isLoading}
                className={`text-left px-4 py-2 mt-6 rounded font-bold text-white transition ${
                    isStressOn
                        ? 'bg-gray-600 hover:bg-gray-700'
                        : 'bg-red-500 hover:bg-red-600'
                } ${isLoading ? 'opacity-50 cursor-not-allowed' : ''}`}
            >
                {isLoading
                    ? '⏳ 처리 중...'
                    : isStressOn
                    ? '🛑 부하 중지'
                    : '🔥 부하 테스트 시작'}
            </button>
        </aside>
    );
};

export default Sidebar;
