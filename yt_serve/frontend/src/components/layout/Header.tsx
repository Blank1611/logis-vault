import React from 'react'
import { Settings, Moon, Sun, Grid3x3, List, Layers, Sparkles } from 'lucide-react'
import { NavigationTabs } from './NavigationTabs'
import { useTheme } from '../../context/ThemeContext'

export interface HeaderProps {
  activeTab: 'playlists' | 'logs'
  onTabChange: (tab: 'playlists' | 'logs') => void
  runningJobsCount?: number
  viewMode?: 'grid' | 'list'
  onViewModeChange?: (mode: 'grid' | 'list') => void
  onOpenSettings: () => void
  onOpenReorganize?: () => void
  onOpenDeduplicate?: () => void
}

export const Header: React.FC<HeaderProps> = ({
  activeTab,
  onTabChange,
  runningJobsCount = 0,
  viewMode = 'grid',
  onViewModeChange,
  onOpenSettings,
  onOpenReorganize,
  onOpenDeduplicate,
}) => {
  const { darkMode, toggleDarkMode } = useTheme()

  return (
    <header className="bg-white dark:bg-gray-800 shadow">
      <div className="max-w-7xl mx-auto px-4 py-6 flex justify-between items-center flex-wrap gap-4">
        <div className="flex items-center gap-6 flex-wrap">
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white">Playlist Manager</h1>

          {/* Top Navigation Tabs */}
          <NavigationTabs
            activeTab={activeTab}
            onTabChange={onTabChange}
            runningJobsCount={runningJobsCount}
          />
        </div>

        <div className="flex gap-2 items-center">
          {/* View Mode Toggle (Only show on playlists tab) */}
          {activeTab === 'playlists' && onViewModeChange && (
            <div className="flex gap-1 p-1 rounded-lg bg-gray-200 dark:bg-gray-700">
              <button
                onClick={() => onViewModeChange('grid')}
                className={`p-2 rounded transition-colors ${
                  viewMode === 'grid'
                    ? 'bg-white dark:bg-gray-600 text-blue-600 dark:text-blue-400'
                    : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
                }`}
                title="Grid View"
              >
                <Grid3x3 className="w-5 h-5" />
              </button>
              <button
                onClick={() => onViewModeChange('list')}
                className={`p-2 rounded transition-colors ${
                  viewMode === 'list'
                    ? 'bg-white dark:bg-gray-600 text-blue-600 dark:text-blue-400'
                    : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
                }`}
                title="List View"
              >
                <List className="w-5 h-5" />
              </button>
            </div>
          )}

          {/* Reorganize Track Index Button */}
          {onOpenReorganize && (
            <button
              onClick={onOpenReorganize}
              className="p-2 rounded-lg bg-gray-200 dark:bg-gray-700 hover:bg-gray-300 dark:hover:bg-gray-600 transition-colors flex items-center gap-1.5 text-xs font-semibold text-gray-700 dark:text-gray-300 px-3"
              title="Track Index & Inter-Playlist Reorganization Manager"
            >
              <Layers className="w-4 h-4 text-blue-600 dark:text-blue-400" />
              <span className="hidden sm:inline">Track Index</span>
            </button>
          )}

          {/* Deduplicate Button */}
          {onOpenDeduplicate && (
            <button
              onClick={onOpenDeduplicate}
              className="p-2 rounded-lg bg-gray-200 dark:bg-gray-700 hover:bg-gray-300 dark:hover:bg-gray-600 transition-colors flex items-center gap-1.5 text-xs font-semibold text-gray-700 dark:text-gray-300 px-3"
              title="Retroactive Library Deduplication & Hardlink Space Reclaimer"
            >
              <Sparkles className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
              <span className="hidden sm:inline">Deduplicate</span>
            </button>
          )}

          {/* Settings Button */}
          <button
            onClick={onOpenSettings}
            className="p-2 rounded-lg bg-gray-200 dark:bg-gray-700 hover:bg-gray-300 dark:hover:bg-gray-600 transition-colors"
            title="Settings"
          >
            <Settings className="w-5 h-5 text-gray-700 dark:text-gray-300" />
          </button>

          {/* Dark Mode Toggle */}
          <button
            onClick={toggleDarkMode}
            className="p-2 rounded-lg bg-gray-200 dark:bg-gray-700 hover:bg-gray-300 dark:hover:bg-gray-600 transition-colors"
            title={darkMode ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
          >
            {darkMode ? (
              <Sun className="w-5 h-5 text-yellow-400" />
            ) : (
              <Moon className="w-5 h-5 text-gray-700 dark:text-gray-300" />
            )}
          </button>
        </div>
      </div>
    </header>
  )
}
