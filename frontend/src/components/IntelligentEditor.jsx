import React, { useState, useEffect, useRef } from 'react';
import { Eye, Edit3, Check, AlertTriangle, Download, Wand2, Save, RefreshCw, Upload } from 'lucide-react';

function useDebounce(value, delay) {
  const [debouncedValue, setDebouncedValue] = useState(value);
  useEffect(() => {
    const handler = setTimeout(() => setDebouncedValue(value), delay);
    return () => clearTimeout(handler);
  }, [value, delay]);
  return debouncedValue;
}

export default function IntelligentEditor({ 
  initialJson, 
  fileType, 
  onStateChange, 
  onAiAnalyze, 
  onSave, 
  isSaving, 
  promptValue, 
  onPromptChange,
  projects = [],
  activeProject = "",
  onImportFromProject
}) {
  const [jsonString, setJsonString] = useState("");
  const [structuredData, setStructuredData] = useState({});
  const [isValidJson, setIsValidJson] = useState(true);
  const [activeTab, setActiveTab] = useState('split'); // 'split' (필드 분할), 'raw' (JSON 텍스트)

  // 부모 컴포넌트로부터 새 JSON이 로드될 때 바인딩 데이터 업데이트
  useEffect(() => {
    if (initialJson) {
      let data = { ...initialJson };
      
      // 만약 가져온 JSON이 완전히 비어있을 때, 해당 타입의 표준 키를 세팅해 줍니다.
      if (Object.keys(data).length === 0) {
        if (fileType === 'overall_plot') {
          data = { overall_plot: "" };
        } else if (fileType === 'theme_background') {
          data = { theme_background: "" };
        } else if (fileType === 'character_profiles') {
          data = { character_profiles: "" };
        } else if (fileType === 'image_plot') {
          data = {
            scene_description: "",
            camera_angle: "",
            manga_effects: "",
            novel_paragraph: "",
            positive_prompt: "",
            negative_prompt: ""
          };
        }
      }
      
      const formatted = JSON.stringify(data, null, 2);
      setJsonString(formatted);
      setStructuredData(data);
      setIsValidJson(true);
    }
  }, [initialJson, fileType]);

  // 디바운스 딜레이(400ms) 적용 후 상태 상향 전파 (서버 저장용)
  const debouncedData = useDebounce(structuredData, 400);
  useEffect(() => {
    if (onStateChange && Object.keys(debouncedData).length > 0) {
      onStateChange(debouncedData);
    }
  }, [debouncedData]);

  // RAW 텍스트 편집 핸들러
  const handleRawJsonChange = (val) => {
    setJsonString(val);
    try {
      const parsed = JSON.parse(val);
      setStructuredData(parsed);
      setIsValidJson(true);
    } catch (e) {
      setIsValidJson(false); // 구문 오류 시 컴포넌트를 크래시하지 않고 플래그만 노출
    }
  };

  // 개별 키-밸류 필드 수정 핸들러
  const handleFieldChange = (key, val) => {
    const updated = { ...structuredData, [key]: val };
    setStructuredData(updated);
    setJsonString(JSON.stringify(updated, null, 2));
  };

  // 개별 문서 및 컷별 속성의 TXT 파일 다운로드 로직
  const handleExportTxt = () => {
    let content = "";
    
    // 각 구조화된 키 값을 구분선과 함께 한국어 번역 설명과 묶어서 다운로드 텍스트 빌드
    Object.entries(structuredData).forEach(([key, val]) => {
      content += `=== ${getFieldLabel(key)} (${key}) ===\n`;
      content += `${val}\n\n`;
    });
    
    if (!content.trim()) {
      alert("내보낼 텍스트 내용이 없습니다.");
      return;
    }
    
    const element = document.createElement("a");
    const file = new Blob([content], { type: 'text/plain;charset=utf-8' });
    element.href = URL.createObjectURL(file);
    element.download = `${fileType || 'state'}_export.txt`;
    document.body.appendChild(element);
    element.click();
    document.body.removeChild(element);
  };


  // 한글 친화적인 필드 설명 라벨 반환 맵
  const getFieldLabel = (key) => {
    const labels = {
      overall_plot: "전체 시나리오 및 기하학적 체위 전개",
      scene_description: "장면 구조 해체 데이터 (체위/앵글/대사)",
      camera_angle: "구도 및 카메라 앵글 시각 연출",
      manga_effects: "인체 충돌 및 지배적 체위 상호작용",
      novel_paragraph: "최종 소설 본문 (Korean Novel Paragraph)",
      positive_prompt: "Flux/SD 생성용 프롬프트 (영어)",
      negative_prompt: "부정 프롬프트 (Negative Prompt)",
      theme_background: "세계관 및 에로틱 배경 설정",
      character_profiles: "등장인물 성향 및 인물 관계 정보"
    };
    return labels[key] || key.toUpperCase().replace('_', ' ');
  };

  const buttonLabel = () => {
    if (fileType === 'image_plot') return "AI 컷 소설화 생성";
    if (fileType === 'overall_plot' || fileType === 'theme_background' || fileType === 'character_profiles') return "AI 초안 생성";
    return null;
  };

  return (
    <div className="glass-card rounded-xl p-6 shadow-2xl flex flex-col h-full">
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 border-b border-slate-800 pb-4 mb-4">
        <div className="min-w-0">
          <h2 className="text-xl font-bold text-slate-100 flex items-center gap-2 flex-wrap sm:flex-nowrap whitespace-nowrap">
            <span>📝 지능형 양방향 에디터</span>
            <span className="text-[10px] tracking-wider px-2 py-0.5 bg-emerald-950 text-emerald-400 border border-emerald-900 rounded font-semibold whitespace-nowrap">LIVE BINDING</span>
          </h2>
          <p className="text-slate-400 text-xs mt-1">JSON 구조 데이터와 입력 텍스트 영역이 실시간 상호 양방향 동기화됩니다.</p>
        </div>
        <div className="flex items-center gap-1.5 flex-wrap justify-start lg:justify-end">
          {/* AI 분석 초안 생성 버튼 (전체줄거리, 컷별묘사, 세계관배경, 등장인물관계 전체 노출) */}
          {buttonLabel() && (
            <button
              onClick={onAiAnalyze}
              title={
                fileType === 'image_plot'
                  ? "AI 비전 분석을 통해 현재 컷의 소설 단락 및 묘사를 자동 생성합니다."
                  : "AI 비전 분석을 통해 대표 이미지로부터 초안 설정을 추출하여 삽입합니다."
              }
              className="flex items-center gap-1 px-2.5 py-1 text-[11px] font-semibold rounded-lg text-emerald-400 bg-emerald-950/40 hover:bg-emerald-950/80 border border-emerald-900/60 hover:border-emerald-800 shadow-md shadow-emerald-950/20 transition whitespace-nowrap"
            >
              <Wand2 className="w-3 h-3 animate-pulse text-emerald-400" />
              <span>{buttonLabel()}</span>
            </button>
          )}

          {/* TXT 추출 버튼 */}
          <button
            onClick={handleExportTxt}
            title="현재 활성화된 탭의 분석 및 편집 텍스트를 TXT 파일로 다운로드합니다."
            className="flex items-center gap-1 px-2.5 py-1 text-[11px] font-semibold rounded-lg text-indigo-400 bg-indigo-950/40 hover:bg-indigo-950/80 border border-indigo-900/60 hover:border-indigo-800 transition whitespace-nowrap"
          >
            <Download className="w-3 h-3" />
            <span>TXT 추출</span>
          </button>

          {/* 가져오기 드롭다운 (컷별 묘사 제외) */}
          {fileType !== 'image_plot' && (
            <div className="flex items-center gap-1 bg-slate-950 px-2 py-1 rounded-lg border border-slate-800 text-[11px] text-slate-400 whitespace-nowrap h-[28px]">
              <Upload className="w-3.5 h-3.5 text-indigo-400" />
              <span>가져오기:</span>
              <select
                value=""
                onChange={(e) => {
                  if (e.target.value) {
                    onImportFromProject(e.target.value);
                  }
                }}
                className="bg-slate-900 border border-slate-700 text-indigo-300 font-bold rounded px-1 focus:outline-none text-[11px] cursor-pointer"
              >
                <option value="" disabled>선택...</option>
                {projects
                  .filter((p) => p !== activeProject)
                  .map((p) => (
                    <option key={p} value={p}>
                      {p}
                    </option>
                  ))}
              </select>
            </div>
          )}

          {/* 저장 (Save) 버튼 */}
          <button
            onClick={onSave}
            disabled={isSaving}
            title="현재 활성화된 탭의 수정 사항을 수동으로 저장합니다."
            className="flex items-center gap-1 px-2.5 py-1 text-[11px] font-bold rounded-lg text-emerald-400 bg-emerald-950/40 hover:bg-emerald-950/80 border border-emerald-900/60 hover:border-emerald-800 disabled:opacity-50 transition whitespace-nowrap"
          >
            {isSaving ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Save className="w-3 h-3" />}
            <span>저장 (Save)</span>
          </button>
          
          <div className="flex items-center gap-1 bg-slate-950/80 p-0.5 rounded-lg border border-slate-800 h-[28px]">
            <button
              onClick={() => setActiveTab('split')}
              className={`flex items-center gap-1 px-2.5 py-1.5 text-[11px] font-semibold rounded-md transition whitespace-nowrap ${
                activeTab === 'split' ? 'bg-indigo-600 text-white' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Edit3 className="w-3.5 h-3.5" />
              <span>필드 분할 뷰</span>
            </button>
            <button
              onClick={() => setActiveTab('raw')}
              className={`flex items-center gap-1 px-2.5 py-1.5 text-[11px] font-semibold rounded-md transition whitespace-nowrap ${
                activeTab === 'raw' ? 'bg-indigo-600 text-white' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Eye className="w-3.5 h-3.5" />
              <span>Raw JSON</span>
            </button>
          </div>
        </div>
      </div>

      {/* 탭 전용 AI 지시 프롬프트 영역 */}
      {promptValue !== undefined && onPromptChange && (
        <div className="mb-5 bg-slate-950/60 p-4 rounded-xl border border-indigo-950/60 flex flex-col gap-2 shadow-inner">
          <div className="flex items-center justify-between">
            <label className="text-xs font-bold text-indigo-400 tracking-wider flex items-center gap-1.5">
              <Wand2 className="w-3.5 h-3.5 text-indigo-400" />
              <span>현재 탭 전용 AI 지시 프롬프트 (Tab-Specific AI Prompt)</span>
            </label>
            <span className="text-[10px] text-slate-500 font-mono">이 탭의 AI 추론 및 초안 생성 시 반영됩니다.</span>
          </div>
          <textarea
            value={promptValue}
            onChange={(e) => onPromptChange(e.target.value)}
            placeholder="AI에게 지시할 해당 탭 고유의 세부 요구사항(예: 특정 어조, 강조할 정보, 스타일 등)을 기입하세요..."
            className="w-full bg-slate-950 border border-slate-800/80 rounded-lg p-3 text-slate-300 text-xs focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/30 resize-none min-h-[56px] scrollbar-thin transition"
          />
        </div>
      )}

      <div className="flex-1 min-h-[400px]">
        {activeTab === 'split' ? (
          <div className="space-y-4 h-full overflow-y-auto max-h-[520px] pr-2 scrollbar-thin">
            {Object.keys(structuredData).length === 0 ? (
              <div className="h-[300px] flex items-center justify-center text-slate-500 text-sm">
                편집할 수 있는 데이터 파일 설정이 비어 있습니다.
              </div>
            ) : (
              Object.keys(structuredData).map((key) => (
                <div key={key} className="flex flex-col gap-2 bg-slate-950/40 p-4 rounded-lg border border-slate-800/80">
                  <label className="text-xs font-bold text-slate-400 tracking-wider flex items-center gap-1.5">
                    <span className="w-1.5 h-1.5 bg-indigo-500 rounded-full"></span>
                    {getFieldLabel(key)}
                    <span className="text-[9px] text-slate-600 font-mono">({key})</span>
                  </label>
                  <textarea
                    value={structuredData[key] || ""}
                    onChange={(e) => handleFieldChange(key, e.target.value)}
                    className={`w-full bg-slate-950 border border-slate-800 rounded-lg p-3 text-slate-200 text-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/30 resize-y scrollbar-thin ${
                      (key === 'overall_plot' || key === 'theme_background' || key === 'character_profiles')
                        ? 'min-h-[400px]'
                        : 'min-h-[100px]'
                    }`}
                  />
                </div>
              ))
            )}
          </div>
        ) : (
          <div className="relative h-full flex flex-col">
            <textarea
              value={jsonString}
              onChange={(e) => handleRawJsonChange(e.target.value)}
              className={`w-full flex-1 bg-slate-950 border rounded-lg p-4 font-mono text-xs text-indigo-300 focus:outline-none focus:ring-1 min-h-[420px] scrollbar-thin ${
                isValidJson ? 'border-slate-800 focus:border-indigo-500 focus:ring-indigo-500/30' : 'border-rose-500 focus:ring-rose-500/30'
              }`}
            />
            {isValidJson ? (
              <div className="absolute bottom-4 right-4 bg-emerald-950/80 border border-emerald-800/80 px-3 py-1.5 rounded-lg shadow-lg text-xs font-semibold text-emerald-300 flex items-center gap-1">
                <Check className="w-3.5 h-3.5" />
                <span>정상적인 JSON 규격</span>
              </div>
            ) : (
              <div className="absolute bottom-4 right-4 bg-rose-950/90 border border-rose-800/80 px-3 py-1.5 rounded-lg shadow-lg text-xs font-semibold text-rose-300 flex items-center gap-1">
                <AlertTriangle className="w-3.5 h-3.5 animate-bounce" />
                <span>JSON 형식 에러 (파싱 중단)</span>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
