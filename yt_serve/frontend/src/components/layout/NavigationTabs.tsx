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
    <div className="flex items-center gap-1 bg-gray-200 dark:bg-gray-700/70 p-1 rounded-xl">
      <button
        onClick={() => onTabChange('playlists')}
        className={`px-4 py-1.5 rounded-lg text-sm font-semibold transition-all flex items-center gap-2 ${
          activeTab === 'playlists'
            ? 'bg-white dark:bg-gray-800 text-blue-600 dark:text-blue-400 shadow-sm'
            : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'
        }`}
      >
        <PlayCircle className="w-4 h-4" />
        Playlists
      </button>

      <button
        onClick={() => onTabChange('quick-download')}
        className={`px-4 py-1.5 rounded-lg text-sm font-semibold transition-all flex items-center gap-2 ${
          activeTab === 'quick-download'
            ? 'bg-white dark:bg-gray-800 text-indigo-600 dark:text-indigo-400 shadow-sm'
            : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'
        }`}
      >
        <Sparkles className="w-4 h-4 text-indigo-500" />
        Quick Download
      </button>

      <button
        onClick={() => onTabChange('logs')}
        className={`px-4 py-1.5 rounded-lg text-sm font-semibold transition-all flex items-center gap-2 ${
          activeTab === 'logs'
            ? 'bg-white dark:bg-gray-800 text-blue-600 dark:text-blue-400 shadow-sm'
            : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'
        }`}
      >
        <FileText className="w-4 h-4" />
        Job Logs
        {runningJobsCount > 0 && (
          <span className="px-1.5 py-0.2 rounded-full text-xs font-bold bg-blue-600 text-white animate-pulse">
            {runningJobsCount}
          </span>
        )}
      </button>
    </div>
  )
}
