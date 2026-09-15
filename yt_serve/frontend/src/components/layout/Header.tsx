import React from 'react'
import { useQuery } from '@tanstack/react-query'
import { Settings, Moon, Sun, Key } from 'lucide-react'
import { NavigationTabs, type TabType } from './NavigationTabs'
import { useTheme } from '../../context/ThemeContext'
import { configApi } from '../../services/api'

export interface HeaderProps {
  activeTab: TabType
  onTabChange: (tab: TabType) => void
  runningJobsCount?: number
  onOpenSettings: () => void
  onOpenSettingsTab?: (tab: 'storage' | 'audio' | 'auth' | 'scheduler' | 'git' | 'network') => void
}

export const Header: React.FC<HeaderProps> = ({
  activeTab,
  onTabChange,
  runningJobsCount = 0,
  onOpenSettings,
  onOpenSettingsTab,
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
    <header className="bg-white dark:bg-gray-800 shadow border-b border-gray-200/80 dark:border-gray-700/80">
      <div className="w-full max-w-[min(94vw,1920px)] mx-auto px-4 sm:px-6 lg:px-8 py-4 flex items-center justify-between gap-4">
        {/* Left: Brand Logo & Title */}
        <div className="flex items-center gap-3 shrink-0">
          <h1 className="text-xl sm:text-2xl font-extrabold text-gray-900 dark:text-white tracking-tight">
            Playlist Manager
          </h1>
        </div>

        {/* Center: Primary Navigation Tabs */}
        <div className="flex-1 flex justify-center">
          <NavigationTabs
            activeTab={activeTab}
            onTabChange={onTabChange}
            runningJobsCount={runningJobsCount}
          />
        </div>

        {/* Right: Global Utilities */}
        <div className="flex items-center gap-2 sm:gap-2.5 shrink-0">
          {/* Cookie Health Pill */}
          <button
            onClick={() => {
              if (onOpenSettingsTab) {
                onOpenSettingsTab('auth')
              } else {
                onOpenSettings()
              }
            }}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium border transition-all ${
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
            <span className="hidden sm:inline">
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
            className="p-2 rounded-lg bg-gray-100 hover:bg-gray-200 dark:bg-gray-700 dark:hover:bg-gray-600 border border-gray-200 dark:border-gray-600 text-gray-700 dark:text-gray-300 transition-colors shadow-xs"
            title="Settings"
          >
            <Settings className="w-4 h-4" />
          </button>

          {/* Dark Mode Toggle */}
          <button
            onClick={toggleDarkMode}
            className="p-2 rounded-lg bg-gray-100 hover:bg-gray-200 dark:bg-gray-700 dark:hover:bg-gray-600 border border-gray-200 dark:border-gray-600 transition-colors shadow-xs"
            title={darkMode ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
          >
            {darkMode ? (
              <Sun className="w-4 h-4 text-yellow-400" />
            ) : (
              <Moon className="w-4 h-4 text-gray-700 dark:text-gray-300" />
            )}
          </button>
        </div>
      </div>
    </header>
  )
}
