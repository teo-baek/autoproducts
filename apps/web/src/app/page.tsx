'use client';

import { useRoleStore } from '@/store/useRoleStore';
import Link from 'next/link';
import { useEffect, useState } from 'react';

export default function Home() {
  const { role } = useRoleStore();
  const [isMounted, setIsMounted] = useState(false);

  useEffect(() => {
    setIsMounted(true);
  }, []);

  if (!isMounted) return null;

  return (
    <div className="min-h-screen bg-white flex flex-col items-center justify-center p-8">
      <h1 className="text-5xl font-black mb-12 tracking-tighter">AUTOPRODUCTS</h1>

      <div className="w-full max-w-4xl grid grid-cols-1 md:grid-cols-2 gap-8">
        
        {/* 도매상 모드 뷰 */}
        {role === 'wholesaler' && (
          <div className="col-span-1 md:col-span-2 bg-gray-50 p-10 rounded-3xl border border-gray-200">
            <h2 className="text-2xl font-bold mb-4 flex items-center">
              <span className="bg-zinc-200 text-sm px-3 py-1 rounded-full mr-3 text-zinc-800">도매상</span>
              상품 관리 워크플로우
            </h2>
            <p className="text-gray-600 mb-8">대량의 상품을 빠르게 등록하고 관리합니다.</p>
            <div className="flex flex-col sm:flex-row gap-4">
              <Link href="/wholesaler/pos" className="flex-1 py-4 px-6 bg-emerald-500 text-white rounded-2xl text-center text-lg font-bold hover:bg-emerald-600 transition-colors shadow-lg hover:shadow-xl">
                🏪 현장 결제 터미널 (POS)
              </Link>
              <Link href="/wholesaler/speed" className="flex-1 py-4 px-6 bg-black text-white rounded-2xl text-center text-lg font-bold hover:bg-gray-800 transition-colors shadow-lg hover:shadow-xl">
                ⚡ 초고속 스피드 등록
              </Link>
              <Link href="/wholesaler/upload" className="flex-1 py-4 px-6 bg-white border-2 border-gray-200 text-black rounded-2xl text-center text-lg font-bold hover:border-black transition-colors shadow-sm">
                📦 엑셀 대량 업로드
              </Link>
            </div>
          </div>
        )}

        {/* 소매상 모드 뷰 */}
        {role === 'retailer' && (
          <>
            <div className="bg-gray-50 p-10 rounded-3xl border border-gray-200 hover:shadow-lg transition-shadow group">
              <h2 className="text-2xl font-bold mb-4">📖 글로벌 카탈로그</h2>
              <p className="text-gray-600 mb-8">VOGUE 스타일의 하이엔드 룩북에서 상품을 탐색하세요.</p>
              <Link 
                href="/retailer/catalog" 
                className="inline-block bg-black text-white px-8 py-4 rounded-full font-bold group-hover:bg-gray-800 transition-colors"
              >
                카탈로그 탐색하기 ➔
              </Link>
            </div>

            <div className="bg-gray-50 p-10 rounded-3xl border border-gray-200 hover:shadow-lg transition-shadow group">
              <h2 className="text-2xl font-bold mb-4">🔴 라이브 방송 대시보드</h2>
              <p className="text-gray-600 mb-8">방송 중 실시간 재고 차감 및 발주서를 관리합니다.</p>
              <Link 
                href="/retailer/live" 
                className="inline-block bg-black text-white px-8 py-4 rounded-full font-bold group-hover:bg-gray-800 transition-colors"
              >
                라이브 패널 열기 ➔
              </Link>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
