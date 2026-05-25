'use client';

import { useState, useEffect } from 'react';
import { supabase } from '@/lib/supabase';
import Link from 'next/link';
import { ArrowLeft, Search, ScanLine, ShoppingCart, Lock, LogOut, Receipt, Printer, RefreshCcw, Loader2 } from 'lucide-react';
import Header from '@/components/Header';

export default function PosTerminalPage() {
  const [products, setProducts] = useState<any[]>([]);
  const [cart, setCart] = useState<any[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(true);
  const [checkoutStatus, setCheckoutStatus] = useState<string | null>(null);

  useEffect(() => {
    fetchProducts();
  }, []);

  const fetchProducts = async () => {
    setLoading(true);
    const { data, error } = await supabase
      .from('products')
      .select('*, product_skus(*)');
    if (data) setProducts(data);
    setLoading(false);
  };

  const addToCart = (product: any, sku: any) => {
    const existing = cart.find(item => item.sku.id === sku.id);
    if (existing) {
      setCart(cart.map(item => 
        item.sku.id === sku.id 
          ? { ...item, quantity: item.quantity + 1 } 
          : item
      ));
    } else {
      setCart([...cart, { product, sku, quantity: 1 }]);
    }
  };

  const removeFromCart = (skuId: string) => {
    setCart(cart.filter(item => item.sku.id !== skuId));
  };

  const totalAmount = cart.reduce((sum, item) => sum + (item.product.price * item.quantity), 0);

  const handleCheckout = async (type: 'sell' | 'sample') => {
    if (cart.length === 0) return;
    
    try {
      for (const item of cart) {
        if (type === 'sell') {
          await supabase.rpc('increment_sold_stock', { p_sku_id: item.sku.id, p_qty: item.quantity });
        } else {
          // 샘플 출고의 경우 별도의 로그나 로직을 태운다고 가정 (Mock)
          console.log('샘플 대여 출고:', item.product.name);
        }
      }
      
      setCheckoutStatus(type === 'sell' ? '결제 및 영수증 인쇄 중...' : '샘플 장부 기록 중...');
      
      setTimeout(() => {
        window.print(); // 영수증 인쇄 팝업
        setTimeout(() => {
          setCart([]);
          setCheckoutStatus(null);
          fetchProducts(); // Refresh stock
        }, 500);
      }, 1000);

    } catch (error) {
      alert('처리 중 오류가 발생했습니다.');
      console.error(error);
    }
  };

  const handleLockStock = async (product: any, sku: any) => {
    const qty = prompt(`[${product.name}] 라이브 셀러를 위해 락을 걸 재고 수량을 입력하세요:`, "10");
    if (!qty || isNaN(Number(qty))) return;

    try {
      await supabase.rpc('increment_allocated_stock', { 
        p_sku_id: sku.id, 
        p_qty: Number(qty) 
      });
      alert(`성공적으로 ${qty}개의 재고가 라이브 락(Lock) 처리되었습니다.`);
      fetchProducts();
    } catch (error) {
      alert('재고 락 처리 중 오류가 발생했습니다.');
    }
  };

  const filteredProducts = products.filter(p => 
    p.name.includes(searchQuery) || p.p_number.includes(searchQuery)
  );

  return (
    <div className="min-h-screen bg-zinc-100 flex flex-col hide-on-print">
      
      <Header 
        title="🏪 현장 결제 터미널 (POS)" 
        rightActions={
          <>
            <div className="bg-zinc-100 px-4 py-2 rounded-full flex items-center gap-2 text-sm text-zinc-600 font-bold">
              <ScanLine className="w-4 h-4" />
              바코드 스캐너 활성
            </div>
            <button 
              onClick={() => setCart([])}
              className="text-sm font-semibold text-zinc-500 hover:text-red-500 transition-colors flex items-center gap-1"
            >
              <RefreshCcw className="w-4 h-4" />
              카트 초기화
            </button>
          </>
        }
      />

      {/* POS Layout (7:3 Split) */}
      <div className="flex-1 flex overflow-hidden">
        
        {/* Left 70%: Catalog Area */}
        <div className="flex-[7] p-6 flex flex-col h-[calc(100vh-73px)] overflow-hidden bg-zinc-50">
          
          {/* Search Bar */}
          <div className="relative mb-6">
            <input 
              type="text" 
              placeholder="상품명 또는 바코드(품번) 스캔..." 
              className="w-full bg-white border-2 border-zinc-200 py-4 pl-12 pr-4 rounded-2xl text-lg focus:outline-none focus:border-black transition-colors shadow-sm"
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
            />
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-6 h-6 text-zinc-400" />
          </div>

          {/* Product Grid */}
          <div className="flex-1 overflow-y-auto pr-2 grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4 pb-12">
            {loading ? (
              <div className="col-span-full flex justify-center py-20">
                <Loader2 className="w-8 h-8 animate-spin text-zinc-400" />
              </div>
            ) : filteredProducts.map(product => {
              const sku = product.product_skus?.[0]; // 단순화 위해 첫번째 SKU 사용
              if (!sku) return null;

              return (
                <div key={product.id} className="bg-white rounded-2xl border border-zinc-200 overflow-hidden shadow-sm hover:shadow-md transition-shadow group flex flex-col">
                  <div className="aspect-square bg-zinc-100 relative">
                    <img 
                      src={product.main_image_url || 'https://via.placeholder.com/300?text=No+Image'} 
                      alt={product.name} 
                      className="w-full h-full object-cover"
                    />
                    <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center p-4">
                      <button 
                        onClick={() => addToCart(product, sku)}
                        className="bg-white text-black font-bold py-3 px-6 rounded-xl w-full flex items-center justify-center gap-2 hover:bg-zinc-200 transition-colors"
                      >
                        <ShoppingCart className="w-5 h-5" /> 담기
                      </button>
                    </div>
                  </div>
                  <div className="p-4">
                    <div className="flex justify-between items-start mb-2">
                      <h3 className="font-bold text-zinc-900 truncate pr-2">{product.name}</h3>
                      <button 
                        onClick={() => handleLockStock(product, sku)}
                        className="text-zinc-400 hover:text-amber-500 transition-colors"
                        title="라이브 방송용 재고 락 걸기"
                      >
                        <Lock className="w-4 h-4" />
                      </button>
                    </div>
                    <p className="text-zinc-500 text-sm font-mono mb-2">{product.p_number}</p>
                    <div className="flex justify-between items-center mt-auto">
                      <span className="font-black text-lg">{product.price.toLocaleString()}</span>
                      <span className="text-xs text-zinc-500">재고: {sku.allocated_stock}</span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Right 30%: Cart & Checkout Area */}
        <div className="flex-[3] bg-white border-l border-zinc-200 flex flex-col h-[calc(100vh-73px)] shadow-[-10px_0_20px_-10px_rgba(0,0,0,0.05)] z-0">
          
          {/* Cart Header */}
          <div className="p-6 border-b border-zinc-200 bg-zinc-50 flex items-center justify-between">
            <h2 className="text-xl font-bold text-zinc-900 flex items-center gap-2">
              <ShoppingCart className="w-5 h-5" /> 현재 장바구니
            </h2>
            <span className="bg-black text-white text-xs px-2 py-1 rounded-full font-bold">{cart.length}</span>
          </div>

          {/* Cart Items */}
          <div className="flex-1 overflow-y-auto p-4 space-y-3 bg-zinc-50/50">
            {cart.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-zinc-400">
                <ScanLine className="w-12 h-12 mb-4 opacity-50" />
                <p>상품을 스캔하거나 탭하여 추가하세요.</p>
              </div>
            ) : (
              cart.map(item => (
                <div key={item.sku.id} className="bg-white p-4 rounded-2xl border border-zinc-200 shadow-sm flex items-center gap-4">
                  <div className="w-16 h-16 rounded-xl overflow-hidden bg-zinc-100 flex-shrink-0">
                    <img src={item.product.main_image_url} alt="" className="w-full h-full object-cover" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <h4 className="font-bold text-zinc-900 truncate">{item.product.name}</h4>
                    <p className="text-sm text-zinc-500">{(item.product.price * item.quantity).toLocaleString()} 원</p>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="font-black text-lg bg-zinc-100 px-3 py-1 rounded-lg">x{item.quantity}</span>
                    <button 
                      onClick={() => removeFromCart(item.sku.id)}
                      className="w-8 h-8 flex items-center justify-center text-zinc-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors"
                    >
                      ×
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>

          {/* Checkout Footer */}
          <div className="p-6 border-t border-zinc-200 bg-white">
            <div className="flex justify-between items-end mb-6">
              <span className="text-zinc-500 font-bold">총 결제 금액</span>
              <span className="text-4xl font-black tracking-tight">{totalAmount.toLocaleString()}<span className="text-xl ml-1 text-zinc-400 font-normal">원</span></span>
            </div>
            
            <div className="space-y-3">
              <button 
                disabled={cart.length === 0 || !!checkoutStatus}
                onClick={() => handleCheckout('sell')}
                className="w-full bg-black text-white py-4 rounded-xl text-lg font-bold hover:bg-zinc-800 transition-colors disabled:bg-zinc-300 disabled:cursor-not-allowed flex items-center justify-center gap-2 shadow-lg"
              >
                {checkoutStatus && checkoutStatus.includes('결제') ? <Loader2 className="w-6 h-6 animate-spin" /> : <Receipt className="w-6 h-6" />}
                {checkoutStatus && checkoutStatus.includes('결제') ? checkoutStatus : '일반 결제 (영수증 출력)'}
              </button>
              
              <button 
                disabled={cart.length === 0 || !!checkoutStatus}
                onClick={() => handleCheckout('sample')}
                className="w-full bg-white border-2 border-zinc-200 text-black py-4 rounded-xl text-lg font-bold hover:border-black transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
              >
                {checkoutStatus && checkoutStatus.includes('샘플') ? <Loader2 className="w-6 h-6 animate-spin" /> : <LogOut className="w-6 h-6" />}
                {checkoutStatus && checkoutStatus.includes('샘플') ? checkoutStatus : '샘플 대여 출고 장부'}
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* 인쇄용 영수증 CSS/Markup */}
      <div className="print-only fixed inset-0 bg-white z-50 p-8 flex-col text-black">
        <div className="text-center border-b-2 border-black pb-4 mb-4">
          <h1 className="text-2xl font-black mb-1">AUTOPRODUCTS POS</h1>
          <p className="text-sm">매장 현장 결제 영수증</p>
        </div>
        <div className="space-y-2 mb-8">
          {cart.map(item => (
            <div key={item.sku.id} className="flex justify-between text-sm">
              <span>{item.product.name} (x{item.quantity})</span>
              <span>{(item.product.price * item.quantity).toLocaleString()}</span>
            </div>
          ))}
        </div>
        <div className="flex justify-between items-center border-t-2 border-black pt-4 font-black text-xl">
          <span>TOTAL</span>
          <span>{totalAmount.toLocaleString()} KRW</span>
        </div>
        <p className="text-center text-xs mt-12 text-zinc-500">이용해 주셔서 감사합니다.</p>
      </div>
      {/* 프린트용 CSS */}
      <style dangerouslySetInnerHTML={{__html: `
        @media print {
          .hide-on-print { display: none !important; }
          .print-only { display: flex !important; position: static !important; }
          body { background: white; margin: 0; padding: 0; }
        }
        @media screen {
          .print-only { display: none !important; }
        }
      `}} />
    </div>
  );
}
