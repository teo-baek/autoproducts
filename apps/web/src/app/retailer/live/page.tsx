'use client';

import { useState, useEffect } from 'react';

import { supabase } from '@/lib/supabase';
import Header from '@/components/Header';

export default function LiveDashboardPage() {
  const [stock, setStock] = useState<any[]>([]);
  const [isLive, setIsLive] = useState(false);

  useEffect(() => {
    fetchLiveStock();
  }, []);

  const fetchLiveStock = async () => {
    const { data, error } = await supabase
      .from('product_skus')
      .select('id, allocated_stock, sold_stock, products(name)')
      .gt('allocated_stock', 0); // 할당된 가상 재고가 있는 상품만
    
    if (!error && data) {
      setStock(data.map(item => ({
        id: item.id,
        name: (item.products as any)?.name || (Array.isArray(item.products) && (item.products as any)[0]?.name) || '상품',
        allocated: item.allocated_stock,
        sold: item.sold_stock
      })));
    }
  };

  const handleSell = async (id: number) => {
    if (!isLive) return alert('라이브 방송을 먼저 시작해주세요!');

    // 옵티미스틱 UI 업데이트 (빠른 반응성)
    setStock(stock.map(item => {
      if (item.id === id && item.allocated > 0) {
        return { ...item, allocated: item.allocated - 1, sold: item.sold + 1 };
      }
      return item;
    }));

    // 백엔드 RPC 호출 (Row-level Lock 적용된 함수)
    const { error } = await supabase.rpc('decrement_stock', { sku_id: id });
    if (error) {
      console.error(error);
      alert('재고 차감 중 오류가 발생했습니다.');
      fetchLiveStock(); // 롤백
    }
  };

  const handleSendPO = () => {
    const totalSold = stock.reduce((sum, item) => sum + item.sold, 0);
    if (totalSold === 0) {
      alert('판매된 상품이 없습니다.');
      return;
    }
    
    alert(`총 ${totalSold}건의 발주서(PO)가 도매상에게 전송되었습니다!`);
    
    // (실제 프로덕션에서는 orders 테이블에 INSERT)
    setIsLive(false);
  };

  return (
    <div className="min-h-screen bg-neutral-900 text-white flex flex-col">
      <Header 
        title={
          <span className="flex items-center gap-2 text-red-500">
            <span className={isLive ? "animate-pulse" : ""}>🔴</span> LIVE SYNERGY
          </span>
        }
        subtitle="라이브 셀러 실시간 재고 연동 대시보드"
        transparent
        rightActions={
          <button 
            onClick={() => setIsLive(!isLive)}
            className={`px-4 py-2 rounded-full font-bold text-sm transition-colors ${
              isLive ? 'bg-red-600 text-white animate-pulse' : 'bg-white text-black hover:bg-zinc-200'
            }`}
          >
            {isLive ? '방송 종료' : '방송 시작 (ON AIR)'}
          </button>
        }
      />

      <main className="max-w-4xl mx-auto w-full space-y-6 mt-8 p-4 md:p-8">
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
