'use client';

import { useState } from 'react';

// 가상의 락(Lock) 걸린 방송용 재고 데이터
const initialStock = [
  { id: 1, name: '기모 오버핏 후드 (블랙)', allocated: 50, sold: 0 },
  { id: 2, name: '카고 와이드 팬츠 (카키)', allocated: 30, sold: 0 },
];

export default function LiveDashboardPage() {
  const [stock, setStock] = useState(initialStock);
  const [isLive, setIsLive] = useState(false);

  const handleSell = (id: number) => {
    if (!isLive) return alert('라이브 방송을 먼저 시작해주세요!');

    setStock(stock.map(item => {
      if (item.id === id && item.allocated > 0) {
        return { ...item, allocated: item.allocated - 1, sold: item.sold + 1 };
      }
      return item;
    }));
  };

  const handleSendPO = () => {
    const totalSold = stock.reduce((sum, item) => sum + item.sold, 0);
    if (totalSold === 0) {
      alert('판매된 상품이 없습니다.');
      return;
    }
    
    alert(`총 ${totalSold}건의 발주서(PO)가 도매상에게 전송되었습니다!`);
    
    // 리셋
    setStock(stock.map(item => ({ ...item, sold: 0 })));
    setIsLive(false);
  };

  return (
    <div className="min-h-screen bg-neutral-900 text-white p-8">
      <header className="max-w-4xl mx-auto flex justify-between items-center mb-12">
        <div>
          <h1 className="text-4xl font-bold text-red-500 flex items-center gap-3">
            <span className={isLive ? "animate-pulse" : ""}>🔴</span> 
            LIVE SYNERGY
          </h1>
          <p className="text-gray-400 mt-2">라이브 셀러 실시간 재고 연동 대시보드</p>
        </div>
        
        <button 
          onClick={() => setIsLive(!isLive)}
          className={`px-6 py-3 rounded-full font-bold text-lg transition-colors ${
            isLive ? 'bg-red-600 text-white animate-pulse' : 'bg-white text-black hover:bg-gray-200'
          }`}
        >
          {isLive ? '방송 종료' : '방송 시작 (ON AIR)'}
        </button>
      </header>

      <main className="max-w-4xl mx-auto space-y-6">
        {stock.map((item) => (
          <div key={item.id} className="bg-neutral-800 rounded-2xl p-6 flex flex-col md:flex-row items-center justify-between border border-neutral-700">
            <div className="flex-1 mb-4 md:mb-0">
              <h2 className="text-2xl font-bold mb-2">{item.name}</h2>
              <div className="flex gap-4 text-lg">
                <span className="text-gray-400">잔여 가상재고:</span>
                <span className={`font-mono font-bold ${item.allocated < 10 ? 'text-red-500' : 'text-emerald-400'}`}>
                  {item.allocated}
                </span>
              </div>
            </div>

            <div className="flex items-center gap-6">
              <div className="text-center">
                <div className="text-sm text-gray-400 mb-1">판매량</div>
                <div className="text-3xl font-mono font-bold text-white">{item.sold}</div>
              </div>
              
              <button 
                onClick={() => handleSell(item.id)}
                disabled={item.allocated === 0 || !isLive}
                className="w-24 h-24 rounded-full bg-blue-600 hover:bg-blue-500 active:scale-95 transition-all disabled:bg-neutral-600 disabled:opacity-50 flex items-center justify-center text-3xl font-bold shadow-lg shadow-blue-900/50"
              >
                -1
              </button>
            </div>
          </div>
        ))}

        <div className="pt-12 flex justify-end">
          <button 
            onClick={handleSendPO}
            className="bg-emerald-500 hover:bg-emerald-400 text-black px-10 py-5 rounded-xl font-bold text-xl transition-transform hover:-translate-y-1 active:translate-y-0 shadow-lg shadow-emerald-900/50"
          >
            📋 도매상에게 발주서 전송 (Send PO)
          </button>
        </div>
      </main>
    </div>
  );
}
