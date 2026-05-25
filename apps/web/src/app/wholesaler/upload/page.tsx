'use client';

import { useState } from 'react';
import { supabase } from '@/lib/supabase';
import * as XLSX from 'xlsx';
import { UploadCloud, Image as ImageIcon, FileSpreadsheet, CheckCircle, GripVertical, Loader2 } from 'lucide-react';
import Header from '@/components/Header';

interface ExcelRow {
  id: string;
  p_number: string;
  name: string;
  price: number;
  retail_price: number | null;
  material: string | null;
  origin: string | null;
  reorder_period: string | null;
  description: string | null;
  color: string;
  size: string;
  imageFile: File | null;
  imageUrl: string | null;
}

interface PhotoItem {
  id: string;
  file: File;
  previewUrl: string;
}

export default function WholesalerUploadPage() {
  const [rows, setRows] = useState<ExcelRow[]>([]);
  const [photos, setPhotos] = useState<PhotoItem[]>([]);
  const [draggedPhotoId, setDraggedPhotoId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);

  const handleExcelUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (event) => {
      const data = new Uint8Array(event.target?.result as ArrayBuffer);
      const workbook = XLSX.read(data, { type: 'array' });
      const firstSheet = workbook.Sheets[workbook.SheetNames[0]];
      const parsedData = XLSX.utils.sheet_to_json<any>(firstSheet);

      const newRows: ExcelRow[] = parsedData.map((row, index) => ({
        id: `row-${Date.now()}-${index}`,
        p_number: row['품번'] || row['p_number'] || `SKU-${Date.now()}-${index}`,
        name: row['상품명'] || row['name'] || '이름 없음',
        price: parseInt(row['단가'] || row['price'] || '0', 10),
        retail_price: row['권장소비자가'] ? parseInt(row['권장소비자가'], 10) : null,
        material: row['혼용률'] || row['소재'] || null,
        origin: row['제조국'] || null,
        reorder_period: row['리오더기간'] || row['리오더 기간'] || null,
        description: row['상세설명'] || null,
        color: row['색상'] || 'Free',
        size: row['사이즈'] || 'Free',
        imageFile: null,
        imageUrl: null,
      }));

      setRows(newRows);
      setIsSuccess(false);
    };
    reader.readAsArrayBuffer(file);
  };

  const handlePhotosUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    const newPhotos = files.map((file, index) => ({
      id: `img-${Date.now()}-${index}`,
      file,
      previewUrl: URL.createObjectURL(file),
    }));
    setPhotos([...photos, ...newPhotos]);
    setIsSuccess(false);
  };

  const handleReset = () => {
    if (window.confirm('업로드된 모든 파일과 매칭 데이터를 초기화하시겠습니까?')) {
      setRows([]);
      setPhotos([]);
      setIsSuccess(false);
    }
  };

  const handleDragStart = (e: React.DragEvent, photoId: string) => {
    setDraggedPhotoId(photoId);
    e.dataTransfer.effectAllowed = 'move';
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
  };

  const handleDrop = (e: React.DragEvent, rowId: string) => {
    e.preventDefault();
    if (!draggedPhotoId) return;

    const photo = photos.find(p => p.id === draggedPhotoId);
    if (!photo) return;

    setRows(rows.map(row => 
      row.id === rowId ? { ...row, imageFile: photo.file, imageUrl: photo.previewUrl } : row
    ));

    setPhotos(photos.filter(p => p.id !== draggedPhotoId));
    setDraggedPhotoId(null);
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

  const handleSave = async () => {
    if (rows.length === 0) {
      alert('엑셀 데이터를 업로드해주세요.');
      return;
    }
    
    const unmatched = rows.some(r => !r.imageFile);
    if (unmatched) {
      alert('모든 상품에 사진을 매칭해주세요!');
      return;
    }

    setIsLoading(true);
    try {
      for (const row of rows) {
        let uploadedUrl = null;
        if (row.imageFile) {
          uploadedUrl = await uploadImageToStorage(row.imageFile);
        }

        const { data: productData, error: productError } = await supabase
          .from('products')
          .insert([{
            p_number: row.p_number,
            name: row.name,
            price: row.price,
            retail_price: row.retail_price,
            material: row.material,
            origin: row.origin,
            reorder_period: row.reorder_period,
            description: row.description,
            main_image_url: uploadedUrl,
            image_urls: uploadedUrl ? [uploadedUrl] : []
          }])
          .select()
          .single();

        if (productError) throw productError;

        const { error: skuError } = await supabase
          .from('product_skus')
          .insert([{
            product_id: productData.id,
            color: row.color,
            size: row.size,
            allocated_stock: 50, // 기본 할당
          }]);

        if (skuError) throw skuError;
      }

      setIsSuccess(true);
      setRows([]);
      setPhotos([]);
    } catch (error) {
      console.error(error);
      alert('저장 중 오류가 발생했습니다.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="bg-zinc-50 min-h-screen flex flex-col">
      <Header 
        title="📦 엑셀 매칭 대량 업로드" 
        onReset={handleReset} 
        isResetDisabled={isLoading} 
      />

      <main className="flex-1 p-4 md:p-8 max-w-6xl mx-auto w-full">
        {isSuccess && (
          <div className="bg-green-50 border border-green-200 rounded-2xl p-6 mb-8 flex items-center gap-4 animate-in fade-in slide-in-from-top-4">
            <CheckCircle className="w-8 h-8 text-green-500" />
            <div>
              <h3 className="text-lg font-bold text-green-900">대량 등록이 성공적으로 완료되었습니다!</h3>
              <p className="text-green-700 text-sm">새로운 엑셀 파일을 업로드하여 계속 진행할 수 있습니다.</p>
            </div>
          </div>
        )}

        {/* 액션 바 */}
        <div className="flex flex-col md:flex-row gap-4 mb-8">
          <label className={`flex-1 bg-white border-2 ${rows.length > 0 ? 'border-green-500' : 'border-zinc-300 border-dashed hover:border-black'} rounded-2xl p-6 flex flex-col items-center justify-center cursor-pointer transition-colors group`}>
            <FileSpreadsheet className={`w-8 h-8 mb-3 ${rows.length > 0 ? 'text-green-500' : 'text-zinc-400 group-hover:text-black'}`} />
            <div className="font-bold text-lg mb-1">{rows.length > 0 ? `${rows.length}개 상품 로드됨` : '1. 엑셀 파일 업로드'}</div>
            <div className="text-zinc-500 text-sm">(.xlsx 파일 선택)</div>
            <input type="file" accept=".xlsx, .csv" className="hidden" onChange={handleExcelUpload} disabled={isLoading} />
          </label>
          
          <label className={`flex-1 bg-white border-2 ${photos.length > 0 ? 'border-blue-500' : 'border-zinc-300 border-dashed hover:border-black'} rounded-2xl p-6 flex flex-col items-center justify-center cursor-pointer transition-colors group`}>
            <ImageIcon className={`w-8 h-8 mb-3 ${photos.length > 0 ? 'text-blue-500' : 'text-zinc-400 group-hover:text-black'}`} />
            <div className="font-bold text-lg mb-1">{photos.length > 0 ? `${photos.length}장 미아 사진 대기중` : '2. 미아 사진 여러장 업로드'}</div>
            <div className="text-zinc-500 text-sm">(드래그 앤 드롭용 폴더 업로드)</div>
            <input type="file" multiple accept="image/*" className="hidden" onChange={handlePhotosUpload} disabled={isLoading} />
          </label>
        </div>

        <div className="grid lg:grid-cols-3 gap-8">
          {/* 엑셀 파싱 테이블 영역 */}
          <div className="lg:col-span-2 bg-white rounded-3xl shadow-sm border border-zinc-200 overflow-hidden flex flex-col">
            <div className="bg-zinc-50 px-6 py-5 border-b border-zinc-200 flex justify-between items-center">
              <h2 className="font-bold text-zinc-800 flex items-center gap-2">
                📄 매칭 보드 <span className="text-sm font-normal text-zinc-500">(사진을 우측에서 끌어다 놓으세요)</span>
              </h2>
            </div>
            
            <div className="p-6 overflow-y-auto max-h-[600px] flex-1 bg-zinc-50/50">
              {rows.length === 0 ? (
                <div className="text-center text-zinc-400 py-20 flex flex-col items-center">
                  <FileSpreadsheet className="w-12 h-12 mb-4 opacity-50" />
                  엑셀 파일을 업로드하면 이곳에 표가 생성됩니다.
                </div>
              ) : (
                <div className="space-y-4">
                  {rows.map(row => (
                    <div 
                      key={row.id} 
                      className={`flex items-center justify-between p-4 bg-white border-2 rounded-2xl transition-all
                        ${row.imageUrl ? 'border-green-500 shadow-sm' : 'border-zinc-200 border-dashed hover:border-blue-500'}
                      `}
                      onDragOver={handleDragOver}
                      onDrop={(e) => handleDrop(e, row.id)}
                    >
                      <div className="flex-1 min-w-0 pr-4">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="bg-zinc-100 text-xs font-bold px-2 py-1 rounded text-zinc-600 truncate max-w-[150px]">{row.p_number}</span>
                          {row.imageUrl && <span className="bg-green-100 text-green-700 text-xs font-bold px-2 py-1 rounded flex-shrink-0">매칭 완료</span>}
                        </div>
                        <p className="text-lg font-bold text-zinc-900 truncate">{row.name}</p>
                        <div className="flex flex-wrap gap-x-3 gap-y-1 mt-1 text-sm text-zinc-500">
                          <span>{row.price.toLocaleString()}원</span>
                          {row.color && <span>• {row.color}</span>}
                          {row.size && <span>• {row.size}</span>}
                          {row.origin && <span>• {row.origin}</span>}
                        </div>
                      </div>
                      
                      <div className={`w-24 h-24 rounded-xl flex items-center justify-center overflow-hidden border-2 transition-colors flex-shrink-0
                        ${row.imageUrl ? 'border-green-500' : 'border-zinc-100 bg-zinc-100'}
                      `}>
                        {row.imageUrl ? (
                          <img src={row.imageUrl} alt={row.name} className="w-full h-full object-cover" />
                        ) : (
                          <div className="text-center">
                            <UploadCloud className="w-6 h-6 text-zinc-400 mx-auto mb-1" />
                            <span className="text-zinc-400 text-[10px] font-bold">DROP HERE</span>
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
            
            {rows.length > 0 && (
              <div className="p-4 border-t border-zinc-200 bg-white flex gap-4">
                <button 
                  onClick={handleReset}
                  disabled={isLoading}
                  className="w-1/3 bg-white border-2 border-zinc-200 text-zinc-700 py-4 rounded-xl text-lg font-bold hover:bg-zinc-50 transition-colors disabled:opacity-50"
                >
                  취소 (초기화)
                </button>
                <button 
                  onClick={handleSave}
                  disabled={isLoading}
                  className="w-2/3 bg-black text-white px-6 py-4 rounded-xl text-lg hover:bg-zinc-800 transition-colors font-bold disabled:bg-zinc-400 flex justify-center items-center gap-2 shadow-md"
                >
                  {isLoading ? (
                    <>
                      <Loader2 className="w-6 h-6 animate-spin" />
                      클라우드 일괄 저장 중...
                    </>
                  ) : (
                    <>
                      🚀 확인 (전체 일괄 저장)
                    </>
                  )}
                </button>
              </div>
            )}
          </div>

          {/* 미매칭 사진 갤러리 */}
          <div className="bg-white rounded-3xl shadow-sm border border-zinc-200 overflow-hidden flex flex-col h-[700px]">
            <div className="bg-zinc-50 px-6 py-5 border-b border-zinc-200">
              <h2 className="font-bold text-zinc-800 flex items-center gap-2">
                🖼️ 미매칭 갤러리
                <span className="bg-black text-white text-xs px-2 py-1 rounded-full">{photos.length}</span>
              </h2>
            </div>
            <div className="p-4 overflow-y-auto flex-1 grid grid-cols-2 gap-3 content-start bg-zinc-100/50">
              {photos.length === 0 ? (
                <div className="col-span-2 text-center text-zinc-400 py-20 flex flex-col items-center">
                  <ImageIcon className="w-12 h-12 mb-4 opacity-50" />
                  대기 중인 사진이 없습니다.
                </div>
              ) : (
                photos.map(photo => (
                  <div 
                    key={photo.id}
                    draggable
                    onDragStart={(e) => handleDragStart(e, photo.id)}
                    className="cursor-move group relative transform hover:-translate-y-1 hover:shadow-lg transition-all rounded-xl overflow-hidden border border-zinc-200 bg-white"
                  >
                    <img src={photo.previewUrl} alt="Unmatched" className="w-full aspect-square object-cover pointer-events-none" />
                    <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                      <GripVertical className="w-8 h-8 text-white" />
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
