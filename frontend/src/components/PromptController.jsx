import React from 'react';
import { Sliders, HelpCircle } from 'lucide-react';

export default function PromptController({ userPrompt, onUserPromptChange, activeFileType }) {
  const getTabLabel = (type) => {
    const labels = {
      overall_plot: "전체 줄거리 (overall_plot)",
      image_plot: "컷별 묘사 (image_plot)",
      theme_background: "세계관 배경 (theme_background)",
      character_profiles: "등장인물 관계 (character_profiles)"
    };
    return labels[type] || type;
  };

  return (
    <div className="glass-card rounded-xl p-6 shadow-2xl">
      <div className="flex items-center gap-2 border-b border-slate-800 pb-4 mb-4">
        <Sliders className="w-5 h-5 text-indigo-400" />
        <h2 className="text-xl font-bold text-slate-100">프롬프트 컨트롤러</h2>
      </div>

      <div className="space-y-4">
        <div>
          <div className="flex items-center justify-between mb-1.5">
            <label className="text-xs font-bold text-slate-300 flex items-center gap-1">
              <span>지시문 - {getTabLabel(activeFileType)}</span>
              <span className="text-[10px] text-slate-500 font-normal">(LLM에 병합 주입)</span>
            </label>
            <div className="group relative">
              <HelpCircle className="w-3.5 h-3.5 text-slate-500 hover:text-slate-400 cursor-pointer" />
              <div className="absolute right-0 bottom-full mb-2 hidden group-hover:block w-64 bg-slate-950 text-slate-300 text-[10px] rounded p-2 border border-slate-800 shadow-2xl leading-relaxed z-10">
                선택한 에디터 탭의 AI 추론/분석에 주입할 개별 지시사항을 입력합니다. 
                예: "특정 스타일 반영", "이전 장면과의 연관 묘사 강화" 등.
              </div>
            </div>
          </div>
          
          <textarea
            value={userPrompt}
            onChange={(e) => onUserPromptChange(e.target.value)}
            placeholder="AI에게 요구할 특별한 문체나 지시사항을 입력해 주십시오..."
            className="w-full bg-slate-950 border border-slate-800 rounded-lg p-3 text-slate-200 text-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/30 h-28 resize-none scrollbar-thin"
          />
        </div>
      </div>
    </div>
  );
}
