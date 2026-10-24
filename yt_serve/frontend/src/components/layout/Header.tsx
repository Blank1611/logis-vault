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
  onOpenSettingsTab?: (tab: 'storage' | 'profiles' | 'audio' | 'auth' | 'scheduler' | 'git' | 'network') => void
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
    <header className="sticky top-0 z-40 bg-slate-950/80 backdrop-blur-xl border-b border-white/10 shadow-xl transition-all">
      <div className="w-full max-w-[min(94vw,1920px)] mx-auto px-4 sm:px-6 lg:px-8 py-3.5 flex items-center justify-between gap-4">
        {/* Left: Glowing Brand Logo & Title */}
        <div className="flex items-center gap-3.5 shrink-0">
          <div className="relative group cursor-pointer" onClick={() => onTabChange('playlists')}>
            {/* Ambient Logo Glow */}
            <div className="absolute -inset-1 bg-gradient-to-r from-cyan-500 to-blue-600 rounded-2xl blur-md opacity-70 group-hover:opacity-100 transition-all duration-300"></div>
            <div className="relative w-10 h-10 rounded-xl bg-gradient-to-br from-cyan-400 via-blue-500 to-indigo-600 flex items-center justify-center shadow-lg border border-white/25">
              <svg className="w-5 h-5 text-white fill-current ml-0.5 drop-shadow" viewBox="0 0 24 24">
                <path d="M8 5v14l11-7z" />
              </svg>
            </div>
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-lg sm:text-xl font-extrabold tracking-tight bg-gradient-to-r from-white via-slate-100 to-cyan-300 bg-clip-text text-transparent">
                Playlist Manager
              </h1>
              <span className="hidden md:inline-block px-2 py-0.5 text-[10px] font-bold tracking-wider uppercase rounded-full bg-cyan-500/15 text-cyan-300 border border-cyan-500/30">
                PRO
              </span>
            </div>
            <p className="text-[11px] font-medium tracking-wider text-slate-400 hidden sm:block">
              MEDIA ENGINE &bull; ARCHIVE &bull; EXTRACT
            </p>
          </div>
        </div>

        {/* Center: Primary Navigation Tabs Capsule */}
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
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold backdrop-blur-md border transition-all ${
              cookiesStatus?.status === 'valid'
                ? 'glass-pill-emerald'
                : cookiesStatus?.status === 'expiring_soon'
                ? 'bg-amber-500/15 text-amber-300 border-amber-500/40 hover:bg-amber-500/25'
                : cookiesStatus?.status === 'expired' || cookiesStatus?.status === 'invalid'
                ? 'glass-pill-rose'
                : 'bg-slate-800/60 text-slate-400 border-white/10 hover:bg-slate-800 hover:text-slate-200'
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
            className="p-2 rounded-xl bg-slate-900/70 hover:bg-slate-800/90 border border-white/10 hover:border-cyan-500/40 text-slate-300 hover:text-cyan-300 transition-all shadow-sm backdrop-blur-md"
            title="Settings"
          >
            <Settings className="w-4 h-4" />
          </button>

          {/* Dark Mode Toggle */}
          <button
            onClick={toggleDarkMode}
            className="p-2 rounded-xl bg-slate-900/70 hover:bg-slate-800/90 border border-white/10 hover:border-yellow-500/40 transition-all shadow-sm backdrop-blur-md"
            title={darkMode ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
          >
            {darkMode ? (
              <Sun className="w-4 h-4 text-yellow-400" />
            ) : (
              <Moon className="w-4 h-4 text-slate-300" />
            )}
          </button>
        </div>
      </div>
    </header>
  )
}
