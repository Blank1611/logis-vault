import React, { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { configApi, type Config } from '../services/api'
import { useToast } from '../context/ToastContext'
import { useConfirm } from '../context/ConfirmContext'
import { FieldHeader, AudioModeCard } from '../components/ui/FormField'
import { IntervalPicker } from '../components/ui/IntervalPicker'
import { TimePicker } from '../components/ui/TimePicker'
import { UnmanagedFoldersManager } from '../components/settings/UnmanagedFoldersManager'
import { Button } from '../components/ui/Button'
import {
  HardDrive, Music, Key, Clock, GitBranch, Settings2, ArrowLeft,
  Save, RotateCcw, Loader2, CheckCircle2, AlertCircle, Shield,
  Upload, Trash2, Cpu, RefreshCw, ChevronDown, ChevronUp, Check, X, Globe
} from 'lucide-react'

export type SettingsTab = 'storage' | 'audio' | 'auth' | 'scheduler' | 'git' | 'network'

export interface SettingsPageProps {
  onBack: () => void
  onOpenDeduplicate?: () => void
  initialTab?: SettingsTab
}

export function SettingsPage({ onBack, onOpenDeduplicate, initialTab = 'storage' }: SettingsPageProps) {
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const confirm = useConfirm()

  const [activeTab, setActiveTab] = useState<SettingsTab>(initialTab || 'storage')
  const [formData, setFormData] = useState<Partial<Config>>({})
  const [isDirty, setIsDirty] = useState(false)
  const [gitTestStatus, setGitTestStatus] = useState<'idle' | 'testing' | 'success' | 'failed'>('idle')
  const [gitTestMessage, setGitTestMessage] = useState<string>('')
  const [showGitAdvanced, setShowGitAdvanced] = useState(false)

  useEffect(() => {
    if (initialTab) {
      setActiveTab(initialTab)
    }
  }, [initialTab])

  // Status queries
  const { data: config, isLoading } = useQuery({
    queryKey: ['config'],
    queryFn: async () => {
      const res = await configApi.get()
      return res.data
    },
  })

  useEffect(() => {
    if (config) {
      setFormData(config)
    }
  }, [config])

  const { data: cookiesStatus, refetch: refetchCookies } = useQuery({
    queryKey: ['cookiesStatus'],
    queryFn: async () => {
      const res = await configApi.getCookiesStatus()
      return res.data
    }
  })

  const { data: ytdlpVersion, refetch: refetchYtdlp } = useQuery({
    queryKey: ['ytdlpVersion'],
    queryFn: async () => {
      const res = await configApi.getYtdlpVersion()
      return res.data
    }
  })

  // Mutations
  const updateConfig = useMutation({
    mutationFn: (newConfig: Partial<Config>) => configApi.update(newConfig),
    onSuccess: (res) => {
      queryClient.setQueryData(['config'], res.data)
      setFormData(res.data)
      setIsDirty(false)
      toast.success('Settings saved and applied successfully!')
    },
    onError: (err: any) => {
      toast.error(`Failed to save settings: ${err.response?.data?.detail || err.message}`)
    }
  })

  const updateYtdlpMutation = useMutation({
    mutationFn: () => configApi.updateYtdlp(),
    onSuccess: (res) => {
      if (res.data.success) {
        toast.success(res.data.message)
        refetchYtdlp()
      } else {
        toast.error(`Update failed: ${res.data.message}`)
      }
    },
    onError: (err: any) => {
      toast.error(`yt-dlp update failed: ${err.message}`)
    }
  })

  const testFlareSolverrMutation = useMutation({
    mutationFn: (url?: string) => configApi.testFlareSolverr(url),
    onSuccess: (res) => {
      if (res.data.success) {
        toast.success(res.data.message)
      } else {
        toast.error(res.data.message)
      }
    },
    onError: (err: any) => {
      toast.error(`FlareSolverr test failed: ${err.message}`)
    }
  })

  const testGitSyncMutation = useMutation({
    mutationFn: () => {
      setGitTestStatus('testing')
      return configApi.testGitSync({
        git_remote_url: formData.git_remote_url?.trim() || undefined,
        git_auth_token: formData.git_auth_token?.trim() || undefined,
        git_branch: formData.git_branch?.trim() || undefined,
      })
    },
    onSuccess: (res) => {
      if (res.data.success) {
        setGitTestStatus('success')
        setGitTestMessage(res.data.message || 'Remote Git connection verified successfully.')
        toast.success(res.data.message || 'Remote Git connection verified successfully.')
      } else {
        setGitTestStatus('failed')
        setGitTestMessage(res.data.message || 'Remote Git test failed.')
        toast.error(res.data.message || 'Remote Git test failed.')
      }
    },
    onError: (err: any) => {
      setGitTestStatus('failed')
      const msg = err.response?.data?.detail || err.message || 'Connection failed.'
      setGitTestMessage(msg)
      toast.error(`Git sync test failed: ${msg}`)
    }
  })

  const uploadCookiesMutation = useMutation({
    mutationFn: (file: File) => configApi.uploadCookies(file),
    onSuccess: () => {
      toast.success('cookies.txt uploaded and verified!')
      refetchCookies()
      queryClient.invalidateQueries({ queryKey: ['config'] })
    },
    onError: (err: any) => {
      toast.error(`Cookie upload failed: ${err.response?.data?.detail || err.message}`)
    }
  })

  const deleteCookiesMutation = useMutation({
    mutationFn: () => configApi.deleteCookies(),
    onSuccess: () => {
      toast.success('cookies.txt removed.')
      refetchCookies()
      queryClient.invalidateQueries({ queryKey: ['config'] })
    },
    onError: (err: any) => {
      toast.error(`Failed to delete cookies: ${err.message}`)
    }
  })

  // Handle field change and track dirty state
  const handleFieldChange = <K extends keyof Config>(key: K, value: Config[K]) => {
    setFormData(prev => ({ ...prev, [key]: value }))
    setIsDirty(true)
    if (key === 'git_remote_url' || key === 'git_auth_token') {
      setGitTestStatus('idle')
      setGitTestMessage('')
    }
  }

  const handleReset = () => {
    if (config) {
      setFormData(config)
      setIsDirty(false)
      setGitTestStatus('idle')
      setGitTestMessage('')
      toast.info('Settings reverted to active configuration.')
    }
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()

    const validated: Partial<Config> = {
      base_download_path: formData.base_download_path?.trim(),
      temp_download_path: formData.temp_download_path?.trim() || null,
      audio_extract_mode: formData.audio_extract_mode || 'copy',
      max_extraction_workers: Number(formData.max_extraction_workers) || 4,
      max_concurrent_downloads: Number(formData.max_concurrent_downloads) || 1,
      batch_size: Number(formData.batch_size) || 200,
      sleep_interval_min: Number(formData.sleep_interval_min) ?? 1,
      sleep_interval_max: Number(formData.sleep_interval_max) ?? 5,
      concurrent_fragments: Number(formData.concurrent_fragments) || 2,
      enable_daily_auto_refresh: Boolean(formData.enable_daily_auto_refresh),
      daily_refresh_mode: formData.daily_refresh_mode || 'scheduled',
      daily_refresh_time: formData.daily_refresh_time?.trim() || '04:00',
      daily_refresh_timezone: formData.daily_refresh_timezone?.trim() || 'Asia/Kolkata',
      daily_refresh_interval_minutes: Number(formData.daily_refresh_interval_minutes) || 1440,
      enable_git_metadata_sync: Boolean(formData.enable_git_metadata_sync),
      enable_git_remote_push: Boolean(formData.enable_git_remote_push),
      git_remote_url: formData.git_remote_url != null ? formData.git_remote_url.trim() : '',
      git_auth_token: formData.git_auth_token != null ? formData.git_auth_token.trim() : '',
      git_branch: formData.git_branch?.trim() || 'main',
      git_user_name: formData.git_user_name?.trim() || 'YouTube Playlist Manager',
      git_user_email: formData.git_user_email?.trim() || 'yt-manager@homelab.local',
      cookies_auth_mode: formData.cookies_auth_mode || 'cookies_txt',
      cookies_file: formData.cookies_file?.trim() || null,
      use_browser_cookies: formData.cookies_auth_mode === 'browser' || Boolean(formData.use_browser_cookies),
      browser_name: formData.browser_name || 'chrome',
      enable_stream_integrity_check: Boolean(formData.enable_stream_integrity_check),
      flaresolverr_url: formData.flaresolverr_url != null ? formData.flaresolverr_url.trim() : '',
      enable_auto_discovery: Boolean(formData.enable_auto_discovery),
      auto_discovery_interval_minutes: Number(formData.auto_discovery_interval_minutes) ?? 1440,
      // Fixed Ad-Hoc Paths Persistence
      adhoc_download_path: formData.adhoc_download_path?.trim() || null,
      use_custom_adhoc_path: Boolean(formData.use_custom_adhoc_path),
      // Auto-Discovery Exclusions & Rename
      excluded_dirs: formData.excluded_dirs?.trim() || '',
      rename_folder_on_link: Boolean(formData.rename_folder_on_link),
    }

    updateConfig.mutate(validated)
  }

  const tabs: Array<{ id: SettingsTab; label: string; icon: React.ElementType }> = [
    { id: 'storage', label: 'Storage & Folders', icon: HardDrive },
    { id: 'audio', label: 'Audio Extraction', icon: Music },
    { id: 'auth', label: 'Cookies & Auth', icon: Key },
    { id: 'scheduler', label: 'Scheduler & Discovery', icon: Clock },
    { id: 'git', label: 'Git Metadata Sync', icon: GitBranch },
    { id: 'network', label: 'Network & Engine', icon: Settings2 },
  ]

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-950 text-white flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="w-10 h-10 animate-spin text-blue-500" />
          <p className="text-sm text-gray-400">Loading system settings...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 flex flex-col pb-24">
      {/* Top Header Bar */}
      <header className="sticky top-0 z-40 bg-gray-900/90 backdrop-blur-md border-b border-gray-800 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={onBack}
            className="flex items-center gap-2 bg-gray-800 hover:bg-gray-700 text-gray-200 border border-gray-700"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>Back to Playlists</span>
          </Button>

          <div>
            <h1 className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
              <Settings2 className="w-5 h-5 text-blue-500" />
              <span>System Settings</span>
            </h1>
            <p className="text-xs text-gray-400">
              Configure directories, audio extraction, sync, cookies, and automation
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {isDirty && (
            <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-amber-950/60 text-amber-400 border border-amber-800/80 animate-pulse">
              Unsaved Changes
            </span>
          )}
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={handleReset}
            disabled={!isDirty || updateConfig.isPending}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-colors ${isDirty
                ? 'bg-gray-100 hover:bg-gray-200 dark:bg-gray-800 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-200'
                : 'opacity-40 cursor-not-allowed bg-gray-100 dark:bg-gray-800 text-gray-400'
              }`}
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span>Reset</span>
          </Button>
          <Button
            type="button"
            variant="primary"
            size="sm"
            onClick={handleSubmit}
            disabled={updateConfig.isPending}
            className="px-4 py-1.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-lg text-xs font-semibold flex items-center gap-1.5 shadow-sm transition-colors"
          >
            {updateConfig.isPending ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Save className="w-3.5 h-3.5" />
            )}
            <span>Save Settings</span>
          </Button>
        </div>
      </header>

      {/* Main Layout: Sidebar Tabs + Content Pane */}
      <div className="max-w-7xl w-full mx-auto px-4 sm:px-6 py-6 grid grid-cols-1 md:grid-cols-4 gap-6">
        {/* Navigation Sidebar */}
        <nav className="md:col-span-1 space-y-1">
          {tabs.map((tab) => {
            const Icon = tab.icon
            const isActive = activeTab === tab.id
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id)}
                className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-semibold transition-all ${isActive
                    ? 'bg-blue-600 text-white shadow-lg shadow-blue-600/25'
                    : 'text-gray-400 hover:text-white hover:bg-gray-900 border border-transparent'
                  }`}
              >
                <Icon className={`w-4 h-4 ${isActive ? 'text-white' : 'text-gray-400'}`} />
                <span>{tab.label}</span>
              </button>
            )
          })}

          {onOpenDeduplicate && (
            <div className="pt-4 border-t border-gray-800">
              <button
                type="button"
                onClick={onOpenDeduplicate}
                className="w-full flex items-center gap-3 px-4 py-2.5 rounded-xl text-xs font-semibold text-indigo-400 hover:text-indigo-300 hover:bg-indigo-950/30 border border-indigo-900/40 transition-colors"
              >
                <HardDrive className="w-4 h-4 text-indigo-400" />
                <span>Deduplicate Space</span>
              </button>
            </div>
          )}
        </nav>

        {/* Content Pane */}
        <div className="md:col-span-3 space-y-6">
          {/* TAB 1: Storage & Folders */}
          {activeTab === 'storage' && (
            <div className="space-y-6 animate-in fade-in duration-200">
              <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6 shadow-xl space-y-6">
                <h3 className="text-lg font-bold text-white flex items-center gap-2 border-b border-gray-800 pb-3">
                  <HardDrive className="w-5 h-5 text-blue-400" />
                  <span>Storage Directories</span>
                </h3>

                {/* Base Download Path */}
                <div>
                  <FieldHeader
                    label="Base Download Path"
                    required={true}
                    infoText="Absolute filesystem path where all YouTube playlists are downloaded and organized."
                    id="base_download_path"
                  />
                  <input
                    id="base_download_path"
                    type="text"
                    value={formData.base_download_path || ''}
                    onChange={(e) => handleFieldChange('base_download_path', e.target.value)}
                    className="w-full px-4 py-2.5 bg-gray-950 border border-gray-700 rounded-xl text-white font-mono text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    placeholder="/downloads"
                  />
                </div>

                {/* Temp Download Path */}
                <div>
                  <FieldHeader
                    label="Temporary Download Path (Optional)"
                    infoText="Fast scratch directory (such as an SSD, NVMe, or tmpfs ramdisk) for downloading in-progress chunks before moving to long-term storage."
                    id="temp_download_path"
                  />
                  <input
                    id="temp_download_path"
                    type="text"
                    value={formData.temp_download_path || ''}
                    onChange={(e) => handleFieldChange('temp_download_path', e.target.value)}
                    className="w-full px-4 py-2.5 bg-gray-950 border border-gray-700 rounded-xl text-white font-mono text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    placeholder="Leave empty to use in-place download"
                  />
                </div>

                {/* Ad-Hoc Downloads Folder Configuration */}
                <div className="p-4 bg-gray-950/60 border border-gray-800 rounded-xl space-y-4">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <h4 className="text-sm font-semibold text-white">Custom Ad-hoc Downloads Directory</h4>
                      <p className="text-xs text-gray-400 mt-0.5">
                        Standalone tracks downloaded via the Quick Download bar are kept separate from playlists.
                      </p>
                    </div>
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input
                        type="checkbox"
                        checked={Boolean(formData.use_custom_adhoc_path)}
                        onChange={(e) => handleFieldChange('use_custom_adhoc_path', e.target.checked)}
                        className="sr-only peer"
                      />
                      <div className="w-11 h-6 bg-gray-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                    </label>
                  </div>

                  {formData.use_custom_adhoc_path ? (
                    <div>
                      <FieldHeader
                        label="Ad-hoc Downloads Path"
                        infoText="Custom absolute directory for single songs."
                        id="adhoc_download_path"
                      />
                      <input
                        id="adhoc_download_path"
                        type="text"
                        value={formData.adhoc_download_path || ''}
                        onChange={(e) => handleFieldChange('adhoc_download_path', e.target.value)}
                        className="w-full px-4 py-2.5 bg-gray-950 border border-gray-700 rounded-xl text-white font-mono text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                        placeholder="/downloads/_adhoc_downloads"
                      />
                    </div>
                  ) : (
                    <div className="text-xs text-gray-400 bg-gray-900/60 p-3 rounded-lg border border-gray-800/80">
                      Default location:{' '}
                      <span className="font-mono text-gray-300 font-semibold">
                        {formData.effective_adhoc_download_path || `${formData.base_download_path || '/downloads'}/_adhoc_downloads`}
                      </span>
                    </div>
                  )}
                </div>

                {/* Excluded Directories */}
                <div>
                  <FieldHeader
                    label="Excluded Directories (Comma-separated)"
                    infoText="Folder names inside your base download directory that auto-discovery will strictly ignore."
                    id="excluded_dirs"
                  />
                  <input
                    id="excluded_dirs"
                    type="text"
                    value={formData.excluded_dirs || ''}
                    onChange={(e) => handleFieldChange('excluded_dirs', e.target.value)}
                    className="w-full px-4 py-2.5 bg-gray-950 border border-gray-700 rounded-xl text-white font-mono text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    placeholder="temp, logs, scratch, node_modules, _adhoc_downloads"
                  />
                </div>

                {/* Folder Rename Policy on Link */}
                <div className="flex items-center justify-between pt-1">
                  <div>
                    <FieldHeader
                      label="Rename Disk Folder on Link"
                      infoText="Default policy when linking an unmanaged disk folder to a YouTube playlist: automatically rename the folder on disk to match the YouTube playlist title. If disabled, your custom existing disk folder name is preserved."
                      id="rename_folder_on_link"
                    />
                    <p className="text-xs text-gray-400 mt-0.5">
                      Automatically rename disk directories to match playlist titles when linked in the Unmanaged Folders manager.
                    </p>
                  </div>
                  <label className="relative inline-flex items-center cursor-pointer shrink-0 ml-4">
                    <input
                      type="checkbox"
                      id="rename_folder_on_link"
                      checked={Boolean(formData.rename_folder_on_link)}
                      onChange={(e) => handleFieldChange('rename_folder_on_link', e.target.checked)}
                      className="sr-only peer"
                    />
                    <div className="w-11 h-6 bg-gray-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                  </label>
                </div>
              </div>

              {/* Sonarr-Style Unmanaged Folders Manager */}
              <UnmanagedFoldersManager />
            </div>
          )}

          {/* TAB 2: Audio Extraction */}
          {activeTab === 'audio' && (
            <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6 shadow-xl space-y-6 animate-in fade-in duration-200">
              <h3 className="text-lg font-bold text-white flex items-center gap-2 border-b border-gray-800 pb-3">
                <Music className="w-5 h-5 text-purple-400" />
                <span>Audio Extraction Settings</span>
              </h3>

              {/* Extraction Mode */}
              <div>
                <FieldHeader
                  label="Audio Extraction Format"
                  recommended="Recommended: Direct Stream Copy"
                  infoText="Direct Stream Copy extracts YouTube's native audio (.m4a AAC or .opus) instantaneously without transcoding or quality loss."
                  id="audio_extract_mode"
                />
                <select
                  id="audio_extract_mode"
                  value={formData.audio_extract_mode || 'copy'}
                  onChange={(e) => handleFieldChange('audio_extract_mode', e.target.value)}
                  className="w-full px-4 py-2.5 bg-gray-950 border border-gray-700 rounded-xl text-white text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                >
                  <option value="copy">Direct Stream Copy (Fastest, Lossless original)</option>
                  <option value="mp3_best">MP3 Best Quality (VBR ~250–320 kbps)</option>
                  <option value="mp3_high">MP3 High Quality (VBR ~190–250 kbps)</option>
                  <option value="opus">Opus Audio (~160 kbps)</option>
                </select>

                <AudioModeCard mode={formData.audio_extract_mode || 'copy'} />
              </div>

              {/* Worker Threads */}
              <div>
                <FieldHeader
                  label="Extraction Worker Threads"
                  recommended="Recommended: 4 Threads"
                  infoText="Number of parallel ffmpeg worker threads for transcoding audio when not using direct stream copy."
                  id="max_extraction_workers"
                />
                <input
                  id="max_extraction_workers"
                  type="number"
                  min={1}
                  max={16}
                  value={formData.max_extraction_workers ?? 4}
                  onChange={(e) => handleFieldChange('max_extraction_workers', parseInt(e.target.value, 10))}
                  className="w-full px-4 py-2.5 bg-gray-950 border border-gray-700 rounded-xl text-white font-mono text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                />
              </div>

              {/* Stream Integrity Verification (ffprobe) */}
              <div className="flex items-center justify-between p-4 bg-gray-950/60 border border-gray-800 rounded-xl">
                <div>
                  <h4 className="text-sm font-semibold text-white flex items-center gap-1.5">
                    <Shield className="w-4 h-4 text-emerald-400" />
                    <span>Stream Integrity Verification (ffprobe)</span>
                  </h4>
                  <p className="text-xs text-gray-400 mt-0.5">
                    Post-Extraction Validation Layer: Runs ffprobe inspection on newly extracted audio files (.m4a, .mp3, .opus) to confirm valid container headers and playback duration.
                  </p>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    id="enable_stream_integrity_check"
                    checked={Boolean(formData.enable_stream_integrity_check)}
                    onChange={(e) => handleFieldChange('enable_stream_integrity_check', e.target.checked)}
                    className="sr-only peer"
                  />
                  <div className="w-11 h-6 bg-gray-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                </label>
              </div>
            </div>
          )}

          {/* TAB 3: Cookies & Auth */}
          {activeTab === 'auth' && (
            <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6 shadow-xl space-y-6 animate-in fade-in duration-200">
              <h3 className="text-lg font-bold text-white flex items-center gap-2 border-b border-gray-800 pb-3">
                <Key className="w-5 h-5 text-amber-400" />
                <span>Cookies & Authentication</span>
              </h3>

              {/* Authentication Mode Selector */}
              <div className="space-y-2">
                <FieldHeader
                  label="Authentication Mode"
                  infoText="Choose how yt-dlp authenticates with YouTube. Netscape cookies.txt is recommended for containerized environments. Browser profile extraction extracts directly from local SQLite databases. Public-only skips authentication."
                />
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 p-1 bg-gray-950/80 border border-gray-800 rounded-xl">
                  <button
                    type="button"
                    onClick={() => {
                      handleFieldChange('cookies_auth_mode', 'cookies_txt')
                      handleFieldChange('use_browser_cookies', false)
                    }}
                    className={`flex items-center justify-center gap-2 py-2.5 px-3 rounded-lg text-xs font-semibold transition-all ${
                      (formData.cookies_auth_mode || (formData.use_browser_cookies ? 'browser' : 'cookies_txt')) === 'cookies_txt'
                        ? 'bg-blue-600 text-white shadow-md'
                        : 'text-gray-400 hover:text-white hover:bg-gray-900'
                    }`}
                  >
                    <Upload className="w-3.5 h-3.5" />
                    <span>cookies.txt File (Recommended)</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      handleFieldChange('cookies_auth_mode', 'browser')
                      handleFieldChange('use_browser_cookies', true)
                    }}
                    className={`flex items-center justify-center gap-2 py-2.5 px-3 rounded-lg text-xs font-semibold transition-all ${
                      (formData.cookies_auth_mode || (formData.use_browser_cookies ? 'browser' : 'cookies_txt')) === 'browser'
                        ? 'bg-blue-600 text-white shadow-md'
                        : 'text-gray-400 hover:text-white hover:bg-gray-900'
                    }`}
                  >
                    <Globe className="w-3.5 h-3.5" />
                    <span>Browser Profile Extraction</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      handleFieldChange('cookies_auth_mode', 'none')
                      handleFieldChange('use_browser_cookies', false)
                    }}
                    className={`flex items-center justify-center gap-2 py-2.5 px-3 rounded-lg text-xs font-semibold transition-all ${
                      (formData.cookies_auth_mode || (formData.use_browser_cookies ? 'browser' : 'cookies_txt')) === 'none'
                        ? 'bg-blue-600 text-white shadow-md'
                        : 'text-gray-400 hover:text-white hover:bg-gray-900'
                    }`}
                  >
                    <Shield className="w-3.5 h-3.5" />
                    <span>No Cookies (Public Only)</span>
                  </button>
                </div>
              </div>

              {/* Mode 1: cookies.txt */}
              {(formData.cookies_auth_mode || (formData.use_browser_cookies ? 'browser' : 'cookies_txt')) === 'cookies_txt' && (
                <div className="space-y-4 animate-in fade-in duration-150">
                  {/* Live Cookie Status Banner */}
                  <div className={`p-4 rounded-xl border flex items-start gap-3 ${cookiesStatus?.is_installed && cookiesStatus?.status === 'valid'
                      ? 'bg-emerald-950/40 border-emerald-800/60 text-emerald-300'
                      : 'bg-amber-950/40 border-amber-800/60 text-amber-300'
                    }`}>
                    {cookiesStatus?.is_installed && cookiesStatus?.status === 'valid' ? (
                      <CheckCircle2 className="w-5 h-5 shrink-0 mt-0.5 text-emerald-400" />
                    ) : (
                      <AlertCircle className="w-5 h-5 shrink-0 mt-0.5 text-amber-400" />
                    )}
                    <div className="flex-1 text-xs">
                      <div className="font-semibold text-sm">
                        {cookiesStatus?.status_message || 'Cookie status not checked'}
                      </div>
                      {cookiesStatus?.file_path && (
                        <div className="mt-1 font-mono text-gray-400">
                          File: {cookiesStatus.file_path}
                        </div>
                      )}
                      {cookiesStatus?.days_remaining !== undefined && cookiesStatus?.days_remaining !== null && (
                        <div className="mt-0.5">
                          Days remaining before expiration: {cookiesStatus.days_remaining}
                        </div>
                      )}
                    </div>

                    {cookiesStatus?.is_installed && (
                      <Button
                        type="button"
                        variant="danger"
                        size="sm"
                        onClick={async () => {
                          const ok = await confirm({
                            title: 'Delete Cookies File',
                            message: 'Are you sure you want to remove the installed cookies.txt file?',
                            confirmText: 'Delete',
                            isDestructive: true,
                          })
                          if (ok) deleteCookiesMutation.mutate()
                        }}
                        className="text-xs bg-rose-600 hover:bg-rose-500 text-white"
                      >
                        <Trash2 className="w-3.5 h-3.5 mr-1" />
                        <span>Remove</span>
                      </Button>
                    )}
                  </div>

                  {/* Upload cookies.txt */}
                  <div className="p-4 bg-gray-950/60 border border-gray-800 rounded-xl space-y-3">
                    <div className="flex items-center justify-between">
                      <h4 className="text-sm font-semibold text-white flex items-center gap-2">
                        <Upload className="w-4 h-4 text-blue-400" />
                        <span>Upload Netscape cookies.txt</span>
                      </h4>
                    </div>
                    <p className="text-xs text-gray-400 leading-relaxed">
                      Export cookies from your browser using extensions like "Get cookies.txt LOCALLY" while logged into YouTube.
                    </p>
                    <input
                      type="file"
                      accept=".txt"
                      onChange={(e) => {
                        const file = e.target.files?.[0]
                        if (file) uploadCookiesMutation.mutate(file)
                      }}
                      className="block w-full text-xs text-gray-400 file:mr-4 file:py-2 file:px-4 file:rounded-xl file:border-0 file:text-xs file:font-semibold file:bg-blue-600 file:text-white hover:file:bg-blue-500 file:cursor-pointer cursor-pointer"
                    />
                  </div>
                </div>
              )}

              {/* Mode 2: Browser Profile Extraction */}
              {(formData.cookies_auth_mode || (formData.use_browser_cookies ? 'browser' : 'cookies_txt')) === 'browser' && (
                <div className="p-4 bg-gray-950/60 border border-gray-800 rounded-xl space-y-3 animate-in fade-in duration-150">
                  <div>
                    <h4 className="text-sm font-semibold text-white flex items-center gap-2">
                      <Globe className="w-4 h-4 text-cyan-400" />
                      <span>Browser Profile Extraction (Local / Headless)</span>
                    </h4>
                    <p className="text-xs text-gray-400 mt-0.5">
                      Extract YouTube session cookies directly from a local browser database on the fly.
                    </p>
                  </div>

                  <div className="pt-2 border-t border-gray-800/80 space-y-3">
                    <div>
                      <FieldHeader
                        label="Browser Engine Profile"
                        infoText="Browser to decrypt and extract cookies from. yt-dlp will read from the browser's default profile path."
                        id="browser_name"
                      />
                      <select
                        id="browser_name"
                        value={formData.browser_name || 'chrome'}
                        onChange={(e) => handleFieldChange('browser_name', e.target.value)}
                        className="w-full px-4 py-2.5 bg-gray-950 border border-gray-700 rounded-xl text-white text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 font-mono"
                      >
                        <option value="chrome">Google Chrome / Chromium</option>
                        <option value="firefox">Mozilla Firefox</option>
                        <option value="edge">Microsoft Edge</option>
                        <option value="safari">Apple Safari</option>
                      </select>
                    </div>
                    <div className="p-3 bg-amber-950/30 border border-amber-800/50 rounded-lg text-xs text-amber-300 space-y-1">
                      <div className="font-semibold flex items-center gap-1.5">
                        <AlertCircle className="w-4 h-4 text-amber-400" />
                        <span>Docker Container Notice</span>
                      </div>
                      <p className="text-amber-300/80 leading-relaxed">
                        When running in Docker, you must mount your host browser profile directory into the container (e.g. <code>~/.config/google-chrome:/root/.config/google-chrome:ro</code>) so yt-dlp can access the cookie SQLite database.
                      </p>
                    </div>
                  </div>
                </div>
              )}

              {/* Mode 3: No Cookies (Public Only) */}
              {(formData.cookies_auth_mode || (formData.use_browser_cookies ? 'browser' : 'cookies_txt')) === 'none' && (
                <div className="p-4 bg-gray-950/60 border border-gray-800 rounded-xl space-y-2 animate-in fade-in duration-150">
                  <div className="flex items-center gap-2 text-sm font-semibold text-gray-300">
                    <Shield className="w-4 h-4 text-gray-400" />
                    <span>Public Only Mode Active</span>
                  </div>
                  <p className="text-xs text-gray-400 leading-relaxed">
                    yt-dlp will make requests without session cookies or authentication headers. Public playlists and videos will download normally, but age-restricted videos, private playlists, or YouTube Premium high-bitrate streams will be unavailable.
                  </p>
                </div>
              )}

              {/* FlareSolverr */}
              <div className="space-y-3">
                <FieldHeader
                  label="FlareSolverr Proxy URL (Optional)"
                  infoText="FlareSolverr proxy service URL to bypass Cloudflare and bot checks on restricted streams."
                  id="flaresolverr_url"
                />
                <div className="flex gap-2">
                  <input
                    id="flaresolverr_url"
                    type="text"
                    value={formData.flaresolverr_url || ''}
                    onChange={(e) => handleFieldChange('flaresolverr_url', e.target.value)}
                    className="flex-1 px-4 py-2.5 bg-gray-950 border border-gray-700 rounded-xl text-white font-mono text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    placeholder="http://localhost:8191"
                  />
                  <Button
                    type="button"
                    variant="secondary"
                    onClick={() => testFlareSolverrMutation.mutate(formData.flaresolverr_url || undefined)}
                    disabled={testFlareSolverrMutation.isPending}
                    className="px-3 py-2 bg-gray-100 hover:bg-gray-200 dark:bg-gray-800 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-200 rounded-lg text-xs font-medium flex items-center gap-1.5 transition-colors disabled:opacity-50 shrink-0"
                  >
                    {testFlareSolverrMutation.isPending ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <span>Test URL</span>
                    )}
                  </Button>
                </div>
              </div>
            </div>
          )}

          {/* TAB 4: Scheduler & Discovery */}
          {activeTab === 'scheduler' && (
            <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6 shadow-xl space-y-6 animate-in fade-in duration-200">
              <h3 className="text-lg font-bold text-white flex items-center gap-2 border-b border-gray-800 pb-3">
                <Clock className="w-5 h-5 text-emerald-400" />
                <span>Scheduler & Automation</span>
              </h3>

              {/* 1. TOP SECTION: Automated YouTube Metadata Refresh */}
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h4 className="text-sm font-semibold text-white">Automated YouTube Metadata Refresh</h4>
                    <p className="text-xs text-gray-400 mt-0.5">
                      Check YouTube for new video additions across all saved playlists automatically in the background.
                    </p>
                  </div>
                  <label className="relative inline-flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      checked={Boolean(formData.enable_daily_auto_refresh)}
                      onChange={(e) => handleFieldChange('enable_daily_auto_refresh', e.target.checked)}
                      className="sr-only peer"
                    />
                    <div className="w-11 h-6 bg-gray-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                  </label>
                </div>

                {formData.enable_daily_auto_refresh && (
                  <div className="bg-gray-950/60 border border-gray-800 rounded-xl p-4 space-y-4 animate-in fade-in duration-150">
                    {/* Mode Selector */}
                    <div>
                      <FieldHeader
                        label="Refresh Mode"
                        infoText="Choose whether metadata sync runs at a specific daily clock time or repeats periodically on an interval cadence."
                      />
                      <div className="inline-flex rounded-xl bg-gray-950 p-1 border border-gray-700">
                        <button
                          type="button"
                          onClick={() => handleFieldChange('daily_refresh_mode', 'scheduled')}
                          className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                            (formData.daily_refresh_mode || 'scheduled') === 'scheduled'
                              ? 'bg-blue-600 text-white shadow-md'
                              : 'text-gray-400 hover:text-white'
                          }`}
                        >
                          Scheduled Time
                        </button>
                        <button
                          type="button"
                          onClick={() => handleFieldChange('daily_refresh_mode', 'interval')}
                          className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                            formData.daily_refresh_mode === 'interval'
                              ? 'bg-blue-600 text-white shadow-md'
                              : 'text-gray-400 hover:text-white'
                          }`}
                        >
                          Periodic Interval
                        </button>
                      </div>
                    </div>

                    {(formData.daily_refresh_mode || 'scheduled') === 'scheduled' ? (
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-1">
                        <div>
                          <FieldHeader
                            label="Scheduled Run Time"
                            id="daily_refresh_time"
                            infoText="Exact clock time when daily YouTube metadata check will run."
                          />
                          <TimePicker
                            id="daily_refresh_time"
                            value={formData.daily_refresh_time || '04:00'}
                            onChange={(t) => handleFieldChange('daily_refresh_time', t)}
                          />
                        </div>
                        <div>
                          <FieldHeader
                            label="Timezone"
                            id="daily_refresh_timezone"
                            infoText="Timezone applied to the scheduled run time."
                          />
                          <select
                            id="daily_refresh_timezone"
                            value={formData.daily_refresh_timezone || 'Asia/Kolkata'}
                            onChange={(e) => handleFieldChange('daily_refresh_timezone', e.target.value)}
                            className="w-full px-3.5 py-2.5 bg-gray-950 border border-gray-700 rounded-xl text-white text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 font-mono"
                          >
                            <option value="Asia/Kolkata">Asia/Kolkata (IST, UTC+5:30) — Default</option>
                            <option value="UTC">UTC (Coordinated Universal Time)</option>
                            <option value="America/New_York">America/New_York (EST/EDT, UTC-5)</option>
                            <option value="America/Chicago">America/Chicago (CST/CDT, UTC-6)</option>
                            <option value="America/Denver">America/Denver (MST/MDT, UTC-7)</option>
                            <option value="America/Los_Angeles">America/Los_Angeles (PST/PDT, UTC-8)</option>
                            <option value="Europe/London">Europe/London (GMT/BST, UTC+0/+1)</option>
                            <option value="Europe/Berlin">Europe/Berlin (CET/CEST, UTC+1/+2)</option>
                            <option value="Europe/Paris">Europe/Paris (CET/CEST, UTC+1/+2)</option>
                            <option value="Asia/Dubai">Asia/Dubai (GST, UTC+4)</option>
                            <option value="Asia/Singapore">Asia/Singapore (SGT, UTC+8)</option>
                            <option value="Asia/Tokyo">Asia/Tokyo (JST, UTC+9)</option>
                            <option value="Australia/Sydney">Australia/Sydney (AEST/AEDT, UTC+10/+11)</option>
                          </select>
                        </div>
                      </div>
                    ) : (
                      <div className="pt-1">
                        <FieldHeader
                          label="Refresh Cadence"
                          infoText="How often to scan YouTube playlists in the background."
                        />
                        <IntervalPicker
                          valueMinutes={formData.daily_refresh_interval_minutes ?? 1440}
                          onChange={(mins) => handleFieldChange('daily_refresh_interval_minutes', mins)}
                          minMinutes={15}
                        />
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* 2. BOTTOM SECTION: Periodic Library Auto-Discovery */}
              <div className="space-y-4 pt-5 border-t border-gray-800">
                <div className="flex items-center justify-between">
                  <div>
                    <h4 className="text-sm font-semibold text-white">Periodic Library Auto-Discovery</h4>
                    <p className="text-xs text-gray-400 mt-0.5">
                      Scans the download directory for newly placed playlist folders. Instant scans can also be triggered anytime in Storage Settings.
                    </p>
                  </div>
                  <label className="relative inline-flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      checked={Boolean(formData.enable_auto_discovery)}
                      onChange={(e) => handleFieldChange('enable_auto_discovery', e.target.checked)}
                      className="sr-only peer"
                    />
                    <div className="w-11 h-6 bg-gray-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                  </label>
                </div>

                {formData.enable_auto_discovery && (
                  <div className="bg-gray-950/60 border border-gray-800 rounded-xl p-4 space-y-2 animate-in fade-in duration-150">
                    <FieldHeader
                      label="Scanning Interval"
                      infoText="Frequency of background scans. Default is Once Daily (24 Hours). Instant scans can always be triggered on-demand in Storage Settings."
                    />
                    <IntervalPicker
                      valueMinutes={formData.auto_discovery_interval_minutes ?? 1440}
                      onChange={(mins) => handleFieldChange('auto_discovery_interval_minutes', mins)}
                      minMinutes={5}
                    />
                  </div>
                )}
              </div>
            </div>
          )}

          {/* TAB 5: Git Metadata Sync */}
          {activeTab === 'git' && (
            <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6 shadow-xl space-y-6 animate-in fade-in duration-200">
              {/* Header with Master Toggle */}
              <div className="flex items-center justify-between border-b border-gray-800 pb-3">
                <div className="flex items-center gap-2">
                  <GitBranch className="w-5 h-5 text-rose-400" />
                  <div>
                    <h3 className="text-lg font-bold text-white">Git Metadata Sync</h3>
                    <p className="text-xs text-gray-400 mt-0.5">
                      Track and version playlist metadata changes over time using Git.
                    </p>
                  </div>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={Boolean(formData.enable_git_metadata_sync)}
                    onChange={(e) => handleFieldChange('enable_git_metadata_sync', e.target.checked)}
                    className="sr-only peer"
                  />
                  <div className="w-11 h-6 bg-gray-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                </label>
              </div>

              {formData.enable_git_metadata_sync ? (
                <div className="space-y-6 animate-in fade-in duration-150">
                  {/* Tier 1: Local Git Versioning Card */}
                  <div className="p-4 bg-gray-950/60 border border-gray-800 rounded-xl space-y-2">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                        <h4 className="text-sm font-semibold text-white">Local Git Versioning (Active)</h4>
                      </div>
                      <span className="text-[11px] px-2 py-0.5 rounded-full font-semibold bg-emerald-950/60 text-emerald-400 border border-emerald-800/80">
                        Offline Ready
                      </span>
                    </div>
                    <p className="text-xs text-gray-400 leading-relaxed">
                      Every playlist folder on disk maintains its own local Git repository. Whenever tracks are added, removed, or reorganized, changes to <code className="text-gray-300 font-mono text-[11px]">playlist_info.json</code> are committed locally with full historical change tracking. No remote repository is required.
                    </p>
                  </div>

                  {/* Tier 2: Remote Repository Push (Optional) */}
                  <div className="p-4 bg-gray-950/60 border border-gray-800 rounded-xl space-y-4">
                    <div className="flex items-center justify-between flex-wrap gap-2">
                      <div>
                        <h4 className="text-sm font-semibold text-white flex items-center gap-2">
                          <Globe className="w-4 h-4 text-rose-400" />
                          <span>Remote Repository Push (Optional)</span>
                        </h4>
                        <p className="text-xs text-gray-400 mt-0.5">
                          Push commits automatically to a remote Git provider (GitHub, GitLab, Gitea) after each local commit.
                        </p>
                      </div>

                      {/* Arr-style Status Pill */}
                      <div className="flex items-center gap-2">
                        {gitTestStatus === 'idle' && (
                          <span className="text-xs px-2.5 py-1 rounded-full font-medium bg-gray-800 text-gray-400 border border-gray-700">
                            Not Tested
                          </span>
                        )}
                        {gitTestStatus === 'testing' && (
                          <span className="text-xs px-2.5 py-1 rounded-full font-medium bg-blue-950/70 text-blue-300 border border-blue-800 flex items-center gap-1.5">
                            <Loader2 className="w-3 h-3 animate-spin text-blue-400" />
                            <span>Testing...</span>
                          </span>
                        )}
                        {gitTestStatus === 'success' && (
                          <span className="text-xs px-2.5 py-1 rounded-full font-medium bg-emerald-950/70 text-emerald-300 border border-emerald-800 flex items-center gap-1.5">
                            <Check className="w-3 h-3 text-emerald-400" />
                            <span>Verified Connected</span>
                          </span>
                        )}
                        {gitTestStatus === 'failed' && (
                          <span className="text-xs px-2.5 py-1 rounded-full font-medium bg-rose-950/70 text-rose-300 border border-rose-800 flex items-center gap-1.5">
                            <X className="w-3 h-3 text-rose-400" />
                            <span>Test Failed</span>
                          </span>
                        )}
                      </div>
                    </div>

                    <div className="space-y-4 pt-2">
                      {/* Independent Remote Push Toggle */}
                      <div className="flex items-center justify-between p-3.5 bg-gray-900/80 border border-gray-800 rounded-xl">
                        <div>
                          <div className="text-xs font-semibold text-white">Enable Remote Repository Push</div>
                          <p className="text-[11px] text-gray-400 mt-0.5">
                            Automatically push commits to the remote repository. When disabled, metadata remains safely versioned locally offline.
                          </p>
                        </div>
                        <label className="relative inline-flex items-center cursor-pointer">
                          <input
                            type="checkbox"
                            checked={Boolean(formData.enable_git_remote_push)}
                            onChange={(e) => handleFieldChange('enable_git_remote_push', e.target.checked)}
                            className="sr-only peer"
                          />
                          <div className="w-11 h-6 bg-gray-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                        </label>
                      </div>

                      <div>
                        <FieldHeader
                          label="Remote Git Repository URL"
                          id="git_remote_url"
                          infoText="HTTPS URL for remote repository where metadata commits should be pushed (e.g., https://github.com/username/yt-metadata.git)."
                        />
                        <input
                          id="git_remote_url"
                          type="text"
                          value={formData.git_remote_url || ''}
                          onChange={(e) => {
                            handleFieldChange('git_remote_url', e.target.value)
                            setGitTestStatus('idle')
                          }}
                          className="w-full px-4 py-2.5 bg-gray-950 border border-gray-700 rounded-xl text-white font-mono text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                          placeholder="https://github.com/username/yt-metadata.git"
                        />
                      </div>

                      <div>
                        <FieldHeader
                          label={formData.enable_git_remote_push ? "Personal Access Token (PAT) *" : "Personal Access Token (PAT)"}
                          id="git_auth_token"
                          infoText={formData.enable_git_remote_push
                            ? "GitHub/GitLab token with repo:write permissions. Required when Remote Repository Push is enabled."
                            : "GitHub/GitLab token with repo:write permissions used to authenticate push operations without entering passwords."}
                        />
                        <input
                          id="git_auth_token"
                          type="password"
                          value={formData.git_auth_token || ''}
                          onChange={(e) => {
                            handleFieldChange('git_auth_token', e.target.value)
                            setGitTestStatus('idle')
                          }}
                          className="w-full px-4 py-2.5 bg-gray-950 border border-gray-700 rounded-xl text-white font-mono text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                          placeholder="ghp_xxxxxxxxxxxxxxxxxxxx"
                        />
                      </div>

                      {/* Test Connection Button */}
                      <div className="flex items-center gap-3 pt-1">
                        <Button
                          type="button"
                          variant="secondary"
                          onClick={() => testGitSyncMutation.mutate()}
                          disabled={testGitSyncMutation.isPending || !formData.git_remote_url}
                          className="px-3 py-2 bg-gray-800 hover:bg-gray-700 text-gray-200 border border-gray-700 rounded-lg text-xs font-medium flex items-center gap-1.5 transition-colors disabled:opacity-50"
                        >
                          {testGitSyncMutation.isPending ? (
                            <Loader2 className="w-3.5 h-3.5 animate-spin mr-1" />
                          ) : (
                            <GitBranch className="w-3.5 h-3.5 mr-1 text-rose-400" />
                          )}
                          <span>Test Connection (Read-Only)</span>
                        </Button>
                        {!formData.git_remote_url && (
                          <span className="text-xs text-gray-500 italic">
                            Enter a remote repository URL to enable connection test
                          </span>
                        )}
                      </div>

                      {gitTestMessage && (
                        <p className={`text-xs ${gitTestStatus === 'success' ? 'text-emerald-400' : 'text-rose-400'}`}>
                          {gitTestMessage}
                        </p>
                      )}
                    </div>

                    {/* Expandable Accordion for Author Identity & Branch */}
                    <div className="border-t border-gray-800/80 pt-3">
                      <button
                        type="button"
                        onClick={() => setShowGitAdvanced(!showGitAdvanced)}
                        className="flex items-center justify-between w-full text-xs font-medium text-gray-400 hover:text-gray-200 py-1"
                      >
                        <span className="flex items-center gap-1.5">
                          <span>Advanced Commit & Author Identity Settings</span>
                          <span className="text-[11px] text-gray-500 font-mono">(Defaults Pre-configured)</span>
                        </span>
                        {showGitAdvanced ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                      </button>

                      {showGitAdvanced && (
                        <div className="mt-3 space-y-4 p-3.5 bg-gray-950/80 border border-gray-800 rounded-xl animate-in fade-in duration-150">
                          <p className="text-xs text-gray-400 leading-relaxed">
                            Git requires author name and email metadata for every commit (both local and remote). Safe homelab defaults are pre-configured below.
                          </p>
                          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                            <div>
                              <FieldHeader
                                label="Target Branch"
                                id="git_branch"
                                infoText="Branch to commit to and push (e.g. main or master)."
                              />
                              <input
                                id="git_branch"
                                type="text"
                                value={formData.git_branch || 'main'}
                                onChange={(e) => handleFieldChange('git_branch', e.target.value)}
                                className="w-full px-4 py-2.5 bg-gray-900 border border-gray-700 rounded-xl text-white font-mono text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                              />
                            </div>
                            <div>
                              <FieldHeader
                                label="Committer Name"
                                id="git_user_name"
                                infoText="Git author name recorded in commit history."
                              />
                              <input
                                id="git_user_name"
                                type="text"
                                value={formData.git_user_name || 'YouTube Playlist Manager'}
                                onChange={(e) => handleFieldChange('git_user_name', e.target.value)}
                                className="w-full px-4 py-2.5 bg-gray-900 border border-gray-700 rounded-xl text-white text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                              />
                            </div>
                            <div>
                              <FieldHeader
                                label="Committer Email"
                                id="git_user_email"
                                infoText="Git author email recorded in commit history."
                              />
                              <input
                                id="git_user_email"
                                type="email"
                                value={formData.git_user_email || 'yt-manager@homelab.local'}
                                onChange={(e) => handleFieldChange('git_user_email', e.target.value)}
                                className="w-full px-4 py-2.5 bg-gray-900 border border-gray-700 rounded-xl text-white text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                              />
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="p-4 bg-gray-950/40 border border-gray-800/60 rounded-xl text-xs text-gray-500 italic">
                  Git metadata synchronization is currently disabled. Toggle the switch above to enable local revision tracking and optional remote pushing.
                </div>
              )}
            </div>
          )}

          {/* TAB 6: Network & Engine */}
          {activeTab === 'network' && (
            <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6 shadow-xl space-y-6 animate-in fade-in duration-200">
              <h3 className="text-lg font-bold text-white flex items-center gap-2 border-b border-gray-800 pb-3">
                <Settings2 className="w-5 h-5 text-cyan-400" />
                <span>Engine & Network Throttling</span>
              </h3>

              {/* YouTube Anti-Ban Educational Callout */}
              <div className="p-4 bg-cyan-950/30 border border-cyan-800/60 rounded-xl text-xs text-cyan-200 space-y-2">
                <div className="font-semibold text-sm flex items-center gap-2 text-cyan-300">
                  <Shield className="w-4 h-4 text-cyan-400" />
                  <span>Understanding Rate Limiting & Anti-Ban Throttling</span>
                </div>
                <p className="text-cyan-200/90 leading-relaxed">
                  YouTube actively monitors download velocity, client fingerprints, and connection patterns. Downloading many videos concurrently or in rapid succession without delays frequently results in temporary IP rate-limits (HTTP 429), CAPTCHA blocks, or flagged sessions.
                </p>
                <p className="text-cyan-200/80 leading-relaxed">
                  Our recommended default of <strong className="text-white">1 concurrent download</strong> and a randomized <strong className="text-white">1s to 5s sleep delay</strong> between tracks mimics genuine human listening behavior to ensure dependable 24/7 background operation.
                </p>
              </div>

              {/* Tier 1: Application Download Queue */}
              <div className="p-4 bg-gray-950/60 border border-gray-800 rounded-xl space-y-4">
                <div>
                  <h4 className="text-sm font-semibold text-white flex items-center gap-2">
                    <Clock className="w-4 h-4 text-blue-400" />
                    <span>Application Download Queue & Throttling</span>
                  </h4>
                  <p className="text-xs text-gray-400 mt-0.5">
                    Controls how the background worker dequeues and spaces out video downloads across playlists.
                  </p>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-1">
                  <div>
                    <FieldHeader
                      label="Max Concurrent Downloads"
                      id="max_concurrent_downloads"
                      recommended="1 (Anti-Ban Safe)"
                      infoText="Controls how many tracks the application downloads concurrently. Keeping this at 1 prevents YouTube IP bans and 429 Too Many Requests errors."
                    />
                    <input
                      id="max_concurrent_downloads"
                      type="number"
                      min={1}
                      max={10}
                      value={formData.max_concurrent_downloads ?? 1}
                      onChange={(e) => handleFieldChange('max_concurrent_downloads', parseInt(e.target.value, 10))}
                      className="w-full px-4 py-2.5 bg-gray-950 border border-gray-700 rounded-xl text-white font-mono text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    />
                  </div>

                  <div>
                    <FieldHeader
                      label="Batch Processing Size"
                      id="batch_size"
                      recommended="200 (Default)"
                      infoText="Number of tracks processed in a single execution cycle before flushing database state and updating progress stats."
                    />
                    <input
                      id="batch_size"
                      type="number"
                      min={1}
                      max={1000}
                      value={formData.batch_size ?? 200}
                      onChange={(e) => handleFieldChange('batch_size', parseInt(e.target.value, 10))}
                      className="w-full px-4 py-2.5 bg-gray-950 border border-gray-700 rounded-xl text-white font-mono text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-1 border-t border-gray-800/80">
                  <div>
                    <FieldHeader
                      label="Inter-Track Sleep Delay Min (Seconds)"
                      id="sleep_interval_min"
                      recommended="1s"
                      infoText="Minimum randomized delay between successive track downloads. Added jitter prevents bot detection."
                    />
                    <input
                      id="sleep_interval_min"
                      type="number"
                      min={0}
                      max={60}
                      value={formData.sleep_interval_min ?? 1}
                      onChange={(e) => handleFieldChange('sleep_interval_min', parseInt(e.target.value, 10))}
                      className="w-full px-4 py-2.5 bg-gray-950 border border-gray-700 rounded-xl text-white font-mono text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    />
                  </div>

                  <div>
                    <FieldHeader
                      label="Inter-Track Sleep Delay Max (Seconds)"
                      id="sleep_interval_max"
                      recommended="5s"
                      infoText="Maximum randomized delay between successive track downloads. Simulates natural listening patterns."
                    />
                    <input
                      id="sleep_interval_max"
                      type="number"
                      min={1}
                      max={120}
                      value={formData.sleep_interval_max ?? 5}
                      onChange={(e) => handleFieldChange('sleep_interval_max', parseInt(e.target.value, 10))}
                      className="w-full px-4 py-2.5 bg-gray-950 border border-gray-700 rounded-xl text-white font-mono text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    />
                  </div>
                </div>
              </div>

              {/* Tier 2: yt-dlp Engine & Network Optimization */}
              <div className="p-4 bg-gray-950/60 border border-gray-800 rounded-xl space-y-4">
                <div>
                  <h4 className="text-sm font-semibold text-white flex items-center gap-2">
                    <Cpu className="w-4 h-4 text-cyan-400" />
                    <span>yt-dlp Core Engine & Media Fragments</span>
                  </h4>
                  <p className="text-xs text-gray-400 mt-0.5">
                    Low-level engine parameters applied to the yt-dlp downloader process.
                  </p>
                </div>

                <div>
                  <FieldHeader
                    label="Concurrent DASH Stream Fragments"
                    id="concurrent_fragments"
                    recommended="2 (Safe)"
                    infoText="Number of audio/video DASH fragments downloaded in parallel by yt-dlp per track. Higher values (e.g. 4-8) increase download speeds on high-speed internet, while lower values (1-2) reduce network throttling."
                  />
                  <input
                    id="concurrent_fragments"
                    type="number"
                    min={1}
                    max={16}
                    value={formData.concurrent_fragments ?? 2}
                    onChange={(e) => handleFieldChange('concurrent_fragments', parseInt(e.target.value, 10))}
                    className="w-full px-4 py-2.5 bg-gray-950 border border-gray-700 rounded-xl text-white font-mono text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  />
                </div>

                {/* Engine Version Card */}
                <div className="p-3.5 bg-gray-900 border border-gray-800 rounded-xl flex items-center justify-between flex-wrap gap-3">
                  <div>
                    <div className="text-xs text-gray-400">Installed yt-dlp Version:</div>
                    <div className="font-mono text-cyan-300 font-bold text-sm">
                      {ytdlpVersion?.version || 'Checking...'}
                    </div>
                  </div>
                  <Button
                    type="button"
                    variant="secondary"
                    size="sm"
                    onClick={() => updateYtdlpMutation.mutate()}
                    disabled={updateYtdlpMutation.isPending}
                    className="px-3 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-colors shrink-0"
                  >
                    {updateYtdlpMutation.isPending ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <RefreshCw className="w-3.5 h-3.5" />
                    )}
                    <span>Update yt-dlp</span>
                  </Button>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
