'use client';

import { useState, useEffect } from 'react';

import { supabase } from '@/lib/supabase';

export default function CatalogPage() {
  const [products, setProducts] = useState<any[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [semanticTag, setSemanticTag] = useState<string | null>(null);

  useEffect(() => {
    fetchProducts();
  }, []);

  const fetchProducts = async () => {
    const { data, error } = await supabase
      .from('products')
      .select('*')
      .order('created_at', { ascending: false });
    
    if (!error && data) {
      setProducts(data);
    }
  };
  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchQuery.includes('따뜻') || searchQuery.includes('넉넉')) {
      setSemanticTag('AI 번역: #기모 #오버핏');
    } else {
      setSemanticTag('AI 번역: #' + searchQuery);
    }
  };

  return (
    <div className="min-h-screen bg-black text-white selection:bg-white selection:text-black">
      {/* Header & Search */}
      <header className="px-8 py-12 md:py-20 max-w-7xl mx-auto">
        <h1 className="text-5xl md:text-7xl font-serif tracking-tighter mb-8 font-light">
          DISCOVER<br/><span className="italic text-gray-400">THE COLLECTION</span>
        </h1>
        
        <form onSubmit={handleSearch} className="relative max-w-2xl">
          <input 
            type="text" 
            placeholder="예: 따뜻하고 넉넉한 옷 찾아줘..." 
            className="w-full bg-transparent border-b-2 border-gray-600 py-4 text-xl md:text-2xl text-white placeholder-gray-600 focus:outline-none focus:border-white transition-colors"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
          {semanticTag && (
            <div className="absolute -bottom-8 left-0 text-sm font-bold text-emerald-400 tracking-wider">
              {semanticTag}
            </div>
          )}
        </form>
      </header>

      {/* Grid Catalog (Progressive Disclosure) */}
      <main className="px-4 pb-24 max-w-[1600px] mx-auto">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {products.length === 0 && (
            <div className="col-span-1 md:col-span-3 text-center py-20 text-gray-500">
              등록된 상품이 없습니다. 도매상 앱에서 상품을 등록해보세요.
            </div>
          )}
          {products.map((item) => (
            <div key={item.id} className="group relative aspect-[3/4] overflow-hidden bg-zinc-900 cursor-pointer">
              <img 
                src={item.main_image_url || 'https://images.unsplash.com/photo-1556821840-3a63f95609a7?auto=format&fit=crop&w=800&q=80'} 
                alt={item.name} 
                className="w-full h-full object-cover transition-transform duration-700 ease-out group-hover:scale-105 opacity-80 group-hover:opacity-100"
              />
              
              {/* Hover Overlay (Progressive Disclosure) */}
              <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500 flex flex-col justify-end p-8">
                <h3 className="text-2xl font-bold mb-2 translate-y-4 group-hover:translate-y-0 transition-transform duration-500">{item.name}</h3>
                <p className="text-xl text-gray-300 translate-y-4 group-hover:translate-y-0 transition-transform duration-500 delay-75">
                  {item.price.toLocaleString()} KRW
                </p>
                <div className="mt-6 translate-y-4 group-hover:translate-y-0 transition-transform duration-500 delay-150">
                  <button className="bg-white text-black px-6 py-3 font-bold text-sm tracking-widest hover:bg-gray-200 transition-colors">
                    ADD TO CART
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      </main>
    </div>
  );
}
