import React, { useState, useEffect, useRef } from 'react';
import { BookOpen, Film, Landmark, Users, Save, CheckCircle, AlertCircle, RefreshCw, Download, Trash2, Wand2, Copy } from 'lucide-react';
import AssetManager from './components/AssetManager';
import IntelligentEditor from './components/IntelligentEditor';
import HistoryPanel from './components/HistoryPanel';
import PromptController from './components/PromptController';

export default function App() {
  // 활성화된 편집 문서 타입 ('overall_plot', 'image_plot', 'theme_background', 'character_profiles')
  const [activeFileType, setActiveFileType] = useState('overall_plot');
  const [activeCutNum, setActiveCutNum] = useState(1);
  
  // 다중 프로젝트 관리 상태
  const [projects, setProjects] = useState(['default']);
  const [activeProject, setActiveProject] = useState('default');
  
  // 편집 중인 실시간 데이터 및 에러 상태
  const [currentData, setCurrentData] = useState({});
  const [revisionHistory, setRevisionHistory] = useState([]);
  const [currentRevisionNum, setCurrentRevisionNum] = useState(null);
  const [fullNovelText, setFullNovelText] = useState("");
  
  // 각 탭별 및 원고 전용 AI 지시 프롬프트 상태
  const [tabPrompts, setTabPrompts] = useState({
    overall_plot: "전체적인 스토리 라인을 긴장감 넘치고 흥미진진하게 완성해줘.",
    image_plot: "캐릭터간의 대화 어투를 끈적한 구어체로 현지화해주고, 각 컷의 물리적 접촉과 체위 구도를 상세하게 묘사해줘.",
    theme_background: "세계관 설정과 성인 코믹스에 맞춤화된 에로틱한 분위기를 세부 배경 묘사에 녹여내줘.",
    character_profiles: "인물들의 나이, 체형, 성적 욕망 및 지배/피지배 성향 간의 상호 관계를 자세히 서술해줘.",
    novel_manuscript: "전체 소설 원고의 어조를 매끄럽고 윤기 나게 다음어주고, 문맥 연결이 끊어지지 않게 고쳐줘."
  });

  const [isRefiningNovel, setIsRefiningNovel] = useState(false);

  // 실시간 AI 일괄 처리 진행 상태 데이터
  const [processingProgress, setProcessingProgress] = useState({
    active: false,
    total: 0,
    current: 0,
    currentCut: null,
    statusText: ""
  });

  const cancelProcessingRef = useRef(false);
  const novelTextareaRef = useRef(null);

  const handleCancelProcessing = () => {
    cancelProcessingRef.current = true;
    showNotification("작업 중단 요청 중... 현재 진행 중인 컷이 완료되면 즉시 정지합니다.", "info");
  };

  // 대시보드 상태 알림 메시지
  const [alertInfo, setAlertInfo] = useState({ text: "", type: "" }); // type: 'success', 'error', 'info'
  const [isSaving, setIsSaving] = useState(false);

  // 생성 소설 완성본 마스터 원고 버전 관리 상태
  const [masterNovelHistory, setMasterNovelHistory] = useState([]);
  const [currentMasterNovelRevision, setCurrentMasterNovelRevision] = useState(null);

  // 클립보드 복사 시 [Cut #...] 헤더 제외 여부 상태
  const [excludeCutHeaders, setExcludeCutHeaders] = useState(false);

  // 컴포넌트 최초 기동 및 활성 프로젝트 변경 시 프로젝트 목록 갱신
  useEffect(() => {
    fetchProjects();
  }, [activeProject]);

  // 타겟 문서 유형, 활성 컷 번호, 또는 프로젝트 세션 변경 시 최신 상태 로드
  useEffect(() => {
    loadActiveStateData();
    loadMasterNovelData();
  }, [activeFileType, activeCutNum, activeProject]);

  const showNotification = (text, type = "success") => {
    setAlertInfo({ text, type });
    setTimeout(() => setAlertInfo({ text: "", type: "" }), 3500);
  };

  const fetchProjects = async () => {
    try {
      const res = await fetch('/api/state/projects');
      if (res.ok) {
        const list = await res.json();
        setProjects(list);
      }
    } catch (err) {
      console.error("프로젝트 목록 로드 에러:", err);
    }
  };

  const handleCreateProject = async () => {
    const newName = prompt("새로운 소설 작업의 프로젝트 이름을 입력하세요 (공백/특수문자 제외 권장):");
    if (!newName) return;
    const trimmed = newName.trim();
    if (!trimmed) return;

    try {
      const res = await fetch('/api/state/project/new', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ new_project_name: trimmed })
      });
      const result = await res.json();
      if (res.ok) {
        showNotification(`새 작업 [${trimmed}] 프로젝트가 생성되어 활성화되었습니다.`);
        await fetchProjects();
        setActiveProject(trimmed);
        setActiveFileType('overall_plot');
        setActiveCutNum(1);
      } else {
        alert(result.detail || "작업 생성 중 에러가 발생했습니다.");
      }
    } catch (err) {
      console.error("새 프로젝트 생성 요청 오류:", err);
      showNotification("네트워크 오류 발생", "error");
    }
  };

  const handleDeleteProject = async () => {
    if (!confirm(`현재 선택된 작업 [${activeProject}]을 완전히 삭제하시겠습니까?\n데이터베이스 히스토리 및 해당 이미지 폴더들이 영구 삭제되며 복구할 수 없습니다.`)) {
      return;
    }

    try {
      const res = await fetch(`/api/state/project/${activeProject}`, {
        method: 'DELETE'
      });
      const result = await res.json();
      if (res.ok) {
        showNotification(`작업 [${activeProject}]이 영구 삭제되었습니다.`, "success");
        
        // 프로젝트 목록 갱신
        await fetchProjects();
        
        // 삭제 후 'default' 또는 남아있는 프로젝트 중 하나로 복귀
        setActiveProject('default');
        setActiveFileType('overall_plot');
        setActiveCutNum(1);
      } else {
        alert(result.detail || "작업 삭제 중 오류가 발생했습니다.");
      }
    } catch (err) {
      console.error("프로젝트 삭제 요청 오류:", err);
      showNotification("네트워크 오류 발생", "error");
    }
  };

  const fetchFullNovel = async () => {
    try {
      const res = await fetch(`/api/state/novel/full?project_name=${activeProject}`);
      if (res.ok) {
        const data = await res.json();
        let rawNovel = data.full_novel || "아직 변환 완료되어 생성된 소설 단락이 없습니다. 에셋 매니저에서 컷 변환을 먼저 수행해 주십시오.";
        const formattedNovel = rawNovel.replace(/\\n/g, '\n');
        setFullNovelText(formattedNovel);
      }
    } catch (err) {
      console.error("전체 소설 로드 에러:", err);
    }
  };

  const handleDownloadNovelTxt = () => {
    if (!fullNovelText || fullNovelText.startsWith("아직 변환 완료")) {
      alert("다운로드할 소설 원고 내용이 없습니다.");
      return;
    }
    
    let downloadText = fullNovelText;
    if (excludeCutHeaders) {
      downloadText = downloadText.replace(/\[Cut\s*#\d+\]\r?\n?/gi, '');
      downloadText = downloadText.replace(/\n{3,}/g, '\n\n').trim();
    }

    // 윈도우(Windows) 메모장과의 완벽한 줄바꿈 호환을 위해 \n 개행을 \r\n (CRLF) 포맷으로 일괄 교환
    const windowsFormattedText = downloadText.replace(/\r?\n/g, '\r\n');
    
    const element = document.createElement("a");
    const file = new Blob([windowsFormattedText], { type: 'text/plain;charset=utf-8' });
    element.href = URL.createObjectURL(file);
    element.download = `novel_manuscript_${activeProject}.txt`;
    document.body.appendChild(element);
    element.click();
    document.body.removeChild(element);
  };

  const handleCopyNovelToClipboard = async () => {
    if (!fullNovelText || fullNovelText.startsWith("아직 변환 완료")) {
      showNotification("복사할 소설 원고 내용이 없습니다.", "error");
      return;
    }
    try {
      let copyText = fullNovelText;
      if (excludeCutHeaders) {
        copyText = copyText.replace(/\[Cut\s*#\d+\]\r?\n?/gi, '');
        copyText = copyText.replace(/\n{3,}/g, '\n\n').trim();
      }
      await navigator.clipboard.writeText(copyText);
      showNotification(excludeCutHeaders ? "Cut 번호가 제외된 순수 소설 원고가 복사되었습니다!" : "소설 원고 전체가 클립보드에 복사되었습니다!", "success");
    } catch (err) {
      console.error(err);
      showNotification("클립보드 복사 중 오류가 발생했습니다.", "error");
    }
  };

  const loadMasterNovelData = async () => {
    try {
      const res = await fetch(`/api/state/master_novel?project_name=${activeProject}`);
      if (res.ok) {
        const data = await res.json();
        if (data && data.master_novel) {
          setFullNovelText(data.master_novel);
        } else {
          await fetchFullNovel();
        }
      } else {
        await fetchFullNovel();
      }
      await loadMasterNovelHistory();
    } catch (err) {
      console.error(err);
      await fetchFullNovel();
    }
  };

  const loadMasterNovelHistory = async () => {
    try {
      const res = await fetch(`/api/state/master_novel/history?project_name=${activeProject}`);
      if (res.ok) {
        const historyData = await res.json();
        setMasterNovelHistory(historyData);
        if (historyData.length > 0) {
          setCurrentMasterNovelRevision(historyData[0].revision);
        } else {
          setCurrentMasterNovelRevision(null);
        }
      }
    } catch (err) {
      console.error(err);
    }
  };

  const handleRollbackMasterNovel = async (targetRev) => {
    if (!confirm(`소설 원고를 리비전 v${targetRev} 버전으로 롤백 복원하시겠습니까?`)) {
      return;
    }
    try {
      const res = await fetch(`/api/state/master_novel/rollback/${targetRev}?project_name=${activeProject}`, {
        method: 'POST'
      });
      if (res.ok) {
        const data = await res.json();
        if (data && data.master_novel) {
          setFullNovelText(data.master_novel);
          showNotification(`v${targetRev} 버전 상태로 소설 원고 복원 성공`, "success");
        }
        await loadMasterNovelHistory();
      } else {
        showNotification("롤백 처리에 실패했습니다.", "error");
      }
    } catch (err) {
      console.error(err);
      showNotification("롤백 네트워크 요청 오류", "error");
    }
  };

  const handleSaveMasterNovel = async () => {
    setIsSaving(true);
    try {
      const payload = {
        project_name: activeProject,
        data: { master_novel: fullNovelText },
        cut_number: null,
        author: 'user',
        change_description: '생성 소설 완성본 원고 수동 수정 및 저장'
      };

      const res = await fetch(`/api/state/master_novel`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (res.ok) {
        showNotification("소설 완성본 원고가 저장되어 새 리비전이 생성되었습니다.", "success");
        await loadMasterNovelHistory();
      } else {
        showNotification("원고 저장에 실패했습니다.", "error");
      }
    } catch (err) {
      console.error(err);
      showNotification("네트워크 오류 발생", "error");
    } finally {
      setIsSaving(false);
    }
  };

  const loadActiveStateData = async () => {
    try {
      let url = `/api/state/${activeFileType}?project_name=${activeProject}`;
      if (activeFileType === 'image_plot') {
        url += `&cut_number=${activeCutNum}`;
      }
      
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        setCurrentData(data);
      }

      // 버전 히스토리 로그도 병행 로딩
      let historyUrl = `/api/state/${activeFileType}/history?project_name=${activeProject}`;
      if (activeFileType === 'image_plot') {
        historyUrl += `&cut_number=${activeCutNum}`;
      }
      
      const historyRes = await fetch(historyUrl);
      if (historyRes.ok) {
        const historyData = await historyRes.json();
        setRevisionHistory(historyData);
        if (historyData.length > 0) {
          setCurrentRevisionNum(historyData[0].revision); // 가장 최신 리비전을 마크
        } else {
          setCurrentRevisionNum(null);
        }
      }
      
      // 전체 소설 데이터도 실시간 동기화
      fetchFullNovel();
    } catch (err) {
      console.error("데이터 초기 로드 에러:", err);
      showNotification("데이터 로드 중 에러 발생", "error");
    }
  };

  // 에디터 컴포넌트 내부 변경 핸들러
  const handleEditorDataChange = (updatedData) => {
    setCurrentData(updatedData);
  };

  // 다른 프로젝트로부터 설정 파일 데이터 복제/가져오기 핸들러
  const handleImportFromProject = async (targetProject) => {
    try {
      let url = `/api/state/${activeFileType}?project_name=${targetProject}`;
      if (activeFileType === 'image_plot') {
        url += `&cut_number=${activeCutNum}`;
      }
      
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        if (Object.keys(data).length === 0) {
          showNotification(`작업 [${targetProject}]의 해당 탭에 데이터가 없습니다.`, "error");
          return;
        }
        setCurrentData(data);
        showNotification(`작업 [${targetProject}]의 해당 설정 데이터를 성공적으로 가져왔습니다!`, "success");
      } else {
        showNotification("선택한 작업의 데이터를 가져오는 데 실패했습니다.", "error");
      }
    } catch (err) {
      console.error("가져오기 에러:", err);
      showNotification("네트워크 오류가 발생했습니다.", "error");
    }
  };

  // AI 초안 분석 자동 실행 액션
  const handleAiDraftAnalysis = async () => {
    if (activeFileType === 'image_plot') {
      // 컷별 묘사의 경우, 현재 컷 번호를 단독 가공하는 파이프라인으로 연결
      await handleProcessCuts([activeCutNum]);
      return;
    }
    
    setIsSaving(true);
    setProcessingProgress({
      active: true,
      total: 1,
      current: 0,
      currentCut: activeFileType === 'overall_plot' ? '전체 줄거리' : (activeFileType === 'theme_background' ? '세계관 배경' : '인물 프로필'),
      statusText: "대표 이미지를 로드하여 AI 비전 분석 초안을 추출하고 있습니다. 잠시만 기다려 주십시오..."
    });
    
    try {
      let typePath = "";
      let customPrompt = "";
      if (activeFileType === 'overall_plot') {
        typePath = 'plot';
        customPrompt = tabPrompts.overall_plot;
      } else if (activeFileType === 'theme_background') {
        typePath = 'theme';
        customPrompt = tabPrompts.theme_background;
      } else if (activeFileType === 'character_profiles') {
        typePath = 'characters';
        customPrompt = tabPrompts.character_profiles;
      } else {
        showNotification("이 탭에서는 AI 분석 생성을 지원하지 않습니다.", "error");
        setIsSaving(false);
        setProcessingProgress({ active: false, total: 0, current: 0, currentCut: null, statusText: "" });
        return;
      }

      let existingContext = "";
      if (currentData) {
        if (typeof currentData === 'string') {
          existingContext = currentData;
        } else if (activeFileType === 'overall_plot') {
          existingContext = currentData.overall_plot || "";
        } else if (activeFileType === 'theme_background') {
          existingContext = currentData.theme_background || "";
        } else if (activeFileType === 'character_profiles') {
          existingContext = currentData.character_profiles || "";
        } else {
          existingContext = JSON.stringify(currentData);
        }
      }

      const res = await fetch(`/api/inference/analyze/${typePath}?project_name=${activeProject}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          user_prompt: customPrompt,
          existing_context: existingContext
        })
      });

      if (res.ok) {
        showNotification("AI 비전 분석 초안 설정이 완료되어 새로운 리비전이 생성되었습니다.");
        loadActiveStateData(); // 분석 데이터 새로고침
      } else {
        const errData = await res.json();
        showNotification(`분석 실패: ${errData.detail || "알 수 없는 오류"}`, "error");
      }
    } catch (err) {
      console.error("AI 초안 분석 요청 오류:", err);
      showNotification("AI 분석 엔진 통신 중 오류 발생", "error");
    } finally {
      setIsSaving(false);
      setProcessingProgress({ active: false, total: 0, current: 0, currentCut: null, statusText: "" });
    }
  };

  // 수동 저장(POST) 액션 -> 새로운 리비전 버전 데이터 빌드 생성
  const handleManualSave = async () => {
    setIsSaving(true);
    try {
      const payload = {
        project_name: activeProject,
        data: currentData,
        cut_number: activeFileType === 'image_plot' ? activeCutNum : null,
        author: 'user',
        change_description: '작업자에 의한 웹 에디터 수동 수정 저장'
      };

      const res = await fetch(`/api/state/${activeFileType}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (res.ok) {
        showNotification("수정 사항이 저장되어 새 리비전이 생성되었습니다.");
        loadActiveStateData(); // 히스토리 리프레시
      } else {
        showNotification("저장에 실패했습니다.", "error");
      }
    } catch (err) {
      console.error("저장 통신 에러:", err);
      showNotification("네트워크 오류 발생", "error");
    } finally {
      setIsSaving(false);
    }
  };

  // 롤백 복구 처리 액션
  const handleRollback = async (targetRev) => {
    try {
      let url = `/api/state/${activeFileType}/rollback/${targetRev}?project_name=${activeProject}`;
      if (activeFileType === 'image_plot') {
        url += `&cut_number=${activeCutNum}`;
      }

      const res = await fetch(url, { method: 'POST' });
      if (res.ok) {
        showNotification(`리비전 #${targetRev} 버전 상태로 롤백 복원 성공`);
        loadActiveStateData();
      } else {
        showNotification("롤백 처리에 실패했습니다.", "error");
      }
    } catch (err) {
      console.error(err);
      showNotification("롤백 네트워크 요청 오류", "error");
    }
  };

  // 에셋 매니저에서 호출하는 AI 분석 실행 로직 연동 (순차 루프 처리 진행상태 반영)
  const handleProcessCuts = async (cutNumbers) => {
    cancelProcessingRef.current = false; // 플래그 초기화
    
    setProcessingProgress({
      active: true,
      total: cutNumbers.length,
      current: 0,
      currentCut: cutNumbers[0],
      statusText: `AI 컷 변환 파이프라인 가동 개시...`
    });

    let successCount = 0;

    for (let i = 0; i < cutNumbers.length; i++) {
      // 루프 진입 전 취소 여부 검사
      if (cancelProcessingRef.current) {
        break;
      }

      const cutNum = cutNumbers[i];
      setProcessingProgress(prev => ({
        ...prev,
        current: i,
        currentCut: cutNum,
        statusText: `[Cut #${cutNum}] AI 비전 분석 및 관능적 대사/소설 변환 중...`
      }));

      try {
        const res = await fetch('/api/inference/run', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            project_name: activeProject,
            cut_numbers: [cutNum],
            user_prompt: tabPrompts.image_plot,
            existing_context: (activeFileType === 'image_plot' && activeCutNum === cutNum && currentData)
              ? JSON.stringify(currentData)
              : ""
          })
        });

        const result = await res.json();
        if (res.ok) {
          successCount++;
          showNotification(`[Cut #${cutNum}] 변환 성공!`, "success");
          // 각 컷 완료 시마다 실시간으로 에디터 데이터 및 완성 소설 로드
          loadActiveStateData();
        } else {
          showNotification(`[Cut #${cutNum}] 변환 오류: ${result.detail || "오류"}`, "error");
        }
      } catch (err) {
        console.error(err);
        showNotification(`[Cut #${cutNum}] 통신 오류가 발생했습니다.`, "error");
      }
    }

    setProcessingProgress({
      active: false,
      total: 0,
      current: 0,
      currentCut: null,
      statusText: ""
    });

    if (cancelProcessingRef.current) {
      showNotification(`작업이 중단되었습니다. 중단 시점까지 총 ${successCount}개 컷 변환 완료.`, "info");
    } else {
      showNotification(`일괄 변환 완료: 총 ${successCount}개 컷 변환 성공!`, "success");
    }
    
    // 최종 상태 갱신
    loadActiveStateData();
  };

  // 완성본 소설 원고 재교열/윤문(Polish) AI 실행
  const handleRefineNovel = async () => {
    if (!fullNovelText || fullNovelText.startsWith("아직 변환 완료")) {
      alert("교열할 소설 원고 내용이 없습니다. 먼저 에셋 매니저에서 컷 변환을 수행해주세요.");
      return;
    }
    
    setIsRefiningNovel(true);
    setProcessingProgress({
      active: true,
      total: 1,
      current: 0,
      currentCut: "전체 소설 원고",
      statusText: "AI 윤문 엔진이 원고 전체를 분석 및 교열/윤색하고 있습니다. 분량에 따라 최대 수십 초가 소요됩니다..."
    });
    
    try {
      const res = await fetch('/api/inference/refine/novel', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project_name: activeProject,
          user_prompt: tabPrompts.novel_manuscript,
          full_novel: fullNovelText
        })
      });
      
      const result = await res.json();
      if (res.ok && result.refined_novel) {
        setFullNovelText(result.refined_novel);
        showNotification("원고 교열/윤문이 완료되었습니다!", "success");
      } else {
        showNotification(result.detail || "교열 중 오류가 발생했습니다.", "error");
      }
    } catch (err) {
      console.error("원고 교열 통신 에러:", err);
      showNotification("네트워크 오류 발생", "error");
    } finally {
      setIsRefiningNovel(false);
      setProcessingProgress({ active: false, total: 0, current: 0, currentCut: null, statusText: "" });
    }
  };

  return (
    <div className="min-h-screen bg-[#070b13] text-slate-100 flex flex-col pb-12">
      {/* 상단 통합 헤더 */}
      <header className="border-b border-slate-800/80 bg-slate-950/40 backdrop-blur-md sticky top-0 z-50 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 bg-indigo-600 rounded-lg flex items-center justify-center font-bold text-white shadow-lg shadow-indigo-600/40">
            DS
          </div>
          <div>
            <h1 className="text-lg font-bold tracking-tight bg-gradient-to-r from-slate-100 to-slate-400 bg-clip-text text-transparent">DeepScribe Dashboard</h1>
            <p className="text-[10px] text-slate-400 font-mono">Uncensored Manga to Korean Novel Generator</p>
          </div>
        </div>

        {/* 알림 배너 */}
        {alertInfo.text && (
          <div className={`px-4 py-2 rounded-lg text-xs font-semibold flex items-center gap-2 animate-fade-in shadow-md ${
            alertInfo.type === 'success' ? 'bg-emerald-950/80 border border-emerald-800 text-emerald-300' :
            alertInfo.type === 'error' ? 'bg-rose-950/80 border border-rose-800 text-rose-300' :
            'bg-indigo-950/80 border border-indigo-800 text-indigo-300'
          }`}>
            {alertInfo.type === 'success' && <CheckCircle className="w-4 h-4" />}
            {alertInfo.type === 'error' && <AlertCircle className="w-4 h-4" />}
            {alertInfo.type === 'info' && <RefreshCw className="w-4 h-4 animate-spin" />}
            <span>{alertInfo.text}</span>
          </div>
        )}

        <div className="flex items-center gap-3">
          {/* 작업 세션(프로젝트) 전환 및 신규 생성 컨트롤러 */}
          <div className="flex items-center gap-1.5 bg-slate-900/80 px-2.5 py-1.5 rounded-lg border border-slate-800">
            <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">작업 선택</span>
            <select
              value={activeProject}
              onChange={(e) => {
                setActiveProject(e.target.value);
                // 세션 변경 시 UI 초기화 격리 보장
                setActiveFileType('overall_plot');
                setActiveCutNum(1);
              }}
              className="bg-slate-950 border border-slate-700 text-indigo-300 text-xs font-bold py-1 px-2.5 rounded focus:outline-none transition cursor-pointer"
            >
              {projects.map(p => (
                <option key={p} value={p}>{p}</option>
              ))}
            </select>
          </div>

          <button
            onClick={handleCreateProject}
            className="flex items-center gap-1 px-3 py-1.5 text-xs font-semibold text-slate-300 bg-slate-800/80 hover:bg-slate-800 rounded-lg border border-slate-700/60 transition"
          >
            <span>➕ 새 작업 시작</span>
          </button>

          <button
            onClick={handleDeleteProject}
            className="flex items-center gap-1 px-3 py-1.5 text-xs font-semibold text-rose-400 bg-rose-950/40 hover:bg-rose-950/80 border border-rose-900/60 hover:border-rose-800 rounded-lg transition"
          >
            <Trash2 className="w-3.5 h-3.5" />
            <span>작업 삭제</span>
          </button>

          <button
            onClick={handleManualSave}
            disabled={isSaving}
            className="flex items-center gap-1.5 px-4 py-2 text-xs font-bold text-slate-900 bg-emerald-400 hover:bg-emerald-300 disabled:opacity-50 rounded-lg shadow-lg shadow-emerald-500/10 transition"
          >
            {isSaving ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
            <span>작업 임시저장 (Save)</span>
          </button>
        </div>
      </header>

      <main className="max-w-[1600px] w-full mx-auto px-6 mt-8 flex flex-col gap-6 flex-1">
        {/* 실시간 AI 파이프라인 변환 진행 상태 패널 */}
        {processingProgress.active && (
          <div className="bg-slate-900/80 border border-indigo-500/40 rounded-xl p-5 shadow-2xl flex flex-col gap-3 relative overflow-hidden animate-pulse">
            {/* 배경 그라데이션 장식 */}
            <div className="absolute top-0 right-0 w-32 h-32 bg-indigo-500/10 rounded-full blur-2xl pointer-events-none" />
            
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <RefreshCw className="w-5 h-5 text-indigo-400 animate-spin" />
                <div>
                  <h3 className="text-sm font-bold text-slate-100 flex items-center gap-2">
                    <span>⚡ AI 파이프라인 변환 진행 중</span>
                    <span className="text-[10px] bg-indigo-950 text-indigo-400 border border-indigo-900 px-2 py-0.5 rounded font-mono font-semibold">
                      {processingProgress.current + 1} / {processingProgress.total} CUT / 단계
                    </span>
                  </h3>
                  <p className="text-[11px] text-slate-400 mt-0.5">{processingProgress.statusText}</p>
                </div>
              </div>
              
              <div className="flex items-center gap-3">
                <span className="text-xs font-bold text-indigo-400 font-mono">
                  {Math.round(((processingProgress.current) / processingProgress.total) * 100)}%
                </span>
                <button
                  onClick={handleCancelProcessing}
                  className="px-2.5 py-1 text-[10px] font-bold text-rose-400 bg-rose-950/40 hover:bg-rose-900 hover:text-white border border-rose-900/60 rounded-md transition shadow shadow-rose-950/20"
                >
                  작업 취소
                </button>
              </div>
            </div>

            {/* 프로그레스 바 슬라이더 */}
            <div className="w-full h-2.5 bg-slate-950 rounded-full overflow-hidden border border-slate-800">
              <div 
                className="h-full bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500 transition-all duration-500 ease-out shadow-[0_0_8px_rgba(99,102,241,0.5)]"
                style={{ width: `${((processingProgress.current) / processingProgress.total) * 100}%` }}
              />
            </div>
            
            {/* 세부 정보 안내 */}
            <div className="flex justify-between items-center text-[10px] text-slate-500 font-mono">
              <span>대상 프로젝트: {activeProject}</span>
              <span>현재 분석 중인 대상: {processingProgress.currentCut ? `[ ${processingProgress.currentCut} ]` : '초안 설정/원고'}</span>
            </div>
          </div>
        )}

        {/* 1. 에셋 매니저 그리드 레이아웃 */}
        <AssetManager 
          projectName={activeProject}
          onProcessCuts={handleProcessCuts} 
          onSelectCut={(cutNum) => {
            setActiveCutNum(cutNum);
            setActiveFileType('image_plot');
            showNotification(`Cut #${cutNum}의 상세 분석 데이터가 로드되었습니다.`, "success");
            
            // 상단 썸네일 클릭 시 맨 하단 생성 소설 완성본 위치로 자동 스크롤 및 텍스트 포커싱
            if (novelTextareaRef.current) {
              novelTextareaRef.current.scrollIntoView({ behavior: 'smooth', block: 'center' });
              
              setTimeout(() => {
                const textarea = novelTextareaRef.current;
                if (!textarea) return;
                const text = textarea.value;
                const regex = new RegExp(`\\[Cut\\s*#\\s*${cutNum}\\]`, 'i');
                const match = text.match(regex);
                if (match) {
                  const startIndex = match.index;
                  const endIndex = startIndex + match[0].length;
                  
                  // 정확한 라인 높이 계산을 통한 내부 스크롤 (text-sm leading-relaxed 기준 라인당 약 23px)
                  const linesBefore = text.substring(0, startIndex).split('\n').length - 1;
                  const lineHeight = 23;
                  
                  textarea.focus();
                  textarea.setSelectionRange(startIndex, endIndex);
                  textarea.scrollTop = linesBefore * lineHeight;
                }
              }, 400); // smooth 스크롤 완료되는 타이밍에 텍스트 선택/포커싱 수행
            }
          }}
        />

        {/* 2. 대시보드 코어 작업 공간 그리드 */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-stretch">
          
          {/* 좌측 세부 설정 및 에디터 (8컬럼) */}
          <div className="lg:col-span-8 flex flex-col gap-6">
            
            {/* 설정 데이터 전환 탭바 */}
            <div className="bg-slate-900/50 p-1.5 rounded-xl border border-slate-800/80 flex items-center justify-between flex-wrap gap-2">
              <div className="flex items-center gap-1">
                <button
                  onClick={() => setActiveFileType('overall_plot')}
                  className={`flex items-center gap-1.5 px-4 py-2 text-xs font-bold rounded-lg transition ${
                    activeFileType === 'overall_plot' ? 'bg-indigo-600 text-white shadow-md' : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  <BookOpen className="w-3.5 h-3.5" />
                  <span>전체 줄거리 (overall_plot)</span>
                </button>

                <button
                  onClick={() => setActiveFileType('image_plot')}
                  className={`flex items-center gap-1.5 px-4 py-2 text-xs font-bold rounded-lg transition ${
                    activeFileType === 'image_plot' ? 'bg-indigo-600 text-white shadow-md' : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  <Film className="w-3.5 h-3.5" />
                  <span>컷별 묘사 (image_plot)</span>
                </button>

                <button
                  onClick={() => setActiveFileType('theme_background')}
                  className={`flex items-center gap-1.5 px-4 py-2 text-xs font-bold rounded-lg transition ${
                    activeFileType === 'theme_background' ? 'bg-indigo-600 text-white shadow-md' : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  <Landmark className="w-3.5 h-3.5" />
                  <span>세계관 배경 (theme_background)</span>
                </button>

                <button
                  onClick={() => setActiveFileType('character_profiles')}
                  className={`flex items-center gap-1.5 px-4 py-2 text-xs font-bold rounded-lg transition ${
                    activeFileType === 'character_profiles' ? 'bg-indigo-600 text-white shadow-md' : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  <Users className="w-3.5 h-3.5" />
                  <span>등장인물 관계 (character_profiles)</span>
                </button>
              </div>

              {/* 컷별 묘사가 선택되었을 때만 컷 번호 스피너 노출 */}
              {activeFileType === 'image_plot' && (
                <div className="flex items-center gap-2 bg-slate-950/80 px-3 py-1 rounded-lg border border-slate-800">
                  <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">대상 컷 번호</span>
                  <input
                    type="number"
                    min="1"
                    max="100"
                    value={activeCutNum}
                    onChange={(e) => setActiveCutNum(Math.max(1, parseInt(e.target.value) || 1))}
                    className="w-12 bg-slate-900 border border-slate-700 text-center rounded text-xs font-bold text-indigo-300 p-0.5 focus:outline-none"
                  />
                </div>
              )}
            </div>

            {/* 에디터 컴포넌트 마운트 */}
            <div className="flex-1">
              <IntelligentEditor 
                initialJson={currentData} 
                fileType={activeFileType}
                onStateChange={handleEditorDataChange} 
                onAiAnalyze={handleAiDraftAnalysis}
                onSave={handleManualSave}
                isSaving={isSaving}
                promptValue={tabPrompts[activeFileType]}
                onPromptChange={(val) => setTabPrompts(prev => ({ ...prev, [activeFileType]: val }))}
                projects={projects}
                activeProject={activeProject}
                onImportFromProject={handleImportFromProject}
              />
            </div>
          </div>

          {/* 우측 버전 제어 히스토리 및 프롬프트 인풋 영역 (4컬럼) */}
          <div className="lg:col-span-4 flex flex-col gap-6">
            <PromptController 
              userPrompt={tabPrompts[activeFileType] || ""} 
              onUserPromptChange={(val) => setTabPrompts(prev => ({ ...prev, [activeFileType]: val }))} 
              activeFileType={activeFileType}
            />
            
            <div className="flex-1">
              <HistoryPanel 
                history={revisionHistory} 
                onRollback={handleRollback} 
                currentRevision={currentRevisionNum} 
              />
            </div>
          </div>

        </div>

        {/* 3.전체 완성 소설 원고 영역 (Compiled Novel draft) */}
        <div className="glass-card rounded-xl p-6 shadow-2xl border border-slate-800/80 bg-slate-900/10 mt-4 flex flex-col gap-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-4">
            <div>
              <h2 className="text-lg font-bold text-slate-100 flex items-center gap-2">
                <span>📖 생성 소설 완성본</span>
                <span className="text-[10px] tracking-wider px-2 py-0.5 bg-indigo-950 text-indigo-400 border border-indigo-900 rounded font-semibold">MANUSCRIPT</span>
              </h2>
              <p className="text-slate-400 text-xs mt-1">각 컷에서 변환된 소설 단락(novel_paragraph)들을 컷 번호 순서대로 실시간 자동 정합하여 하나의 소설 원고로 보여줍니다.</p>
            </div>
          </div>

          {/* 새로 디자인된 프리미엄 컨트롤 툴바 영역 */}
          <div className="flex flex-wrap items-center justify-between gap-3 bg-slate-950/40 p-3 rounded-lg border border-slate-800/60">
            {/* 왼쪽 그룹: 버전 복원 & 새로고침 */}
            <div className="flex items-center gap-2 flex-wrap">
              {masterNovelHistory.length > 0 && (
                <div className="flex items-center gap-1.5 bg-slate-900 px-2.5 py-1.5 rounded-lg border border-slate-800 text-xs text-slate-400">
                  <span className="text-[10px] font-bold text-slate-500 uppercase font-mono">버전 복원</span>
                  <select
                    value={currentMasterNovelRevision || ""}
                    onChange={(e) => handleRollbackMasterNovel(parseInt(e.target.value))}
                    className="bg-slate-950 border border-slate-700 text-indigo-300 font-bold rounded px-2 py-0.5 focus:outline-none text-[11px] font-mono cursor-pointer"
                  >
                    {masterNovelHistory.map((rev) => (
                      <option key={rev.id} value={rev.revision}>
                        v{rev.revision} ({rev.author === 'ai' ? 'AI' : 'User'}) - {new Date(rev.created_at && !rev.created_at.endsWith('Z') ? `${rev.created_at}Z` : rev.created_at).toLocaleTimeString()}
                      </option>
                    ))}
                  </select>
                </div>
              )}

              <button
                onClick={fetchFullNovel}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-slate-300 bg-slate-800/60 hover:bg-slate-800 rounded-lg border border-slate-700/80 transition h-[34px]"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                <span>원고 새로고침</span>
              </button>
            </div>

            {/* 오른쪽 그룹: 편집 옵션 및 저장/추출 액션 */}
            <div className="flex items-center gap-2 flex-wrap">
              <label className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-slate-300 bg-slate-800/40 hover:bg-slate-800 rounded-lg border border-slate-700/80 cursor-pointer transition select-none h-[34px]">
                <input
                  type="checkbox"
                  checked={excludeCutHeaders}
                  onChange={(e) => setExcludeCutHeaders(e.target.checked)}
                  className="rounded border-slate-700 bg-slate-950 text-indigo-500 focus:ring-indigo-500/30 w-3.5 h-3.5"
                />
                <span>Cut 번호 제외</span>
              </label>

              <button
                onClick={handleCopyNovelToClipboard}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-slate-300 bg-slate-800/60 hover:bg-slate-800 rounded-lg border border-slate-700/80 transition h-[34px]"
              >
                <Copy className="w-3.5 h-3.5 text-indigo-400" />
                <span>클립보드에 복사</span>
              </button>

              <div className="h-6 w-[1px] bg-slate-800 hidden sm:block"></div>

              <button
                onClick={handleDownloadNovelTxt}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-slate-900 bg-indigo-400 hover:bg-indigo-300 rounded-lg shadow-lg shadow-indigo-500/10 transition h-[34px]"
              >
                <Download className="w-3.5 h-3.5" />
                <span>원고 TXT 다운로드</span>
              </button>

              <button
                onClick={handleSaveMasterNovel}
                disabled={isSaving}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-slate-900 bg-emerald-400 hover:bg-emerald-300 disabled:opacity-50 rounded-lg shadow-lg shadow-emerald-500/10 transition h-[34px]"
              >
                {isSaving ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
                <span>원고 저장 (Save)</span>
              </button>
            </div>
          </div>

          {/* 전체 원고 교열/윤문 AI 프롬프트 지시 영역 */}
          <div className="bg-slate-950/60 p-4 rounded-xl border border-indigo-950/60 flex flex-col gap-2.5 shadow-inner">
            <div className="flex items-center justify-between">
              <label className="text-xs font-bold text-indigo-400 tracking-wider flex items-center gap-1.5">
                <Wand2 className="w-3.5 h-3.5 animate-pulse text-emerald-400" />
                <span>원고 전체 윤문/교열 AI 프롬프트 (Manuscript Polishing Prompt)</span>
              </label>
              <span className="text-[10px] text-slate-500 font-mono">지정된 프롬프트를 기준으로 완성본 전체의 톤앤매너 및 문맥을 매끄럽게 교정합니다.</span>
            </div>
            <div className="flex gap-3 items-end">
              <textarea
                value={tabPrompts.novel_manuscript}
                onChange={(e) => setTabPrompts(prev => ({ ...prev, novel_manuscript: e.target.value }))}
                placeholder="예: 조금 더 감정선이 깊고 관능적인 어조로 어미를 매끄럽게 고쳐주고, 문단 간 문맥 연결을 자연스럽게 보완해줘..."
                className="flex-1 bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-slate-300 text-xs focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/30 resize-none min-h-[50px] scrollbar-thin transition"
              />
              <button
                onClick={handleRefineNovel}
                disabled={isRefiningNovel}
                className="flex items-center gap-1.5 px-4 py-3 text-xs font-bold text-slate-900 bg-emerald-400 hover:bg-emerald-300 disabled:opacity-50 rounded-lg shadow-lg shadow-emerald-500/10 transition h-[50px] whitespace-nowrap"
              >
                {isRefiningNovel ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Wand2 className="w-4 h-4" />}
                <span>AI 원고 다듬기</span>
              </button>
            </div>
          </div>

          <textarea
            ref={novelTextareaRef}
            value={fullNovelText}
            onChange={(e) => setFullNovelText(e.target.value)}
            className="w-full bg-slate-950/80 rounded-lg p-5 border border-slate-800 font-serif leading-relaxed text-slate-200 text-sm min-h-[400px] max-h-[700px] overflow-y-auto selection:bg-indigo-500/30 focus:outline-none focus:border-indigo-500/40 focus:ring-1 focus:ring-indigo-500/20 resize-y transition"
            placeholder="이곳에서 완성된 전체 소설 원고를 자유롭게 수정하고 우측 상단의 '원고 저장 (Save)' 버튼을 눌러 버전 리비전 히스토리로 기록하세요..."
          />
        </div>

      </main>
    </div>
  );
}
