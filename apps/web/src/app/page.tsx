'use client';

import { useRoleStore } from '@/store/useRoleStore';
import Link from 'next/link';

export default function Home() {
  const { role } = useRoleStore();

  return (
    <div className="min-h-screen bg-white flex flex-col items-center justify-center p-8">
      <h1 className="text-5xl font-black mb-12 tracking-tighter">AUTOPRODUCTS</h1>

      <div className="w-full max-w-4xl grid grid-cols-1 md:grid-cols-2 gap-8">
        
        {/* 도매상 모드 뷰 */}
        {role === 'wholesaler' && (
          <div className="col-span-1 md:col-span-2 bg-gray-50 p-10 rounded-3xl border border-gray-200">
            <h2 className="text-2xl font-bold mb-4">🏢 도매상 워크플로우</h2>
            <p className="text-gray-600 mb-8">대량의 상품을 빠르게 등록하고 관리합니다.</p>
            <Link 
              href="/wholesaler/upload" 
              className="inline-block bg-black text-white px-8 py-4 rounded-full font-bold hover:bg-gray-800 transition-colors"
            >
              엑셀 기반 대량 상품 등록 가기 ➔
            </Link>
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
