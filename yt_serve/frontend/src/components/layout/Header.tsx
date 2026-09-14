import React from 'react'
import { useQuery } from '@tanstack/react-query'
import { Settings, Moon, Sun, Grid3x3, List, Layers, Sparkles, Key } from 'lucide-react'
import { NavigationTabs, type TabType } from './NavigationTabs'
import { useTheme } from '../../context/ThemeContext'
import { configApi } from '../../services/api'

export interface HeaderProps {
  activeTab: TabType
  onTabChange: (tab: TabType) => void
  runningJobsCount?: number
  viewMode?: 'grid' | 'list'
  onViewModeChange?: (mode: 'grid' | 'list') => void
  onOpenSettings: () => void
  onOpenSettingsTab?: (tab: 'storage' | 'audio' | 'auth' | 'scheduler' | 'git' | 'network') => void
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
  onOpenSettingsTab,
  onOpenReorganize,
  onOpenDeduplicate,
}) => {
  const { darkMode, toggleDarkMode } = useTheme()

  const { data: cookiesStatus } = useQuery({
    queryKey: ['cookiesStatus'],
    queryFn: async () => {
      const res = await configApi.getCookiesStatus()
      return res.data
    },
    staleTime: 30000,
  })

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

          {/* Cookie Health Pill */}
          <button
            onClick={() => {
              if (onOpenSettingsTab) {
                onOpenSettingsTab('auth')
              } else {
                onOpenSettings()
              }
            }}
            className={`hidden md:flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border transition-colors ${
              cookiesStatus?.status === 'valid'
                ? 'bg-emerald-50 text-emerald-700 border-emerald-300 dark:bg-emerald-950/50 dark:text-emerald-400 dark:border-emerald-800 hover:bg-emerald-100 dark:hover:bg-emerald-900/50'
                : cookiesStatus?.status === 'expiring_soon'
                ? 'bg-amber-50 text-amber-700 border-amber-300 dark:bg-amber-950/50 dark:text-amber-400 dark:border-amber-800 hover:bg-amber-100 dark:hover:bg-amber-900/50'
                : cookiesStatus?.status === 'expired' || cookiesStatus?.status === 'invalid'
                ? 'bg-rose-50 text-rose-700 border-rose-300 dark:bg-rose-950/50 dark:text-rose-400 dark:border-rose-800 hover:bg-rose-100 dark:hover:bg-rose-900/50'
                : 'bg-gray-100 text-gray-600 border-gray-200 dark:bg-gray-700/60 dark:text-gray-400 dark:border-gray-600 hover:bg-gray-200 dark:hover:bg-gray-700'
            }`}
            title={`Cookies Status: ${cookiesStatus?.status_message || 'Click to configure'}`}
          >
            <Key className="w-3.5 h-3.5" />
            <span>
              {cookiesStatus?.status === 'valid'
                ? `Cookies: Active${cookiesStatus.days_remaining != null ? ` (${cookiesStatus.days_remaining}d)` : ''}`
                : cookiesStatus?.status === 'expiring_soon'
                ? `Cookies: Expiring (${cookiesStatus.days_remaining ?? 0}d)`
                : cookiesStatus?.status === 'expired'
                ? 'Cookies: Expired'
                : cookiesStatus?.status === 'invalid'
                ? 'Cookies: Invalid'
                : 'No Cookies'}
            </span>
          </button>

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
