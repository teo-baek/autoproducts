'use client';

import { useState, useEffect } from 'react';
import { supabase } from '@/lib/supabase';
import { Search, Loader2, X, ShoppingCart } from 'lucide-react';
import Header from '@/components/Header';

export default function CatalogPage() {
  const [products, setProducts] = useState<any[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [semanticTag, setSemanticTag] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [searching, setSearching] = useState(false);
  
  // Modal State
  const [selectedProduct, setSelectedProduct] = useState<any | null>(null);

  useEffect(() => {
    fetchProducts();
  }, [semanticTag]);

  const fetchProducts = async () => {
    setLoading(true);
    let query = supabase
      .from('products')
      .select('*, product_skus(*)')
      .order('created_at', { ascending: false });

    if (semanticTag) {
      if (semanticTag.includes('기모') || semanticTag.includes('따뜻')) {
        query = query.ilike('name', '%기모%');
      } else if (semanticTag.includes('오버핏') || semanticTag.includes('넉넉')) {
        query = query.ilike('name', '%오버핏%');
      } else {
        query = query.ilike('name', `%${searchQuery}%`);
      }
    }

    const { data, error } = await query;
    if (data) {
      setProducts(data);
    }
    setLoading(false);
  };

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;

    setSearching(true);
    setSemanticTag(null);
    setProducts([]);

    setTimeout(() => {
      if (searchQuery.includes('따뜻') || searchQuery.includes('겨울')) {
        setSemanticTag('AI 매칭 키워드: #기모 #두꺼운 #겨울용');
      } else if (searchQuery.includes('넉넉') || searchQuery.includes('큰')) {
        setSemanticTag('AI 매칭 키워드: #오버핏 #루즈핏 #빅사이즈');
      } else {
        setSemanticTag(`AI 매칭 키워드: #${searchQuery.replace(/\s+/g, ' #')}`);
      }
      setSearching(false);
    }, 1500);
  };

  const openProductModal = (product: any) => {
    setSelectedProduct(product);
    document.body.style.overflow = 'hidden'; // prevent background scroll
  };

  const closeProductModal = () => {
    setSelectedProduct(null);
    document.body.style.overflow = 'auto';
  };

  return (
    <div className="min-h-screen bg-black text-white selection:bg-white selection:text-black relative">
      
      {/* Global Navigation Header (Transparent mode for Catalog) */}
      <Header title="" transparent />

      {/* Header & Search */}
      <header className="px-8 pt-12 pb-12 md:py-24 max-w-7xl mx-auto pl-8 md:pl-8">
        <h1 className="text-5xl md:text-7xl font-serif tracking-tighter mb-8 font-light">
          DISCOVER<br/><span className="italic text-zinc-500">THE COLLECTION</span>
        </h1>
        
        <form onSubmit={handleSearch} className="relative max-w-2xl">
          <div className="relative">
            <input 
              type="text" 
              placeholder="예: 따뜻하고 넉넉한 옷 찾아줘..." 
              className="w-full bg-transparent border-b border-zinc-600 py-4 pl-12 pr-4 text-xl md:text-2xl text-white placeholder-zinc-600 focus:outline-none focus:border-white transition-colors disabled:opacity-50"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              disabled={searching}
            />
            <Search className="absolute left-2 top-1/2 -translate-y-1/2 w-6 h-6 text-zinc-500" />
            {searching && (
              <Loader2 className="absolute right-2 top-1/2 -translate-y-1/2 w-6 h-6 text-emerald-400 animate-spin" />
            )}
          </div>
          
          {semanticTag && !searching && (
            <div className="absolute -bottom-10 left-0 text-sm font-bold text-emerald-400 tracking-wider flex items-center gap-2 animate-in fade-in slide-in-from-top-2">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              {semanticTag}
            </div>
          )}
        </form>
      </header>

      {/* Grid / Snap-Scroll Catalog (Progressive Disclosure) */}
      <main className="px-4 pb-24 max-w-[1600px] mx-auto min-h-[50vh]">
        {loading || searching ? (
          <div className="flex flex-col items-center justify-center py-32 text-zinc-500">
            <Loader2 className="w-12 h-12 animate-spin mb-4 text-white" />
            <p className="text-lg tracking-widest uppercase">
              {searching ? 'AI 분석 및 매칭 중...' : '상품 불러오는 중...'}
            </p>
          </div>
        ) : (
          <div className="h-[75vh] md:h-auto overflow-y-scroll snap-y snap-mandatory md:overflow-visible flex flex-col md:grid md:grid-cols-2 lg:grid-cols-3 gap-4 hide-scrollbar">
            {products.length === 0 && (
              <div className="col-span-1 md:col-span-3 text-center py-32 text-zinc-500">
                <p className="text-xl mb-2">검색된 상품이 없습니다.</p>
                <p className="text-sm">다른 키워드로 검색하거나 도매상 앱에서 상품을 등록해보세요.</p>
              </div>
            )}
            
            {products.map((item) => (
              <div 
                key={item.id} 
                onClick={() => openProductModal(item)}
                className="w-full h-full flex-shrink-0 snap-start snap-always md:aspect-[3/4] group relative overflow-hidden bg-zinc-900 cursor-pointer rounded-2xl md:rounded-none"
              >
                {/* Carousel Container */}
                <div className="w-full h-full flex overflow-x-scroll snap-x snap-mandatory hide-scrollbar relative">
                  {(item.image_urls && item.image_urls.length > 0 ? item.image_urls : [item.main_image_url || 'https://images.unsplash.com/photo-1556821840-3a63f95609a7?auto=format&fit=crop&w=800&q=80']).map((url: string, i: number) => (
                    <img 
                      key={i}
                      src={url} 
                      alt={`${item.name} - cut ${i}`} 
                      className="w-full h-full flex-shrink-0 snap-center object-cover transition-transform duration-700 group-hover:scale-105 pointer-events-none"
                    />
                  ))}
                </div>

                {/* Dots for carousel */}
                {item.image_urls && item.image_urls.length > 1 && (
                  <div className="absolute bottom-6 left-0 right-0 flex justify-center gap-1.5 z-10">
                    {item.image_urls.map((_: any, i: number) => (
                      <div key={i} className="w-1.5 h-1.5 rounded-full bg-white/50" />
                    ))}
                  </div>
                )}

                {/* Hover Overlay */}
                <div className="absolute inset-0 bg-gradient-to-t from-black/90 via-black/30 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500 flex flex-col justify-end p-8 pointer-events-none">
                  <div className="flex items-center gap-2 mb-2 translate-y-4 group-hover:translate-y-0 transition-transform duration-500">
                    <span className="bg-white/20 backdrop-blur text-white text-xs px-2 py-1 rounded">{item.p_number}</span>
                  </div>
                  <h3 className="text-2xl font-bold mb-1 translate-y-4 group-hover:translate-y-0 transition-transform duration-500">{item.name}</h3>
                  <p className="text-xl text-zinc-300 translate-y-4 group-hover:translate-y-0 transition-transform duration-500 delay-75">
                    {item.price.toLocaleString()} KRW
                  </p>
                  <p className="text-sm text-zinc-400 mt-2 line-clamp-2 translate-y-4 group-hover:translate-y-0 transition-transform duration-500 delay-100">
                    {item.description || "상세 설명을 보려면 클릭하세요."}
                  </p>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>

      {/* Product Detail Modal */}
      {selectedProduct && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 md:p-8 animate-in fade-in duration-300">
          <div className="absolute inset-0 bg-black/80 backdrop-blur-sm" onClick={closeProductModal}></div>
          <div className="bg-zinc-900 border border-zinc-800 rounded-3xl w-full max-w-5xl max-h-[90vh] overflow-hidden relative z-10 flex flex-col md:flex-row shadow-2xl animate-in zoom-in-95 duration-300">
            
            {/* Left: Modal Image Carousel */}
            <div className="md:w-1/2 h-64 md:h-auto bg-black relative flex overflow-x-scroll snap-x snap-mandatory hide-scrollbar">
              {(selectedProduct.image_urls && selectedProduct.image_urls.length > 0 ? selectedProduct.image_urls : [selectedProduct.main_image_url || 'https://via.placeholder.com/800']).map((url: string, i: number) => (
                <img 
                  key={i}
                  src={url} 
                  alt=""
                  className="w-full h-full flex-shrink-0 snap-center object-cover"
                />
              ))}
            </div>

            {/* Right: Detailed Metadata */}
            <div className="md:w-1/2 flex flex-col h-full max-h-[50vh] md:max-h-[90vh]">
              <div className="flex-1 p-8 overflow-y-auto">
                <div className="flex justify-between items-start mb-6">
                  <div>
                    <span className="text-xs font-bold text-zinc-500 tracking-widest">{selectedProduct.p_number}</span>
                    <h2 className="text-3xl font-bold mt-1 text-white">{selectedProduct.name}</h2>
                  </div>
                  <button onClick={closeProductModal} className="p-2 bg-zinc-800 hover:bg-zinc-700 rounded-full transition-colors text-zinc-400">
                    <X className="w-5 h-5" />
                  </button>
                </div>

                <div className="flex items-end gap-3 mb-8 pb-8 border-b border-zinc-800">
                  <span className="text-3xl font-black text-white">{selectedProduct.price.toLocaleString()} <span className="text-xl font-normal text-zinc-500">원</span></span>
                  {selectedProduct.retail_price && (
                    <span className="text-lg text-zinc-500 line-through">권장 {selectedProduct.retail_price.toLocaleString()} 원</span>
                  )}
                </div>

                {/* Metadata Grid */}
                <div className="grid grid-cols-2 gap-y-6 gap-x-4 mb-8">
                  {selectedProduct.product_skus?.[0]?.color && (
                    <div>
                      <p className="text-xs font-bold text-zinc-500 uppercase tracking-widest mb-1">Color</p>
                      <p className="text-sm text-zinc-300">{selectedProduct.product_skus[0].color}</p>
                    </div>
                  )}
                  {selectedProduct.product_skus?.[0]?.size && (
                    <div>
                      <p className="text-xs font-bold text-zinc-500 uppercase tracking-widest mb-1">Size</p>
                      <p className="text-sm text-zinc-300">{selectedProduct.product_skus[0].size}</p>
                    </div>
                  )}
                  {selectedProduct.material && (
                    <div className="col-span-2">
                      <p className="text-xs font-bold text-zinc-500 uppercase tracking-widest mb-1">Material</p>
                      <p className="text-sm text-zinc-300">{selectedProduct.material}</p>
                    </div>
                  )}
                  {selectedProduct.origin && (
                    <div>
                      <p className="text-xs font-bold text-zinc-500 uppercase tracking-widest mb-1">Origin</p>
                      <p className="text-sm text-zinc-300">{selectedProduct.origin}</p>
                    </div>
                  )}
                  {selectedProduct.reorder_period && (
                    <div>
                      <p className="text-xs font-bold text-zinc-500 uppercase tracking-widest mb-1">Re-order</p>
                      <p className="text-sm text-zinc-300">{selectedProduct.reorder_period}</p>
                    </div>
                  )}
                </div>

                {selectedProduct.description && (
                  <div className="mb-8">
                    <p className="text-xs font-bold text-zinc-500 uppercase tracking-widest mb-2">Description</p>
                    <p className="text-sm text-zinc-400 leading-relaxed whitespace-pre-wrap">{selectedProduct.description}</p>
                  </div>
                )}
              </div>

              {/* Standardized Actions (Cancel / Confirm) */}
              <div className="p-6 border-t border-zinc-800 bg-zinc-900/50 flex gap-4 mt-auto">
                <button 
                  onClick={closeProductModal}
                  className="w-1/3 bg-zinc-800 text-white font-bold py-4 rounded-xl hover:bg-zinc-700 transition-colors"
                >
                  취소 (닫기)
                </button>
                <button 
                  onClick={() => { alert('카트에 담겼습니다! (Mock)'); closeProductModal(); }}
                  className="w-2/3 bg-white text-black font-bold py-4 rounded-xl hover:bg-zinc-200 transition-colors flex justify-center items-center gap-2"
                >
                  <ShoppingCart className="w-5 h-5" />
                  확인 (카트 담기)
                </button>
              </div>
            </div>

          </div>
        </div>
      )}

    </div>
  );
}
