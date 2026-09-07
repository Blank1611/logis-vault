import React, { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { configApi, onboardingApi, type Config } from '../../services/api'
import { Modal } from '../ui/Modal'
import { Button } from '../ui/Button'
import { 
  FolderOpen, Loader2, Info, Zap, Music, Sparkles, Search, HardDrive 
} from 'lucide-react'

// Helper Component for interactive field headers with recommendations and toggleable info
export function FieldHeader({
  label,
  required = false,
  recommended,
  infoText,
  id
}: {
  label: string
  required?: boolean
  recommended?: string
  infoText?: string
  id?: string
}) {
  const [open, setOpen] = useState(false)
  return (
    <div className="mb-1.5">
      <div className="flex items-center justify-between gap-2">
        <label htmlFor={id} className="text-sm font-semibold text-gray-900 dark:text-white flex items-center gap-1.5 flex-wrap">
          <span>{label}</span>
          {required && <span className="text-rose-500 font-bold">*</span>}
          {recommended && (
            <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300">
              {recommended}
            </span>
          )}
        </label>
        {infoText && (
          <button
            type="button"
            onClick={() => setOpen(!open)}
            className={`px-2 py-0.5 rounded text-xs transition-colors flex items-center gap-1 shrink-0 ${
              open 
                ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/60 dark:text-blue-200' 
                : 'text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700'
            }`}
            title="Click to toggle explanation"
          >
            <Info className="w-3.5 h-3.5" />
            <span className="text-[11px] font-medium">{open ? 'Hide info' : 'Info'}</span>
          </button>
        )}
      </div>
      {open && infoText && (
        <div className="mt-1.5 p-2.5 bg-blue-50 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-800/80 rounded-lg text-xs text-blue-950 dark:text-blue-200 leading-relaxed shadow-sm">
          {infoText}
        </div>
      )}
    </div>
  )
}

// Helper Component for dynamic Audio Extraction Mode preview card
export function AudioModeCard({ mode }: { mode: string }) {
  if (mode === 'copy') {
    return (
      <div className="mt-2 p-3 bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-800/60 rounded-lg text-xs space-y-1">
        <div className="font-semibold text-emerald-800 dark:text-emerald-300 flex items-center gap-1.5">
          <Zap className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
          Direct Stream Copy (Lossless & Instantaneous)
        </div>
        <p className="text-emerald-700 dark:text-emerald-300/90 leading-relaxed">
          Extracts YouTube's original native audio track (<code className="font-mono bg-emerald-100 dark:bg-emerald-900/60 px-1 py-0.5 rounded">.m4a</code> for AAC, <code className="font-mono bg-emerald-100 dark:bg-emerald-900/60 px-1 py-0.5 rounded">.opus</code> for Opus) without transcoding. Takes ~0.2s per song with zero CPU load and zero acoustic compression loss.
        </p>
      </div>
    )
  }
  if (mode === 'mp3_best') {
    return (
      <div className="mt-2 p-3 bg-indigo-50 dark:bg-indigo-950/30 border border-indigo-200 dark:border-indigo-800/60 rounded-lg text-xs space-y-1">
        <div className="font-semibold text-indigo-800 dark:text-indigo-300 flex items-center gap-1.5">
          <Music className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
          MP3 Best Quality (VBR ~250–320 kbps)
        </div>
        <p className="text-indigo-700 dark:text-indigo-300/90 leading-relaxed">
          Re-encodes audio to universal MP3 at maximum variable bitrate (<code className="font-mono bg-indigo-100 dark:bg-indigo-900/60 px-1 py-0.5 rounded">libmp3lame -q:a 0</code>). 100% compatible with older car stereos and legacy MP3 players.
        </p>
      </div>
    )
  }
  if (mode === 'mp3_high') {
    return (
      <div className="mt-2 p-3 bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800/60 rounded-lg text-xs space-y-1">
        <div className="font-semibold text-blue-800 dark:text-blue-300 flex items-center gap-1.5">
          <Music className="w-4 h-4 text-blue-600 dark:text-blue-400" />
          MP3 High Quality (VBR ~190–250 kbps)
        </div>
        <p className="text-blue-700 dark:text-blue-300/90 leading-relaxed">
          Standard high-quality MP3 encoding (<code className="font-mono bg-blue-100 dark:bg-blue-900/60 px-1 py-0.5 rounded">libmp3lame -q:a 2</code>). Great balance of smaller file sizes and high audio fidelity.
        </p>
      </div>
    )
  }
  if (mode === 'opus') {
    return (
      <div className="mt-2 p-3 bg-purple-50 dark:bg-purple-950/30 border border-purple-200 dark:border-purple-800/60 rounded-lg text-xs space-y-1">
        <div className="font-semibold text-purple-800 dark:text-purple-300 flex items-center gap-1.5">
          <Sparkles className="w-4 h-4 text-purple-600 dark:text-purple-400" />
          Opus Codec (128 kbps)
        </div>
        <p className="text-purple-700 dark:text-purple-300/90 leading-relaxed">
          Uses the next-generation open Opus audio codec. Delivers crystal-clear acoustic transparency at half the file size of traditional MP3s.
        </p>
      </div>
    )
  }
  return null
}

export interface SettingsModalProps {
  onClose: () => void
  onOpenDeduplicate?: () => void
}

export const SettingsModal: React.FC<SettingsModalProps> = ({ onClose, onOpenDeduplicate }) => {
  const queryClient = useQueryClient()
  
  const { data: config, isLoading } = useQuery({
    queryKey: ['config'],
    queryFn: async () => {
      const res = await configApi.get()
      return res.data
    },
  })

  const { data: ytdlpVersionData, refetch: refetchYtdlp } = useQuery({
    queryKey: ['ytdlpVersion'],
    queryFn: async () => {
      const res = await configApi.getYtdlpVersion()
      return res.data
    },
  })

  const updateYtdlpMutation = useMutation({
    mutationFn: () => configApi.updateYtdlp(),
    onSuccess: (res) => {
      if (res.data.success) {
        alert(`yt-dlp updated successfully to version ${res.data.new_version}`)
        refetchYtdlp()
      } else {
        alert(`Failed to update yt-dlp: ${res.data.message}`)
      }
    },
    onError: (err: any) => {
      alert(`Error updating yt-dlp: ${err.message}`)
    },
  })

  const testFlareSolverrMutation = useMutation({
    mutationFn: (url?: string) => configApi.testFlareSolverr(url),
    onSuccess: (res) => {
      if (res.data.success) {
        alert(`✓ ${res.data.message} (${res.data.response_time_ms}ms)`)
      } else {
        alert(`✗ ${res.data.message}`)
      }
    },
    onError: (err: any) => {
      alert(`Error testing FlareSolverr: ${err.message}`)
    },
  })

  const { data: cookieStatus, refetch: refetchCookieStatus } = useQuery({
    queryKey: ['cookies-status'],
    queryFn: async () => {
      const res = await configApi.getCookiesStatus()
      return res.data
    },
  })

  const uploadCookiesMutation = useMutation({
    mutationFn: (file: File) => configApi.uploadCookies(file),
    onSuccess: (res) => {
      refetchCookieStatus()
      queryClient.invalidateQueries({ queryKey: ['config'] })
      alert(`✓ ${res.data.status_message}`)
    },
    onError: (err: any) => {
      alert(`Failed to upload cookies: ${err.message}`)
    },
  })

  const deleteCookiesMutation = useMutation({
    mutationFn: () => configApi.deleteCookies(),
    onSuccess: () => {
      refetchCookieStatus()
      queryClient.invalidateQueries({ queryKey: ['config'] })
      alert('✓ Cookies removed. Downloads will use mobile client emulation.')
    },
    onError: (err: any) => {
      alert(`Failed to remove cookies: ${err.message}`)
    },
  })

  const testGitSyncMutation = useMutation({
    mutationFn: () => configApi.testGitSync(),
    onSuccess: (res) => {
      alert(res.data.success ? `✓ ${res.data.message}` : `✗ ${res.data.message}`)
    },
    onError: (err: any) => {
      alert(`Git test failed: ${err.message}`)
    },
  })

  const [formData, setFormData] = useState<Partial<Config>>({})

  useEffect(() => {
    if (config) {
      setFormData(config)
    }
  }, [config])

  const updateConfig = useMutation({
    mutationFn: (data: Partial<Config>) => configApi.update(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['config'] })
      alert('Settings saved! Restart the backend for changes to take effect.')
      onClose()
    },
    onError: (err: any) => {
      alert(`Failed to save settings: ${err.response?.data?.detail || err.message}`)
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    
    // Validate inputs
    const validated: Partial<Config> = {}
    
    if (formData.base_download_path) {
      validated.base_download_path = formData.base_download_path.trim()
    }

    if (formData.temp_download_path !== undefined) {
      validated.temp_download_path = formData.temp_download_path?.trim() || null
    }
    
    if (formData.audio_extract_mode) {
      const validModes = ['copy', 'mp3_best', 'mp3_high', 'opus']
      if (validModes.includes(formData.audio_extract_mode)) {
        validated.audio_extract_mode = formData.audio_extract_mode
      }
    }
    
    if (formData.max_extraction_workers !== undefined) {
      const workers = Number(formData.max_extraction_workers)
      if (workers >= 1 && workers <= 16) {
        validated.max_extraction_workers = workers
      }
    }
    
    if (formData.batch_size !== undefined) {
      const size = Number(formData.batch_size)
      if (size >= 1 && size <= 1000) {
        validated.batch_size = size
      }
    }

    if (formData.sleep_interval_min !== undefined) {
      validated.sleep_interval_min = Number(formData.sleep_interval_min)
    }

    if (formData.sleep_interval_max !== undefined) {
      validated.sleep_interval_max = Number(formData.sleep_interval_max)
    }

    if (formData.concurrent_fragments !== undefined) {
      validated.concurrent_fragments = Number(formData.concurrent_fragments)
    }

    if (formData.enable_daily_auto_refresh !== undefined) {
      validated.enable_daily_auto_refresh = formData.enable_daily_auto_refresh
    }

    if (formData.enable_auto_discovery !== undefined) {
      validated.enable_auto_discovery = formData.enable_auto_discovery
    }

    if (formData.auto_discovery_interval_minutes !== undefined) {
      validated.auto_discovery_interval_minutes = Number(formData.auto_discovery_interval_minutes)
    }

    if (formData.daily_refresh_time !== undefined) {
      validated.daily_refresh_time = formData.daily_refresh_time?.trim() || '04:00'
    }

    if (formData.daily_refresh_timezone !== undefined) {
      validated.daily_refresh_timezone = formData.daily_refresh_timezone?.trim() || 'Asia/Kolkata'
    }

    if (formData.enable_git_metadata_sync !== undefined) {
      validated.enable_git_metadata_sync = formData.enable_git_metadata_sync
    }

    if (formData.git_remote_url !== undefined) {
      validated.git_remote_url = formData.git_remote_url?.trim() || null
    }

    if (formData.git_auth_token !== undefined) {
      validated.git_auth_token = formData.git_auth_token?.trim() || null
    }

    if (formData.git_branch !== undefined) {
      validated.git_branch = formData.git_branch?.trim() || 'main'
    }

    if (formData.git_user_name !== undefined) {
      validated.git_user_name = formData.git_user_name?.trim() || 'YouTube Playlist Manager'
    }

    if (formData.git_user_email !== undefined) {
      validated.git_user_email = formData.git_user_email?.trim() || 'yt-manager@homelab.local'
    }
    
    if (formData.cookies_file !== undefined) {
      validated.cookies_file = formData.cookies_file?.trim() || null
    }
    
    if (formData.use_browser_cookies !== undefined) {
      validated.use_browser_cookies = formData.use_browser_cookies
    }
    
    if (formData.browser_name) {
      const validBrowsers = ['chrome', 'firefox', 'edge', 'safari']
      if (validBrowsers.includes(formData.browser_name.toLowerCase())) {
        validated.browser_name = formData.browser_name.toLowerCase()
      }
    }

    if (formData.enable_stream_integrity_check !== undefined) {
      validated.enable_stream_integrity_check = formData.enable_stream_integrity_check
    }

    if (formData.flaresolverr_url !== undefined) {
      validated.flaresolverr_url = formData.flaresolverr_url?.trim() || null
    }

    updateConfig.mutate(validated)
  }

  return (
    <Modal
      isOpen={true}
      onClose={onClose}
      title="Settings"
      maxWidth="2xl"
    >
      {isLoading ? (
        <div className="text-center py-8">
          <Loader2 className="w-8 h-8 animate-spin mx-auto text-blue-600" />
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <FieldHeader
              label="Base Download Path"
              required={true}
              infoText="Root destination directory on your main storage drive (e.g. 2TB external HDD or /downloads) where all completed playlists and audio albums are stored."
            />
            <div className="flex gap-2">
              <input
                type="text"
                value={formData.base_download_path || ''}
                onChange={(e) => setFormData({ ...formData, base_download_path: e.target.value })}
                className="flex-1 px-3.5 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm"
                placeholder="E:\Music\Playlists or /downloads"
              />
              <button
                type="button"
                onClick={() => {
                  const input = document.createElement('input')
                  input.type = 'file'
                  input.webkitdirectory = true
                  input.onchange = (e: any) => {
                    const files = e.target.files
                    if (files && files.length > 0) {
                      const path = files[0].webkitRelativePath.split('/')[0]
                      setFormData({ ...formData, base_download_path: path })
                    }
                  }
                  input.click()
                }}
                className="px-4 py-2 bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-300 dark:hover:bg-gray-600 whitespace-nowrap flex items-center gap-2 text-sm"
              >
                <FolderOpen className="w-4 h-4" />
                Browse
              </button>
            </div>
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
              Note: Browser security limits full path picking. You may type or paste the exact absolute path manually.
            </p>
          </div>

          <div>
            <FieldHeader
              label="Temp Processing Directory"
              recommended="Optional: Fast SSD Buffer"
              infoText="Active multi-fragment chunk downloads and FFmpeg audio extraction occur on this fast SSD directory before being moved in a single sequential write to your main storage."
            />
            <div className="flex gap-2">
              <input
                type="text"
                value={formData.temp_download_path || ''}
                onChange={(e) => setFormData({ ...formData, temp_download_path: e.target.value })}
                className="flex-1 px-3.5 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm"
                placeholder="/downloads-temp (leave empty to download directly to main storage)"
              />
              <button
                type="button"
                onClick={() => {
                  const input = document.createElement('input')
                  input.type = 'file'
                  input.webkitdirectory = true
                  input.onchange = (e: any) => {
                    const files = e.target.files
                    if (files && files.length > 0) {
                      const path = files[0].webkitRelativePath.split('/')[0]
                      setFormData({ ...formData, temp_download_path: path })
                    }
                  }
                  input.click()
                }}
                className="px-4 py-2 bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-300 dark:hover:bg-gray-600 whitespace-nowrap flex items-center gap-2 text-sm"
              >
                <FolderOpen className="w-4 h-4" />
                Browse
              </button>
            </div>
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
              Leave empty if you do not have a separate SSD temp drive.
            </p>
          </div>

          <div>
            <FieldHeader
              label="Ad-hoc Downloads Directory"
              recommended="Default: _adhoc_downloads"
              infoText="Location where single video downloads (outside playlists) are stored. Defaults to '_adhoc_downloads' inside your Base Download Path."
            />
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="use_custom_adhoc_path"
                  checked={formData.use_custom_adhoc_path || false}
                  onChange={(e) => setFormData({ ...formData, use_custom_adhoc_path: e.target.checked })}
                  className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                />
                <label htmlFor="use_custom_adhoc_path" className="text-xs text-gray-700 dark:text-gray-300 font-medium cursor-pointer">
                  Use custom independent folder for ad-hoc downloads
                </label>
              </div>

              {formData.use_custom_adhoc_path && (
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={formData.adhoc_download_path || ''}
                    onChange={(e) => setFormData({ ...formData, adhoc_download_path: e.target.value })}
                    className="flex-1 px-3.5 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm font-mono"
                    placeholder="/path/to/QuickDownloads"
                  />
                </div>
              )}
            </div>
          </div>

          {/* Auto-Discovery & Library Sync Configuration */}
          <div className="bg-gray-50 dark:bg-gray-700/50 rounded-xl p-4 border border-gray-200 dark:border-gray-600 space-y-3">
            <div className="flex justify-between items-center flex-wrap gap-2">
              <div>
                <h4 className="text-sm font-semibold text-gray-900 dark:text-white flex items-center gap-1.5">
                  <span>Continuous Library Auto-Discovery</span>
                </h4>
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                  Automatically scans your download path for newly added playlist folders and builds the track index.
                </p>
              </div>

              <label className="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={formData.enable_auto_discovery ?? true}
                  onChange={(e) => setFormData({ ...formData, enable_auto_discovery: e.target.checked })}
                  className="sr-only peer"
                />
                <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none rounded-full peer dark:bg-gray-600 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-blue-600"></div>
              </label>
            </div>

            {formData.enable_auto_discovery && (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2 border-t border-gray-200 dark:border-gray-600">
                <div>
                  <FieldHeader
                    label="Scanning Interval"
                    infoText="How frequently the background worker scans your download folder for new playlists. Set to 'On Startup Only' to prevent spinning up NAS sleep drives."
                  />
                  <select
                    value={formData.auto_discovery_interval_minutes ?? 60}
                    onChange={(e) => setFormData({ ...formData, auto_discovery_interval_minutes: parseInt(e.target.value, 10) })}
                    className="w-full px-3.5 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm"
                  >
                    <option value={0}>0 — On Startup Only (NAS Sleep Friendly)</option>
                    <option value={15}>Every 15 Minutes</option>
                    <option value={30}>Every 30 Minutes</option>
                    <option value={60}>Every 1 Hour (Recommended)</option>
                    <option value={360}>Every 6 Hours</option>
                    <option value={1440}>Once Daily (24 Hours)</option>
                  </select>
                </div>

                <div className="flex flex-col justify-end">
                  <button
                    type="button"
                    onClick={async () => {
                      try {
                        const scanRes = await onboardingApi.scan(formData.base_download_path)
                        const count = scanRes.data.discovered_playlists.length
                        if (count > 0) {
                          if (confirm(`Discovered ${count} playlists (${scanRes.data.total_estimated_tracks} tracks). Import and index them into database now?`)) {
                            const res = await onboardingApi.confirm({ base_path: formData.base_download_path, items: scanRes.data.discovered_playlists })
                            alert(`✓ Success! ${res.data.playlists_imported} new playlists imported, ${res.data.tracks_indexed} tracks indexed.`)
                            queryClient.invalidateQueries({ queryKey: ['playlists'] })
                            queryClient.invalidateQueries({ queryKey: ['track-index'] })
                          }
                        } else {
                          alert('✓ Library is in sync. No new unmanaged playlist folders detected.')
                        }
                      } catch (err: any) {
                        alert(`Scan failed: ${err.message}`)
                      }
                    }}
                    className="w-full py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-semibold flex items-center justify-center gap-1.5 shadow-sm transition-colors"
                  >
                    <Search className="w-3.5 h-3.5" />
                    <span>Scan Library Now (On-Demand)</span>
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Deduplication & Space Reclaim Action Card */}
          <div className="bg-indigo-50/50 dark:bg-indigo-950/20 rounded-xl p-4 border border-indigo-200 dark:border-indigo-800/60 flex items-center justify-between flex-wrap gap-3">
            <div>
              <h4 className="text-sm font-semibold text-gray-900 dark:text-white flex items-center gap-1.5">
                <Sparkles className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
                <span>Library Deduplication & Space Reclaimer</span>
              </h4>
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                Scan for duplicate songs shared across playlists and convert redundant copies to zero-space hardlinks.
              </p>
            </div>
            {onOpenDeduplicate && (
              <button
                type="button"
                onClick={() => {
                  onClose()
                  onOpenDeduplicate()
                }}
                className="px-3.5 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-semibold flex items-center gap-1.5 shadow-sm transition-colors"
              >
                <HardDrive className="w-3.5 h-3.5" />
                <span>Open Deduplicator</span>
              </button>
            )}
          </div>

          <div>
            <FieldHeader
              label="Audio Extract Mode"
              recommended="Recommended: copy"
              infoText="Selects whether to directly extract native streams without re-encoding (instant, lossless) or transcode to MP3/Opus."
            />
            <select
              value={formData.audio_extract_mode || 'copy'}
              onChange={(e) => setFormData({ ...formData, audio_extract_mode: e.target.value })}
              className="w-full px-3.5 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm"
            >
              <option value="copy">Copy (Direct Stream Copy - Fastest & Lossless)</option>
              <option value="mp3_best">MP3 Best Quality (VBR ~250–320 kbps)</option>
              <option value="mp3_high">MP3 High Quality (VBR ~190–250 kbps)</option>
              <option value="opus">Opus (128 kbps)</option>
            </select>
            <AudioModeCard mode={formData.audio_extract_mode || 'copy'} />
          </div>

          {/* Primary Authentication: Upload cookies.txt & live status */}
          <div className="bg-gray-50 dark:bg-gray-700/50 rounded-xl p-4 border border-gray-200 dark:border-gray-600 space-y-3">
            <div className="flex justify-between items-start">
              <div>
                <h4 className="text-sm font-semibold text-gray-900 dark:text-white flex items-center gap-1.5">
                  <span>YouTube Authentication & Session Cookies</span>
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300">
                    Recommended
                  </span>
                </h4>
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                  Required for age-restricted or private playlists. Public tracks use mobile client emulation.
                </p>
              </div>
              {/* Status Badge */}
              <div>
                {cookieStatus?.status === 'valid' && (
                  <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                    Active (Expires in {cookieStatus.days_remaining}d)
                  </span>
                )}
                {cookieStatus?.status === 'expiring_soon' && (
                  <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300">
                    <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse"></span>
                    Expiring Soon ({cookieStatus.days_remaining}d left)
                  </span>
                )}
                {cookieStatus?.status === 'expired' && (
                  <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-rose-100 text-rose-800 dark:bg-rose-900/40 dark:text-rose-300">
                    <span className="w-1.5 h-1.5 rounded-full bg-rose-500"></span>
                    Expired ({cookieStatus.earliest_expiration})
                  </span>
                )}
                {cookieStatus?.status === 'not_installed' && (
                  <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-gray-200 dark:bg-gray-600 text-gray-700 dark:text-gray-300">
                    Not Installed
                  </span>
                )}
              </div>
            </div>

            {/* Upload form / Clear button */}
            <div className="flex gap-2 items-center">
              <label className="flex-1 cursor-pointer">
                <input
                  type="file"
                  accept=".txt"
                  className="hidden"
                  onChange={(e) => {
                    const file = e.target.files?.[0]
                    if (file) {
                      uploadCookiesMutation.mutate(file)
                    }
                  }}
                  disabled={uploadCookiesMutation.isPending}
                />
                <div className="px-3.5 py-2 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700/50 text-sm text-gray-700 dark:text-gray-200 flex items-center justify-center gap-2 transition-colors">
                  {uploadCookiesMutation.isPending ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      Uploading & Validating...
                    </>
                  ) : (
                    <>
                      <FolderOpen className="w-4 h-4 text-blue-500" />
                      {cookieStatus?.is_installed ? 'Replace cookies.txt' : 'Upload cookies.txt file'}
                    </>
                  )}
                </div>
              </label>
              {cookieStatus?.is_installed && (
                <button
                  type="button"
                  onClick={() => deleteCookiesMutation.mutate()}
                  disabled={deleteCookiesMutation.isPending}
                  className="px-3 py-2 bg-rose-50 hover:bg-rose-100 text-rose-700 dark:bg-rose-900/30 dark:hover:bg-rose-900/50 dark:text-rose-300 border border-rose-200 dark:border-rose-800 rounded-lg text-xs font-medium transition-colors"
                >
                  Remove
                </button>
              )}
            </div>
          </div>

          {/* Advanced Collapsible Settings */}
          <details className="group border border-gray-200 dark:border-gray-700 rounded-xl overflow-hidden bg-gray-50/50 dark:bg-gray-800/40">
            <summary className="px-4 py-3 cursor-pointer text-sm font-semibold text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700/50 transition-colors flex items-center justify-between">
              <span>Advanced Tuning & Performance</span>
              <span className="text-xs text-blue-600 dark:text-blue-400 group-open:rotate-180 transition-transform">▼</span>
            </summary>
            
            <div className="p-4 space-y-4 bg-white dark:bg-gray-800 border-t border-gray-200 dark:border-gray-700">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <FieldHeader
                    label="Max Concurrent Extractions"
                    recommended="Recommended: 4"
                    infoText="Number of parallel CPU worker threads used to extract and encode audio tracks simultaneously (1–16 workers)."
                  />
                  <input
                    type="number"
                    min="1"
                    max="16"
                    value={formData.max_extraction_workers || 4}
                    onChange={(e) => setFormData({ ...formData, max_extraction_workers: parseInt(e.target.value) })}
                    className="w-full px-3.5 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm"
                  />
                </div>

                <div>
                  <FieldHeader
                    label="Batch Size (Videos / run)"
                    recommended="Recommended: 200"
                    infoText="Maximum number of videos to download in a single batch to avoid platform rate-limiting and temporary IP blocks."
                  />
                  <input
                    type="number"
                    min="1"
                    max="1000"
                    value={formData.batch_size || 200}
                    onChange={(e) => setFormData({ ...formData, batch_size: parseInt(e.target.value) })}
                    className="w-full px-3.5 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <FieldHeader
                    label="Anti-Rate-Limit Delay (Min/Max s)"
                    recommended="Recommended: 1s – 5s"
                    infoText="Random delay pause (jitter) introduced between consecutive video downloads. Mimics human behavior to avoid temporary HTTP 429 bans on large playlists."
                  />
                  <div className="flex items-center gap-2">
                    <input
                      type="number"
                      min="0"
                      max="30"
                      value={formData.sleep_interval_min ?? 1}
                      onChange={(e) => setFormData({ ...formData, sleep_interval_min: parseInt(e.target.value) || 0 })}
                      className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm"
                      placeholder="Min (1s)"
                    />
                    <span className="text-gray-400 dark:text-gray-500 font-medium">–</span>
                    <input
                      type="number"
                      min="0"
                      max="60"
                      value={formData.sleep_interval_max ?? 5}
                      onChange={(e) => setFormData({ ...formData, sleep_interval_max: parseInt(e.target.value) || 0 })}
                      className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm"
                      placeholder="Max (5s)"
                    />
                  </div>
                </div>

                <div>
                  <FieldHeader
                    label="Concurrent DASH Fragments"
                    recommended="Recommended: 2"
                    infoText="Number of multi-threaded DASH video stream chunks downloaded concurrently per video. Higher values increase speed but can trigger IP blocks if set above 4."
                  />
                  <input
                    type="number"
                    min="1"
                    max="16"
                    value={formData.concurrent_fragments ?? 2}
                    onChange={(e) => setFormData({ ...formData, concurrent_fragments: parseInt(e.target.value) || 1 })}
                    className="w-full px-3.5 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm"
                  />
                </div>
              </div>

              {/* Browser Profile Extraction */}
              <div className="p-3 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 space-y-2">
                <FieldHeader
                  label="Browser Profile Extraction (Headless / Mounted Directory)"
                  infoText="Extracts cookies directly from a browser database directory (Chrome, Firefox, Edge, Safari). Useful for headless browser setups with mounted profile folders. If active, this is prioritized over cookies.txt."
                />
                <label className="flex items-center space-x-2 mt-1">
                  <input
                    type="checkbox"
                    checked={formData.use_browser_cookies || false}
                    onChange={(e) => setFormData({ ...formData, use_browser_cookies: e.target.checked })}
                    className="rounded text-blue-600 focus:ring-blue-500"
                  />
                  <span className="text-sm text-gray-700 dark:text-gray-300">Enable Browser Profile Extraction</span>
                </label>

                {formData.use_browser_cookies && (
                  <div className="mt-2 space-y-2">
                    <label className="block text-xs font-medium text-gray-700 dark:text-gray-300">
                      Browser Engine Profile
                    </label>
                    <select
                      value={formData.browser_name || 'chrome'}
                      onChange={(e) => setFormData({ ...formData, browser_name: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm"
                    >
                      <option value="chrome">Chrome</option>
                      <option value="firefox">Firefox</option>
                      <option value="edge">Edge</option>
                      <option value="safari">Safari</option>
                    </select>
                    <p className="text-[11px] text-amber-600 dark:text-amber-400">
                      ⚠️ Note: In Docker, ensure your browser profile volume is mounted into the container.
                    </p>
                  </div>
                )}
              </div>

              {/* Experimental Stream Integrity Safeguard */}
              <div className="p-3 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 space-y-1">
                <div className="flex items-start gap-3">
                  <input
                    type="checkbox"
                    id="enable_stream_integrity_check"
                    checked={formData.enable_stream_integrity_check || false}
                    onChange={(e) => setFormData({ ...formData, enable_stream_integrity_check: e.target.checked })}
                    className="mt-1 w-4 h-4 text-blue-600 rounded border-gray-300 dark:border-gray-600"
                  />
                  <div>
                    <label htmlFor="enable_stream_integrity_check" className="text-sm font-semibold text-gray-900 dark:text-white cursor-pointer">
                      Experimental Stream Integrity Verification (ffprobe)
                    </label>
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                      Inspects downloaded video containers for valid audio & video streams. Falls back gracefully if inspection fails.
                    </p>
                  </div>
                </div>
              </div>

              {/* FlareSolverr Homelab Proxy */}
              <div className="p-3 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 space-y-2">
                <FieldHeader
                  label="FlareSolverr Proxy URL"
                  recommended="Optional Homelab Proxy"
                  infoText="Connects to a local FlareSolverr Docker container (e.g. http://localhost:8191/v1) to bypass Cloudflare protection if downloading from external websites."
                />
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={formData.flaresolverr_url || ''}
                    onChange={(e) => setFormData({ ...formData, flaresolverr_url: e.target.value })}
                    className="flex-1 px-3.5 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm"
                    placeholder="http://localhost:8191/v1"
                  />
                  <button
                    type="button"
                    onClick={() => testFlareSolverrMutation.mutate(formData.flaresolverr_url || undefined)}
                    disabled={testFlareSolverrMutation.isPending}
                    className="px-3 py-2 bg-purple-600 text-white text-xs font-medium rounded-lg hover:bg-purple-700 disabled:bg-gray-400 flex items-center gap-1.5 whitespace-nowrap"
                  >
                    {testFlareSolverrMutation.isPending ? (
                      <>
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        Testing...
                      </>
                    ) : (
                      'Test Connection'
                    )}
                  </button>
                </div>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  Connect your homelab FlareSolverr container to bypass anti-bot challenges and solve session cookies.
                </p>
              </div>

              {/* 24/7 Daily Background Metadata Scheduler */}
              <div className="p-3 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 space-y-3">
                <FieldHeader
                  label="24/7 Daily Background Metadata Scheduler"
                  recommended="Recommended: Enabled"
                  infoText="Automatically scans all playlists at your configured overnight time in the background to detect newly added tracks, deleted videos, and silently privatized songs without requiring container restarts."
                />
                <label className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    checked={formData.enable_daily_auto_refresh ?? true}
                    onChange={(e) => setFormData({ ...formData, enable_daily_auto_refresh: e.target.checked })}
                    className="rounded text-blue-600 focus:ring-blue-500"
                  />
                  <span className="text-sm font-medium text-gray-700 dark:text-gray-300">Enable Daily Auto-Scan</span>
                </label>

                {formData.enable_daily_auto_refresh && (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2 border-t border-gray-100 dark:border-gray-700/60">
                    <div>
                      <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">
                        Daily Trigger Time (24-Hour)
                      </label>
                      <input
                        type="time"
                        value={formData.daily_refresh_time || '04:00'}
                        onChange={(e) => setFormData({ ...formData, daily_refresh_time: e.target.value })}
                        className="w-full px-3 py-1.5 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-xs font-mono"
                      />
                    </div>

                    <div>
                      <div className="flex justify-between items-center mb-1">
                        <label className="block text-xs font-medium text-gray-700 dark:text-gray-300">
                          Timezone (IANA)
                        </label>
                        <button
                          type="button"
                          onClick={() => {
                            try {
                              const tz = Intl.DateTimeFormat().resolvedOptions().timeZone
                              if (tz) setFormData({ ...formData, daily_refresh_timezone: tz })
                            } catch (e) {}
                          }}
                          className="text-[11px] text-blue-600 dark:text-blue-400 hover:underline"
                        >
                          Auto-detect
                        </button>
                      </div>
                      <input
                        type="text"
                        value={formData.daily_refresh_timezone || 'Asia/Kolkata'}
                        onChange={(e) => setFormData({ ...formData, daily_refresh_timezone: e.target.value })}
                        list="timezone-options"
                        className="w-full px-3 py-1.5 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-xs font-mono"
                        placeholder="e.g. Asia/Kolkata or America/New_York"
                      />
                      <datalist id="timezone-options">
                        <option value="Asia/Kolkata">Asia/Kolkata (IST +5:30)</option>
                        <option value="UTC">UTC (+0:00)</option>
                        <option value="America/New_York">America/New_York (EST/EDT)</option>
                        <option value="America/Chicago">America/Chicago (CST/CDT)</option>
                        <option value="America/Denver">America/Denver (MST/MDT)</option>
                        <option value="America/Los_Angeles">America/Los_Angeles (PST/PDT)</option>
                        <option value="Europe/London">Europe/London (GMT/BST)</option>
                        <option value="Europe/Berlin">Europe/Berlin (CET/CEST)</option>
                        <option value="Europe/Paris">Europe/Paris (CET/CEST)</option>
                        <option value="Asia/Tokyo">Asia/Tokyo (JST +9:00)</option>
                        <option value="Asia/Singapore">Asia/Singapore (SGT +8:00)</option>
                        <option value="Australia/Sydney">Australia/Sydney (AEST/AEDT)</option>
                      </datalist>
                    </div>
                  </div>
                )}
              </div>

              {/* Automated Git Metadata Versioning & GitHub Sync */}
              <div className="p-3 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 space-y-3">
                <FieldHeader
                  label="Automated Git Metadata Versioning & GitHub Sync"
                  recommended="Recommended: Enabled"
                  infoText="Initializes a Git repo in your download folder (with media files strictly ignored) and creates one atomic commit per playlist whenever playlist_info.json changes, listing exact video IDs of added or removed/privatized songs."
                />
                <label className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    checked={formData.enable_git_metadata_sync ?? false}
                    onChange={(e) => setFormData({ ...formData, enable_git_metadata_sync: e.target.checked })}
                    className="rounded text-blue-600 focus:ring-blue-500"
                  />
                  <span className="text-sm font-medium text-gray-700 dark:text-gray-300">Enable Git Versioning for playlist_info.json</span>
                </label>

                {formData.enable_git_metadata_sync && (
                  <div className="space-y-2.5 pt-1 border-t border-gray-100 dark:border-gray-700/60">
                    <div>
                      <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">
                        GitHub / Remote Git URL (Optional)
                      </label>
                      <input
                        type="text"
                        value={formData.git_remote_url || ''}
                        onChange={(e) => setFormData({ ...formData, git_remote_url: e.target.value })}
                        className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-xs"
                        placeholder="https://github.com/username/yt-playlists-metadata.git"
                      />
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                      <div>
                        <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">
                          GitHub Auth Token / PAT (Optional)
                        </label>
                        <input
                          type="password"
                          value={formData.git_auth_token || ''}
                          onChange={(e) => setFormData({ ...formData, git_auth_token: e.target.value })}
                          className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-xs font-mono"
                          placeholder="ghp_xxxx..."
                        />
                      </div>

                      <div>
                        <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">
                          Target Git Branch
                        </label>
                        <input
                          type="text"
                          value={formData.git_branch || 'main'}
                          onChange={(e) => setFormData({ ...formData, git_branch: e.target.value })}
                          className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-xs"
                          placeholder="main"
                        />
                      </div>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                      <div>
                        <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">
                          Git Committer / Author Name
                        </label>
                        <input
                          type="text"
                          value={formData.git_user_name || ''}
                          onChange={(e) => setFormData({ ...formData, git_user_name: e.target.value })}
                          className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-xs"
                          placeholder="e.g. Blank1611 or YouTube Playlist Manager"
                        />
                      </div>

                      <div>
                        <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">
                          Git Committer / Author Email
                        </label>
                        <input
                          type="email"
                          value={formData.git_user_email || ''}
                          onChange={(e) => setFormData({ ...formData, git_user_email: e.target.value })}
                          className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-xs"
                          placeholder="e.g. your.email@example.com"
                        />
                      </div>
                    </div>
                    <p className="text-[11px] text-gray-500 dark:text-gray-400">
                      Tip: Use your GitHub account email address so commits link directly to your profile avatar and contribution graph.
                    </p>

                    <button
                      type="button"
                      onClick={() => testGitSyncMutation.mutate()}
                      disabled={testGitSyncMutation.isPending}
                      className="px-3 py-1.5 bg-gray-800 hover:bg-black dark:bg-gray-700 dark:hover:bg-gray-600 text-white text-xs font-medium rounded-lg disabled:bg-gray-400 flex items-center gap-1.5"
                    >
                      {testGitSyncMutation.isPending ? (
                        <>
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          Testing Git Sync...
                        </>
                      ) : (
                        'Test Git Connection'
                      )}
                    </button>
                  </div>
                )}
              </div>
            </div>
          </details>

          {/* yt-dlp updater box */}
          <div className="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-4 border border-gray-200 dark:border-gray-600 space-y-2">
            <div className="flex justify-between items-center">
              <div>
                <h4 className="text-sm font-semibold text-gray-900 dark:text-white">yt-dlp Engine</h4>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  Installed Version: <span className="font-mono font-medium text-blue-600 dark:text-blue-400">{ytdlpVersionData?.version || 'Loading...'}</span>
                </p>
              </div>
              <button
                type="button"
                onClick={() => updateYtdlpMutation.mutate()}
                disabled={updateYtdlpMutation.isPending}
                className="px-3 py-1.5 bg-emerald-600 text-white text-xs font-medium rounded-md hover:bg-emerald-700 disabled:bg-gray-400 flex items-center gap-1.5"
              >
                {updateYtdlpMutation.isPending ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    Updating...
                  </>
                ) : (
                  'Update yt-dlp'
                )}
              </button>
            </div>
          </div>

          <div className="flex gap-2 pt-4">
            <Button
              type="submit"
              loading={updateConfig.isPending}
              className="flex-1"
            >
              Save Settings
            </Button>
            <Button
              type="button"
              variant="secondary"
              onClick={onClose}
            >
              Cancel
            </Button>
          </div>
        </form>
      )}
    </Modal>
  )
}
