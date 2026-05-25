'use client';

import { useState } from 'react';
import { supabase } from '@/lib/supabase';
import { QRCodeSVG } from 'qrcode.react';
import { Camera, Printer, Loader2, CheckCircle, ChevronDown, ChevronUp } from 'lucide-react';
import Header from '@/components/Header';

export default function SpeedRegistrationPage() {
  const [images, setImages] = useState<(File | null)[]>([null, null, null, null]);
  const [imageUrls, setImageUrls] = useState<string[]>(['', '', '', '']);
  
  // Basic Info
  const [pNumber, setPNumber] = useState('');
  const [name, setName] = useState('');
  const [price, setPrice] = useState('');

  // Detailed Info (New Fields)
  const [showDetails, setShowDetails] = useState(false);
  const [retailPrice, setRetailPrice] = useState('');
  const [material, setMaterial] = useState('');
  const [origin, setOrigin] = useState('대한민국');
  const [reorderPeriod, setReorderPeriod] = useState('');
  const [description, setDescription] = useState('');
  const [color, setColor] = useState('Free');
  const [size, setSize] = useState('Free');

  const [savedProduct, setSavedProduct] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);

  const handleImageChange = (index: number, file: File | null) => {
    if (!file) return;
    const newImages = [...images];
    newImages[index] = file;
    setImages(newImages);

    const newUrls = [...imageUrls];
    newUrls[index] = URL.createObjectURL(file);
    setImageUrls(newUrls);
  };

  const handleReset = () => {
    if (window.confirm('입력된 모든 사진과 정보를 초기화하시겠습니까?')) {
      resetForm();
    }
  };

  const resetForm = () => {
    setImages([null, null, null, null]);
    setImageUrls(['', '', '', '']);
    setPNumber('');
    setName('');
    setPrice('');
    setRetailPrice('');
    setMaterial('');
    setOrigin('대한민국');
    setReorderPeriod('');
    setDescription('');
    setColor('Free');
    setSize('Free');
    setSavedProduct(null);
    setIsSuccess(false);
    setShowDetails(false);
  };

  const uploadImageToStorage = async (file: File) => {
    const fileName = `${Date.now()}_${file.name}`;
    const { data, error } = await supabase.storage
      .from('product_images')
      .upload(fileName, file);
    if (error) throw error;
    
    const { data: { publicUrl } } = supabase.storage
      .from('product_images')
      .getPublicUrl(fileName);
    return publicUrl;
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!pNumber || !name || !price) {
      alert('품번, 상품명, 도매 단가는 필수 입력 항목입니다.');
      return;
    }

    setIsLoading(true);
    try {
      // 1. Upload images
      const uploadedUrls = [];
      for (const img of images) {
        if (img) {
          const url = await uploadImageToStorage(img);
          uploadedUrls.push(url);
        }
      }

      // 2. Insert into DB (Products)
      const mainUrl = uploadedUrls.length > 0 ? uploadedUrls[0] : null;
      const { data: product, error: productError } = await supabase
        .from('products')
        .insert([{
          p_number: pNumber,
          name,
          price: parseInt(price, 10),
          retail_price: retailPrice ? parseInt(retailPrice, 10) : null,
          material: material || null,
          origin: origin || null,
          reorder_period: reorderPeriod || null,
          description: description || null,
          main_image_url: mainUrl,
          image_urls: uploadedUrls
        }])
        .select()
        .single();

      if (productError) throw productError;

      // 3. Insert into DB (SKUs - with Color/Size)
      const { error: skuError } = await supabase
        .from('product_skus')
        .insert([{
          product_id: product.id,
          color: color || 'Free',
          size: size || 'Free',
          allocated_stock: 50,
        }]);

      if (skuError) throw skuError;

      // 4. Show QR and Print
      setSavedProduct(product);
      setIsSuccess(true);
      
      setTimeout(() => {
        window.print();
        setTimeout(() => {
          resetForm();
        }, 500);
      }, 500);

    } catch (err) {
      console.error(err);
      alert('저장 중 오류가 발생했습니다.');
    } finally {
      setIsLoading(false);
    }
  };

  const slotNames = ['정면', '후면', '디테일 1', '디테일 2'];

  return (
    <div className="min-h-screen bg-zinc-50 flex flex-col hide-on-print">
      
      <Header 
        title="⚡ 초고속 스피드 등록" 
        subtitle="(컨베이어 벨트 모드)" 
        onReset={handleReset} 
        isResetDisabled={isLoading} 
      />

      <main className="flex-1 p-4 md:p-8 max-w-4xl mx-auto w-full pb-32">
        {isSuccess ? (
          <div className="bg-green-50 border border-green-200 rounded-2xl p-8 flex flex-col items-center justify-center text-center animate-in fade-in zoom-in duration-300">
            <CheckCircle className="w-16 h-16 text-green-500 mb-4" />
            <h2 className="text-2xl font-bold text-green-900 mb-2">저장 및 라벨 인쇄 완료!</h2>
            <p className="text-green-700">컨베이어 벨트가 다음 상품을 준비합니다...</p>
          </div>
        ) : (
          <form onSubmit={handleSave} className="bg-white p-6 md:p-8 rounded-3xl shadow-sm border border-zinc-200 flex flex-col">
            
            {/* 카메라 슬롯 영역 */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
              {images.map((_, idx) => (
                <label key={idx} className="aspect-[3/4] bg-zinc-100 rounded-2xl flex flex-col items-center justify-center cursor-pointer overflow-hidden border-2 border-dashed border-zinc-300 hover:border-black hover:bg-zinc-50 transition-all relative group">
                  {imageUrls[idx] ? (
                    <>
                      <img src={imageUrls[idx]} alt="preview" className="w-full h-full object-cover" />
                      <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                        <span className="text-white font-bold text-sm">변경하기</span>
                      </div>
                    </>
                  ) : (
                    <>
                      <Camera className="w-8 h-8 text-zinc-400 mb-3 group-hover:text-black transition-colors" />
                      <span className="text-sm font-bold text-zinc-600 group-hover:text-black transition-colors">{slotNames[idx]}</span>
                    </>
                  )}
                  <input 
                    type="file" 
                    accept="image/*" 
                    capture="environment" 
                    className="hidden" 
                    onChange={(e) => handleImageChange(idx, e.target.files?.[0] || null)}
                    disabled={isLoading}
                  />
                </label>
              ))}
            </div>

            {/* 기본 폼 영역 */}
            <div className="space-y-5 mb-6">
              <div>
                <label className="block text-sm font-bold text-zinc-700 mb-2">품번 (Barcode) <span className="text-red-500">*</span></label>
                <input 
                  type="text" 
                  value={pNumber} 
                  onChange={e => setPNumber(e.target.value)} 
                  className="w-full border-2 border-zinc-200 rounded-xl p-4 text-lg focus:border-black focus:outline-none transition-colors"
                  placeholder="예: SKU-1029"
                  disabled={isLoading}
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-bold text-zinc-700 mb-2">상품명 <span className="text-red-500">*</span></label>
                <input 
                  type="text" 
                  value={name} 
                  onChange={e => setName(e.target.value)} 
                  className="w-full border-2 border-zinc-200 rounded-xl p-4 text-lg focus:border-black focus:outline-none transition-colors"
                  placeholder="예: 기모 오버핏 후드"
                  disabled={isLoading}
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-bold text-zinc-700 mb-2">도매 단가 (원) <span className="text-red-500">*</span></label>
                <input 
                  type="number" 
                  value={price} 
                  onChange={e => setPrice(e.target.value)} 
                  className="w-full border-2 border-zinc-200 rounded-xl p-4 text-lg focus:border-black focus:outline-none transition-colors"
                  placeholder="예: 35000"
                  disabled={isLoading}
                  required
                />
              </div>
            </div>

            {/* 상세 정보 토글 (Progressive Disclosure) */}
            <div className="border-t border-zinc-200 pt-6 mb-8">
              <button
                type="button"
                onClick={() => setShowDetails(!showDetails)}
                className="w-full flex items-center justify-center gap-2 text-zinc-600 font-bold bg-zinc-100 hover:bg-zinc-200 py-3 rounded-xl transition-colors"
              >
                {showDetails ? <ChevronUp className="w-5 h-5" /> : <ChevronDown className="w-5 h-5" />}
                {showDetails ? '상세 정보 닫기' : '+ 상세 정보 더 입력하기 (권장소비자가, 소재, 제조국 등)'}
              </button>

              {showDetails && (
                <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-5 animate-in slide-in-from-top-4 fade-in duration-300">
                  <div>
                    <label className="block text-sm font-bold text-zinc-700 mb-2">색상</label>
                    <input 
                      type="text" 
                      value={color} 
                      onChange={e => setColor(e.target.value)} 
                      className="w-full border-2 border-zinc-200 rounded-xl p-3 focus:border-black focus:outline-none"
                      placeholder="예: 블랙, 화이트, Free"
                      disabled={isLoading}
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-bold text-zinc-700 mb-2">사이즈</label>
                    <input 
                      type="text" 
                      value={size} 
                      onChange={e => setSize(e.target.value)} 
                      className="w-full border-2 border-zinc-200 rounded-xl p-3 focus:border-black focus:outline-none"
                      placeholder="예: S, M, L, Free"
                      disabled={isLoading}
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-bold text-zinc-700 mb-2">권장 소비자가 (원)</label>
                    <input 
                      type="number" 
                      value={retailPrice} 
                      onChange={e => setRetailPrice(e.target.value)} 
                      className="w-full border-2 border-zinc-200 rounded-xl p-3 focus:border-black focus:outline-none"
                      placeholder="예: 79000"
                      disabled={isLoading}
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-bold text-zinc-700 mb-2">혼용률 (소재)</label>
                    <input 
                      type="text" 
                      value={material} 
                      onChange={e => setMaterial(e.target.value)} 
                      className="w-full border-2 border-zinc-200 rounded-xl p-3 focus:border-black focus:outline-none"
                      placeholder="예: 면 80%, 폴리 20%"
                      disabled={isLoading}
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-bold text-zinc-700 mb-2">제조국</label>
                    <input 
                      type="text" 
                      value={origin} 
                      onChange={e => setOrigin(e.target.value)} 
                      className="w-full border-2 border-zinc-200 rounded-xl p-3 focus:border-black focus:outline-none"
                      placeholder="예: 대한민국, 중국"
                      disabled={isLoading}
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-bold text-zinc-700 mb-2">리오더 기간</label>
                    <input 
                      type="text" 
                      value={reorderPeriod} 
                      onChange={e => setReorderPeriod(e.target.value)} 
                      className="w-full border-2 border-zinc-200 rounded-xl p-3 focus:border-black focus:outline-none"
                      placeholder="예: 3~5일 소요"
                      disabled={isLoading}
                    />
                  </div>
                  <div className="md:col-span-2">
                    <label className="block text-sm font-bold text-zinc-700 mb-2">상세 설명</label>
                    <textarea 
                      value={description} 
                      onChange={e => setDescription(e.target.value)} 
                      className="w-full border-2 border-zinc-200 rounded-xl p-3 focus:border-black focus:outline-none h-24 resize-none"
                      placeholder="상품에 대한 추가 설명을 자유롭게 적어주세요."
                      disabled={isLoading}
                    />
                  </div>
                </div>
              )}
            </div>

            {/* 하단 고정 액션 바 (모달/폼 표준화) */}
            <div className="flex gap-4">
              <button 
                type="button"
                onClick={handleReset}
                disabled={isLoading}
                className="w-1/3 bg-white border-2 border-zinc-200 text-zinc-700 py-4 rounded-2xl text-lg font-bold hover:bg-zinc-50 transition-colors disabled:opacity-50"
              >
                취소 (초기화)
              </button>
              <button 
                type="submit" 
                disabled={isLoading}
                className="w-2/3 bg-black text-white py-4 rounded-2xl text-lg font-bold hover:bg-zinc-800 transition-colors disabled:bg-zinc-400 flex items-center justify-center gap-2 shadow-lg"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="w-6 h-6 animate-spin" />
                    클라우드 저장 중...
                  </>
                ) : (
                  <>
                    <Printer className="w-6 h-6" />
                    확인 및 라벨 인쇄
                  </>
                )}
              </button>
            </div>
          </form>
        )}
      </main>

      {/* 인쇄용 영수증/QR 영역 */}
      {savedProduct && (
        <div className="print-only fixed inset-0 bg-white z-50 p-8 flex flex-col items-center justify-center">
          <h1 className="text-3xl font-black mb-4">{savedProduct.name}</h1>
          <p className="text-xl text-zinc-600 mb-8 font-mono border-b border-zinc-300 pb-4 w-full text-center">SKU: {savedProduct.p_number}</p>
          <div className="bg-white p-4 border-4 border-black rounded-3xl mb-8">
            <QRCodeSVG value={`https://autoproducts.com/product/${savedProduct.id}`} size={250} level="H" />
          </div>
          <p className="mt-4 text-4xl font-black">{savedProduct.price.toLocaleString()} KRW</p>
          <p className="mt-12 text-sm text-zinc-400">Powered by AutoProducts B2B</p>
        </div>
      )}

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
