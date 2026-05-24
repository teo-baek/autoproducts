'use client';

import { useState } from 'react';

// 가상의 엑셀 데이터
const initialExcelRows = [
  { id: 'row-1', p_number: 'A-001', name: '기모 오버핏 후드', price: 35000, imageUrl: null },
  { id: 'row-2', p_number: 'A-002', name: '카고 와이드 팬츠', price: 42000, imageUrl: null },
  { id: 'row-3', p_number: 'B-101', name: '레더 크롭 자켓', price: 89000, imageUrl: null },
];

// 가상의 미아(매칭 안 된) 사진들
const initialPhotos = [
  { id: 'img-1', url: 'https://via.placeholder.com/150/000000/FFFFFF/?text=Hoodie' },
  { id: 'img-2', url: 'https://via.placeholder.com/150/222222/FFFFFF/?text=Pants' },
  { id: 'img-3', url: 'https://via.placeholder.com/150/444444/FFFFFF/?text=Jacket' },
];

export default function WholesalerUploadPage() {
  const [rows, setRows] = useState(initialExcelRows);
  const [photos, setPhotos] = useState(initialPhotos);
  const [draggedPhotoId, setDraggedPhotoId] = useState<string | null>(null);

  const handleDragStart = (e: React.DragEvent, photoId: string) => {
    setDraggedPhotoId(photoId);
    e.dataTransfer.effectAllowed = 'move';
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault(); // 필수: 이걸 해야 drop 이벤트가 발생함
    e.dataTransfer.dropEffect = 'move';
  };

  const handleDrop = (e: React.DragEvent, rowId: string) => {
    e.preventDefault();
    if (!draggedPhotoId) return;

    const photo = photos.find(p => p.id === draggedPhotoId);
    if (!photo) return;

    // 해당 행에 사진 매칭
    setRows(rows.map(row => 
      row.id === rowId ? { ...row, imageUrl: photo.url } : row
    ));

    // 매칭된 사진은 하단 갤러리에서 제거
    setPhotos(photos.filter(p => p.id !== draggedPhotoId));
    setDraggedPhotoId(null);
  };

  return (
    <div className="p-8 max-w-6xl mx-auto bg-gray-50 min-h-screen">
      <h1 className="text-3xl font-bold mb-8 text-gray-900">📦 대량 등록 (엑셀 매칭)</h1>

      {/* 상단: 엑셀 테이블 */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden mb-12">
        <div className="bg-gray-100 px-6 py-4 border-b border-gray-200 font-bold text-gray-700">
          📄 엑셀 파싱 데이터 (이미지를 끌어다 놓으세요)
        </div>
        <div className="p-6">
          {rows.map(row => (
            <div 
              key={row.id} 
              className="flex items-center justify-between p-4 mb-4 border-2 border-dashed border-gray-300 rounded-lg hover:border-blue-500 transition-colors"
              onDragOver={handleDragOver}
              onDrop={(e) => handleDrop(e, row.id)}
            >
              <div className="flex-1">
                <p className="text-lg font-bold text-gray-900">{row.name}</p>
                <p className="text-gray-500">품번: {row.p_number} | 단가: {row.price.toLocaleString()}원</p>
              </div>
              
              <div className="w-24 h-24 bg-gray-100 rounded-md flex items-center justify-center overflow-hidden border border-gray-200">
                {row.imageUrl ? (
                  <img src={row.imageUrl} alt={row.name} className="w-full h-full object-cover" />
                ) : (
                  <span className="text-gray-400 text-sm text-center px-2">Drag Image Here</span>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 하단: 미아 사진 갤러리 */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
        <div className="bg-gray-100 px-6 py-4 border-b border-gray-200 font-bold text-gray-700">
          🖼️ 미매칭 사진 갤러리 ({photos.length}장)
        </div>
        <div className="p-6 grid grid-cols-5 gap-4">
          {photos.length === 0 ? (
            <p className="col-span-5 text-center text-gray-500 py-8">모든 사진 매칭 완료! 🎉</p>
          ) : (
            photos.map(photo => (
              <div 
                key={photo.id}
                draggable
                onDragStart={(e) => handleDragStart(e, photo.id)}
                className="cursor-move transform hover:scale-105 transition-transform shadow-md rounded-lg overflow-hidden border border-gray-200"
              >
                <img src={photo.url} alt="Unmatched" className="w-full h-32 object-cover pointer-events-none" />
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
