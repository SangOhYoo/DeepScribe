import React, { useState, useEffect } from 'react';
import { Trash2, Play, CheckSquare, Square, RefreshCw, Upload, FileImage } from 'lucide-react';

export default function AssetManager({ projectName = "default", onProcessCuts, onSelectCut }) {
  const [cuts, setCuts] = useState([]);
  const [selectedIds, setSelectedIds] = useState(new Set());
  const [isLoading, setIsLoading] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [isDragActive, setIsDragActive] = useState(false);

  useEffect(() => {
    fetchCuts();
  }, [projectName]);

  const fetchCuts = async () => {
    try {
      const res = await fetch(`/api/assets?project_name=${projectName}`);
      const data = await res.json();
      setCuts(data);
    } catch (err) {
      console.error("망가 리스트 조회 오류:", err);
    }
  };

  const toggleSelect = (id) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (selectedIds.size === cuts.length && cuts.length > 0) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(cuts.map(cut => cut.cut_number)));
    }
  };

  const handleBatchProcess = async () => {
    if (selectedIds.size === 0) return alert("분석할 컷을 선택해 주세요.");
    setIsLoading(true);
    try {
      await onProcessCuts(Array.from(selectedIds));
      fetchCuts();
    } catch (err) {
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleBatchDelete = async () => {
    if (selectedIds.size === 0) return;
    if (!confirm("선택한 컷과 해당 분석 데이터를 영구 삭제하시겠습니까?")) return;
    try {
      const res = await fetch('/api/assets/batch-delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          cut_numbers: Array.from(selectedIds),
          project_name: projectName
        })
      });
      if (res.ok) {
        setSelectedIds(new Set());
        fetchCuts();
      }
    } catch (err) {
      console.error("삭제 요청 오류:", err);
    }
  };

  // 드래그 앤 드롭 핸들러 등록
  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setIsDragActive(true);
    } else if (e.type === "dragleave") {
      setIsDragActive(false);
    }
  };

  const handleDrop = async (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragActive(false);
 
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      await uploadFiles(e.dataTransfer.files);
    }
  };

  const handleFileUpload = async (e) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    await uploadFiles(files);
  };

  const uploadFiles = async (files) => {
    setIsUploading(true);
    const formData = new FormData();
    for (let i = 0; i < files.length; i++) {
      formData.append('files', files[i]);
    }

    try {
      const res = await fetch(`/api/assets/upload?project_name=${projectName}`, {
        method: 'POST',
        body: formData
      });
      if (res.ok) {
        fetchCuts();
      }
    } catch (err) {
      console.error("업로드 에러:", err);
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div 
      className="glass-card rounded-xl p-6 shadow-2xl relative overflow-hidden transition-all duration-300"
      onDragEnter={handleDrag}
      onDragOver={handleDrag}
    >
      {/* 프리미엄 드롭 존 오버레이 레이어 */}
      {isDragActive && (
        <div 
          className="absolute inset-0 bg-brand-dark/90 backdrop-blur-md border-2 border-dashed border-indigo-500 rounded-xl z-50 flex flex-col items-center justify-center gap-4 transition-all duration-300"
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
        >
          <div className="w-16 h-16 rounded-full bg-indigo-950/80 border border-indigo-500/30 flex items-center justify-center animate-bounce shadow-2xl">
            <Upload className="w-8 h-8 text-indigo-400" />
          </div>
          <div className="text-center">
            <p className="text-slate-100 font-bold text-base tracking-wide">망가 이미지를 여기에 끌어놓으십시오 (Drop Here)</p>
            <p className="text-slate-400 text-xs mt-1">파일 여러 개를 동시에 떨어뜨려 일괄 업로드할 수 있습니다.</p>
          </div>
        </div>
      )}

      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6 border-b border-slate-800 pb-4">
        <div>
          <h2 className="text-xl font-bold text-slate-100 flex items-center gap-2">
            <span>🖼️ 에셋 매니저</span>
            <span className="text-[10px] tracking-wider px-2 py-0.5 bg-indigo-950 text-indigo-400 border border-indigo-900 rounded font-semibold">BATCH CONTROLLER</span>
          </h2>
          <p className="text-slate-400 text-xs mt-1">업로드된 컷들을 선택하여 AI 분석 파이프라인 일괄 실행 및 삭제 관리를 수행합니다.</p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          {/* 업로드 컴포넌트 */}
          <label className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-slate-200 bg-slate-800 hover:bg-slate-700 rounded-lg cursor-pointer transition">
            <Upload className="w-3.5 h-3.5" />
            <span>{isUploading ? '업로드 중...' : '이미지 추가'}</span>
            <input type="file" multiple accept="image/*" className="hidden" onChange={handleFileUpload} disabled={isUploading} />
          </label>
          
          <button 
            onClick={toggleSelectAll} 
            className="flex items-center gap-1 px-3 py-1.5 text-xs font-semibold text-slate-300 bg-slate-800/60 hover:bg-slate-800 rounded-lg border border-slate-700/80 transition"
          >
            {selectedIds.size === cuts.length && cuts.length > 0 ? (
              <>
                <Square className="w-3.5 h-3.5" />
                <span>선택 해제</span>
              </>
            ) : (
              <>
                <CheckSquare className="w-3.5 h-3.5" />
                <span>전체 선택</span>
              </>
            )}
          </button>
          
          <button 
            onClick={handleBatchProcess}
            disabled={isLoading || selectedIds.size === 0}
            className="flex items-center gap-1.5 px-4 py-1.5 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-500 disabled:bg-slate-800/80 disabled:text-slate-500 rounded-lg transition shadow-lg shadow-indigo-950/60 disabled:shadow-none"
          >
            {isLoading ? (
              <RefreshCw className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Play className="w-3.5 h-3.5 fill-current" />
            )}
            <span>선택 컷 소설 변환</span>
          </button>
          
          <button 
            onClick={handleBatchDelete}
            disabled={selectedIds.size === 0}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-rose-400 bg-rose-950/20 border border-rose-900/40 hover:bg-rose-900 hover:text-white disabled:opacity-30 rounded-lg transition"
          >
            <Trash2 className="w-3.5 h-3.5" />
            <span>선택 삭제</span>
          </button>
        </div>
      </div>

      {cuts.length === 0 ? (
        <div 
          className="py-20 text-center text-slate-500 text-sm border-2 border-dashed border-slate-800/60 hover:border-slate-700/80 rounded-xl bg-slate-950/20 flex flex-col items-center justify-center gap-3 transition cursor-pointer"
          onClick={() => document.querySelector('input[type="file"]').click()}
        >
          <FileImage className="w-10 h-10 text-slate-700 group-hover:text-slate-600" />
          <div>
            <p className="font-semibold text-slate-400 text-sm">업로드된 망가 이미지가 없습니다.</p>
            <p className="text-[11px] text-slate-500 mt-1">이곳에 파일을 끌어다 놓거나 마우스로 클릭하여 추가하십시오.</p>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4 max-h-[480px] overflow-y-auto pr-2 scrollbar-thin">
          {cuts.map(cut => {
            const isSelected = selectedIds.has(cut.cut_number);
            return (
              <div 
                key={cut.cut_number}
                onClick={() => onSelectCut && onSelectCut(cut.cut_number)}
                className={`relative cursor-pointer group rounded-xl overflow-hidden border transition-all duration-300 ${
                  isSelected 
                    ? 'border-indigo-500 ring-2 ring-indigo-500/30 bg-indigo-950/10 shadow-lg' 
                    : 'border-slate-800 hover:border-slate-700 bg-slate-950/60'
                }`}
              >
                <div className="aspect-[3/4] bg-slate-900 relative">
                  {/* 정적 서빙 주소 (cut.file_path)로 직접 바인딩 */}
                  <img 
                    src={cut.file_path} 
                    alt={cut.filename}
                    className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                    onError={(e) => {
                      e.target.src = "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?q=80&w=300&auto=format&fit=crop";
                    }}
                  />
                  
                  {/* 체크박스 레이어 */}
                  <div 
                    className="absolute top-2 left-2 z-10"
                    onClick={(e) => {
                      e.stopPropagation();
                      toggleSelect(cut.cut_number);
                    }}
                  >
                    <div className={`w-5 h-5 rounded-md flex items-center justify-center border transition ${
                      isSelected 
                        ? 'bg-indigo-600 border-indigo-500 text-white' 
                        : 'bg-slate-950/80 border-slate-700 text-transparent hover:border-slate-500'
                    }`}>
                      ✓
                    </div>
                  </div>

                  {/* 하단 캡션 오버레이 */}
                  <div className="absolute bottom-0 inset-x-0 bg-gradient-to-t from-slate-950 via-slate-950/60 to-transparent p-2">
                    <p className="text-[10px] text-slate-400 truncate">{cut.filename}</p>
                  </div>
                  
                  {/* 분석 완료 리본 */}
                  {cut.status === 'completed' && (
                    <div className="absolute top-2 right-2 bg-emerald-500/90 backdrop-blur-sm text-slate-950 text-[9px] font-bold px-2 py-0.5 rounded-full shadow-lg border border-emerald-400/20">
                      변환됨
                    </div>
                  )}
                </div>
                <div className="p-3 flex items-center justify-between text-xs font-semibold text-slate-300 border-t border-slate-900">
                  <span>Cut #{cut.cut_number}</span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
