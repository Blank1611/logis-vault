import React from 'react'
import { PlayCircle, FileText, Sparkles } from 'lucide-react'

export type TabType = 'playlists' | 'quick-download' | 'logs'

export interface NavigationTabsProps {
  activeTab: TabType
  onTabChange: (tab: TabType) => void
  runningJobsCount?: number
}

export const NavigationTabs: React.FC<NavigationTabsProps> = ({
  activeTab,
  onTabChange,
  runningJobsCount = 0,
}) => {
  return (
    <div className="glass-nav-capsule flex items-center gap-1.5 p-1.5 rounded-full shadow-2xl">
      <button
        onClick={() => onTabChange('playlists')}
        className={`px-4 sm:px-5 py-2 rounded-full text-xs sm:text-sm font-semibold transition-all flex items-center gap-2 ${
          activeTab === 'playlists'
            ? 'glass-nav-pill-active'
            : 'glass-nav-pill-inactive'
        }`}
      >
        <PlayCircle className={`w-4 h-4 ${activeTab === 'playlists' ? 'text-cyan-300' : 'text-slate-400'}`} />
        <span>Playlists</span>
      </button>

      <button
        onClick={() => onTabChange('quick-download')}
        className={`px-4 sm:px-5 py-2 rounded-full text-xs sm:text-sm font-semibold transition-all flex items-center gap-2 ${
          activeTab === 'quick-download'
            ? 'glass-nav-pill-active'
            : 'glass-nav-pill-inactive'
        }`}
      >
        <Sparkles className={`w-4 h-4 ${activeTab === 'quick-download' ? 'text-cyan-300' : 'text-indigo-400'}`} />
        <span>Quick Download</span>
      </button>

      <button
        onClick={() => onTabChange('logs')}
        className={`px-4 sm:px-5 py-2 rounded-full text-xs sm:text-sm font-semibold transition-all flex items-center gap-2 ${
          activeTab === 'logs'
            ? 'glass-nav-pill-active'
            : 'glass-nav-pill-inactive'
        }`}
      >
        <FileText className={`w-4 h-4 ${activeTab === 'logs' ? 'text-cyan-300' : 'text-slate-400'}`} />
        <span>Job Logs</span>
        {runningJobsCount > 0 && (
          <span className="px-2 py-0.5 rounded-full text-[11px] font-bold bg-cyan-400 text-slate-950 shadow-md shadow-cyan-500/50 animate-pulse">
            {runningJobsCount}
          </span>
        )}
      </button>
    </div>
  )
}
