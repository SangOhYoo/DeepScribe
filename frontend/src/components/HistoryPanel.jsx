import React from 'react';
import { History, RotateCcw, Award, User } from 'lucide-react';

export default function HistoryPanel({ history, onRollback, currentRevision }) {
  const formatDate = (dateStr) => {
    const cleanStr = (dateStr && !dateStr.endsWith('Z')) ? `${dateStr}Z` : dateStr;
    const d = new Date(cleanStr);
    return d.toLocaleString('ko-KR', { 
      year: 'numeric', 
      month: '2-digit', 
      day: '2-digit', 
      hour: '2-digit', 
      minute: '2-digit',
      second: '2-digit',
      hour12: false 
    });
  };

  return (
    <div className="glass-card rounded-xl p-6 shadow-2xl h-full flex flex-col">
      <div className="border-b border-slate-800 pb-4 mb-4">
        <h2 className="text-xl font-bold text-slate-100 flex items-center gap-2">
          <History className="w-5 h-5 text-indigo-400" />
          <span>역사 및 롤백</span>
        </h2>
        <p className="text-slate-400 text-xs mt-1">파일의 변경 리비전을 추적하고 언제든 원하는 시점으로 되돌아갑니다.</p>
      </div>

      <div className="flex-1 overflow-y-auto max-h-[500px] pr-2 scrollbar-thin space-y-3">
        {history.length === 0 ? (
          <div className="h-[250px] flex items-center justify-center text-slate-500 text-sm">
            기록된 저장 리비전이 없습니다. 편집 후 저장하면 리비전 로그가 생성됩니다.
          </div>
        ) : (
          history.map((rev) => {
            const isCurrent = rev.revision === currentRevision;
            const isAI = rev.author === 'ai';
            return (
              <div 
                key={rev.id}
                className={`p-4 rounded-lg border transition duration-200 ${
                  isCurrent 
                    ? 'bg-indigo-950/20 border-indigo-500/50 shadow-md shadow-indigo-950/30' 
                    : 'bg-slate-950/40 border-slate-800 hover:border-slate-700/80'
                }`}
              >
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-1.5">
                    <span className={`flex items-center gap-0.5 px-2 py-0.5 text-[9px] font-bold rounded-full border ${
                      isAI 
                        ? 'bg-cyan-950/80 text-cyan-400 border-cyan-800/40' 
                        : 'bg-emerald-950/80 text-emerald-400 border-emerald-800/40'
                    }`}>
                      {isAI ? (
                        <>
                          <Award className="w-2.5 h-2.5" />
                          <span>AI 생성</span>
                        </>
                      ) : (
                        <>
                          <User className="w-2.5 h-2.5" />
                          <span>작업자</span>
                        </>
                      )}
                    </span>
                    <span className="text-xs font-bold text-slate-200">리비전 #{rev.revision}</span>
                  </div>
                  <span className="text-[10px] text-slate-500 font-mono">{formatDate(rev.created_at)}</span>
                </div>
                
                {rev.change_description && (
                  <p className="text-xs text-slate-300 font-medium mb-3 pl-1 border-l-2 border-slate-700">
                    {rev.change_description}
                  </p>
                )}

                <div className="flex justify-end">
                  {isCurrent ? (
                    <span className="text-[10px] text-indigo-400 font-semibold px-2 py-1 bg-indigo-950/50 rounded border border-indigo-900/50">
                      현재 버전 활성화 중
                    </span>
                  ) : (
                    <button
                      onClick={() => onRollback(rev.revision)}
                      className="flex items-center gap-1 px-2.5 py-1 text-[11px] font-semibold text-slate-300 hover:text-white bg-slate-900 hover:bg-slate-800 border border-slate-800 hover:border-slate-700 rounded transition"
                    >
                      <RotateCcw className="w-3 h-3" />
                      <span>복원하기</span>
                    </button>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
