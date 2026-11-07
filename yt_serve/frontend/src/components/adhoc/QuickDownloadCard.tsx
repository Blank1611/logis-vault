import React, { useState, useEffect, useRef } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { 
  adhocApi, type AdhocProbeResult, type AdhocDownloadParams, type TrackedDirectory
} from '../../services/api'
import { Button } from '../ui/Button'
import type { Job } from '../../services/types'
import { StatusBadge } from '../ui/StatusBadge'
import { DualTierProgressBar } from '../ui/ProgressBar'
import { jobsApi } from '../../services/api'
import { 
  Download, Search, Film, Music, Layers, CheckCircle2, AlertCircle, Loader2, Sparkles, Folder, Clock, Eye, Terminal, XCircle, ListOrdered, ChevronDown, Check, Star, History
} from 'lucide-react'
import { DirectoryPickerModal } from '../modals/DirectoryPickerModal'
import { AdhocMediaViewer } from './AdhocMediaViewer'

export interface QuickDownloadCardProps {
  jobs?: Job[]
  onJobStarted?: (jobId: number) => void
  onViewJobLogs?: (jobId: number) => void
}

export const QuickDownloadCard: React.FC<QuickDownloadCardProps> = ({ 
  jobs = [], 
  onJobStarted,
  onViewJobLogs 
}) => {
  const queryClient = useQueryClient()
  const [url, setUrl] = useState('')
  const [probeResult, setProbeResult] = useState<AdhocProbeResult | null>(null)
  const [extractMode, setExtractMode] = useState<'video_only' | 'audio_only' | 'both'>('both')
  const [videoQuality, setVideoQuality] = useState<string>('best')
  const [audioFormat, setAudioFormat] = useState<string>('copy')
  const [selectedDirectoryPath, setSelectedDirectoryPath] = useState<string>('')
  const [searchFilterQuery, setSearchFilterQuery] = useState<string>('')
  const [isComboboxOpen, setIsComboboxOpen] = useState(false)
  const comboboxRef = useRef<HTMLDivElement>(null)
  const [isPickerOpen, setIsPickerOpen] = useState(false)
  const [mediaRefreshTrigger, setMediaRefreshTrigger] = useState(0)
  const [successJobId, setSuccessJobId] = useState<number | null>(null)
  const [cancellingJobId, setCancellingJobId] = useState<number | null>(null)

  // Commit selected directory to model and persistence
  const handleCommitDirectory = (path: string) => {
    setSelectedDirectoryPath(path)
    try {
      localStorage.setItem('logis_adhoc_dest_path', path)
    } catch {
      // ignore
    }
    setSearchFilterQuery('')
    setIsComboboxOpen(false)
  }

  // Close combobox on outside click and discard transient search filter
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (comboboxRef.current && !comboboxRef.current.contains(e.target as Node)) {
        setIsComboboxOpen(false)
        setSearchFilterQuery('')
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  // Fetch tracked directories
  const { data: trackedDirectories = [], refetch: refetchDirectories } = useQuery<TrackedDirectory[]>({
    queryKey: ['adhocDirectories'],
    queryFn: async () => {
      const res = await adhocApi.getDirectories()
      return res.data
    },
  })

  // Preselect MRU directory from localStorage or trackedDirectories on initial load
  useEffect(() => {
    if (!selectedDirectoryPath && trackedDirectories.length > 0) {
      try {
        const savedDir = localStorage.getItem('logis_adhoc_dest_path')
        if (savedDir && trackedDirectories.some((d) => d.path === savedDir)) {
          setSelectedDirectoryPath(savedDir)
          return
        }
      } catch {
        // ignore
      }

      // Find directory with newest last_used_at timestamp
      const withUsage = trackedDirectories.filter((d) => Boolean(d.last_used_at))
      if (withUsage.length > 0) {
        const sorted = [...withUsage].sort((a, b) => (b.last_used_at || '').localeCompare(a.last_used_at || ''))
        setSelectedDirectoryPath(sorted[0].path)
        return
      }

      // Fallback: Tier 1 default or first entry
      const def = trackedDirectories.find((d) => d.tier === 'default' || d.is_default) || trackedDirectories[0]
      if (def) {
        setSelectedDirectoryPath(def.path)
      }
    }
  }, [trackedDirectories])

  // Watch for completed adhoc jobs to auto-refresh media gallery
  useEffect(() => {
    const completedAdhocJob = jobs.find(
      (j) => (j.id === successJobId || j.job_type?.startsWith('adhoc_')) && j.status === 'completed'
    )
    if (completedAdhocJob) {
      setMediaRefreshTrigger((prev) => prev + 1)
      refetchDirectories()
    }
  }, [jobs, successJobId])

  // 1. Probe Mutation
  const probeMutation = useMutation({
    mutationFn: (targetUrl: string) => adhocApi.probe(targetUrl),
    onSuccess: (res) => {
      setProbeResult(res.data)
      setSuccessJobId(null)
      // Only set destination path if not already committed by user/MRU
      if (res.data.default_download_path && !selectedDirectoryPath) {
        setSelectedDirectoryPath(res.data.default_download_path)
      }
      if (res.data.available_resolutions && res.data.available_resolutions.length > 0) {
        setVideoQuality(String(res.data.available_resolutions[0].height || 'best'))
      }
    },
  })

  // 2. Start Download Mutation
  const startMutation = useMutation({
    mutationFn: (params: AdhocDownloadParams) => adhocApi.start(params),
    onSuccess: (res) => {
      setSuccessJobId(res.data.job_id)
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
      queryClient.invalidateQueries({ queryKey: ['tracks'] })
      if (selectedDirectoryPath) {
        try {
          localStorage.setItem('logis_adhoc_dest_path', selectedDirectoryPath)
        } catch {
          // ignore
        }
      }
      if (onJobStarted) {
        onJobStarted(res.data.job_id)
      }
    },
  })

  // Cancel Job Mutation
  const handleCancelJob = async (jobId: number) => {
    try {
      setCancellingJobId(jobId)
      await jobsApi.cancel(jobId)
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
    } catch (err) {
      console.error('Failed to cancel job:', err)
    } finally {
      setCancellingJobId(null)
    }
  }

  // Find active adhoc jobs (or most recent matching successJobId)
  const activeAdhocJob = jobs.find(j => 
    (j.id === successJobId || (j.job_type && j.job_type.startsWith('adhoc_'))) && 
    (j.status === 'running' || j.status === 'pending')
  ) || (successJobId ? jobs.find(j => j.id === successJobId) : null)

  const handleProbe = (e: React.FormEvent) => {
    e.preventDefault()
    if (!url.trim()) return
    setProbeResult(null)
    probeMutation.mutate(url.trim())
  }

  const handleStartDownload = () => {
    if (!url.trim()) return
    startMutation.mutate({
      url: url.trim(),
      video_quality: videoQuality,
      audio_format: audioFormat,
      extract_mode: extractMode,
      custom_download_path: selectedDirectoryPath.trim() ? selectedDirectoryPath.trim() : undefined,
    })
  }

  return (
    <div className="glass-panel rounded-2xl shadow-2xl border border-white/10 overflow-hidden mb-8">
      {/* Header Banner */}
      <div className="bg-gradient-to-r from-cyan-600/40 via-blue-600/40 to-indigo-600/40 border-b border-white/10 p-6 text-white backdrop-blur-xl">
        <div className="flex items-center gap-3.5">
          <div className="p-3 bg-cyan-500/20 rounded-2xl border border-cyan-400/40 backdrop-blur-md shadow-lg shadow-cyan-500/20">
            <Sparkles className="w-6 h-6 text-cyan-300" />
          </div>
          <div>
            <h2 className="text-xl font-extrabold tracking-tight bg-gradient-to-r from-white via-slate-100 to-cyan-300 bg-clip-text text-transparent">
              Quick / Single Video Downloader
            </h2>
            <p className="text-xs text-slate-300 mt-0.5">
              Probe formats, choose any target resolution up to 4K, extract lossless audio, and download directly without subscribing to a playlist.
            </p>
          </div>
        </div>
      </div>

      <div className="p-6 space-y-6">
        {/* URL Input Form */}
        <form onSubmit={handleProbe} className="space-y-2">
          <label className="text-xs font-bold text-slate-300 uppercase tracking-wider">
            YouTube Video URL
          </label>
          <div className="flex gap-2">
            <input
              type="text"
              placeholder="https://www.youtube.com/watch?v=... or https://youtu.be/..."
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              className="flex-1 glass-input px-4 py-2.5 rounded-xl text-sm placeholder-slate-400 focus:outline-none"
            />
            <button
              type="submit"
              disabled={!url.trim() || probeMutation.isPending}
              className="glass-btn-cyan px-5 py-2.5 rounded-xl text-xs font-bold flex items-center gap-2 shrink-0 disabled:opacity-50 cursor-pointer shadow-md"
            >
              {probeMutation.isPending ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Inspecting...</span>
                </>
              ) : (
                <>
                  <Search className="w-4 h-4" />
                  <span>Inspect Streams</span>
                </>
              )}
            </button>
          </div>
        </form>

        {/* Error Alert */}
        {probeMutation.isError && (
          <div className="p-4 bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 rounded-xl flex items-center gap-3 text-rose-800 dark:text-rose-200 text-xs">
            <AlertCircle className="w-5 h-5 text-rose-500 shrink-0" />
            <div>
              <p className="font-semibold">Inspection Failed</p>
              <p>{(probeMutation.error as any)?.message || 'Could not fetch video information. Verify the URL and connectivity.'}</p>
            </div>
          </div>
        )}

        {/* Probed Video Preview Card & Format Selectors */}
        {probeResult && (
          <div className="bg-gray-50 dark:bg-gray-900/60 border border-gray-200 dark:border-gray-700 rounded-xl p-5 space-y-6">
            {/* Video Overview */}
            <div className="flex flex-col sm:flex-row gap-4 items-start">
              {probeResult.thumbnail && (
                <div className="relative w-full sm:w-48 h-28 bg-gray-200 dark:bg-gray-800 rounded-lg overflow-hidden shrink-0 shadow-sm">
                  <img
                    src={probeResult.thumbnail}
                    alt={probeResult.title}
                    className="w-full h-full object-cover"
                  />
                  <div className="absolute bottom-1.5 right-1.5 px-1.5 py-0.5 bg-black/80 text-white text-[10px] font-mono rounded font-semibold flex items-center gap-1">
                    <Clock className="w-3 h-3" />
                    <span>{probeResult.formatted_duration}</span>
                  </div>
                </div>
              )}

              <div className="flex-1 space-y-1.5">
                <h3 className="text-base font-bold text-gray-900 dark:text-white line-clamp-2">
                  {probeResult.title}
                </h3>
                <p className="text-xs font-semibold text-indigo-600 dark:text-indigo-400">
                  {probeResult.uploader}
                </p>
                <div className="flex items-center gap-3 text-[11px] text-gray-500 dark:text-gray-400 pt-1">
                  <span className="font-mono bg-gray-200 dark:bg-gray-800 px-2 py-0.5 rounded">
                    ID: {probeResult.video_id}
                  </span>
                  {probeResult.view_count > 0 && (
                    <span className="flex items-center gap-1">
                      <Eye className="w-3.5 h-3.5" />
                      <span>{probeResult.view_count.toLocaleString()} views</span>
                    </span>
                  )}
                </div>
              </div>
            </div>

            {/* Mode Selector Buttons */}
            <div className="space-y-2">
              <label className="text-xs font-bold text-gray-700 dark:text-gray-300 uppercase tracking-wider">
                Download & Extraction Mode
              </label>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
                <button
                  type="button"
                  onClick={() => setExtractMode('both')}
                  className={`p-3 rounded-xl border text-left transition-all ${
                    extractMode === 'both'
                      ? 'border-indigo-600 bg-indigo-50 dark:bg-indigo-950/40 text-indigo-950 dark:text-indigo-200 ring-2 ring-indigo-500/20'
                      : 'border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:border-gray-300'
                  }`}
                >
                  <div className="flex items-center gap-2 font-bold text-xs">
                    <Layers className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
                    <span>Both (Video + Audio)</span>
                  </div>
                  <p className="text-[11px] text-gray-500 dark:text-gray-400 mt-1">
                    Saves full HD/4K video and generates standalone MP3/Opus file.
                  </p>
                </button>

                <button
                  type="button"
                  onClick={() => setExtractMode('video_only')}
                  className={`p-3 rounded-xl border text-left transition-all ${
                    extractMode === 'video_only'
                      ? 'border-indigo-600 bg-indigo-50 dark:bg-indigo-950/40 text-indigo-950 dark:text-indigo-200 ring-2 ring-indigo-500/20'
                      : 'border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:border-gray-300'
                  }`}
                >
                  <div className="flex items-center gap-2 font-bold text-xs">
                    <Film className="w-4 h-4 text-blue-600 dark:text-blue-400" />
                    <span>Complete Video (.mp4)</span>
                  </div>
                  <p className="text-[11px] text-gray-500 dark:text-gray-400 mt-1">
                    Full video with combined audio stream (no extra MP3).
                  </p>
                </button>

                <button
                  type="button"
                  onClick={() => setExtractMode('audio_only')}
                  className={`p-3 rounded-xl border text-left transition-all ${
                    extractMode === 'audio_only'
                      ? 'border-indigo-600 bg-indigo-50 dark:bg-indigo-950/40 text-indigo-950 dark:text-indigo-200 ring-2 ring-indigo-500/20'
                      : 'border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:border-gray-300'
                  }`}
                >
                  <div className="flex items-center gap-2 font-bold text-xs">
                    <Music className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
                    <span>Audio Only (.mp3/.opus)</span>
                  </div>
                  <p className="text-[11px] text-gray-500 dark:text-gray-400 mt-1">
                    Fast audio extraction without keeping video file.
                  </p>
                </button>
              </div>
            </div>

            {/* Quality Selectors Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {/* Video Resolution */}
              {extractMode !== 'audio_only' && (
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-gray-700 dark:text-gray-300">
                    Video Resolution Quality
                  </label>
                  <select
                    value={videoQuality}
                    onChange={(e) => setVideoQuality(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-xs bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                  >
                    <option value="best">Best Available (Source Resolution)</option>
                    {probeResult.available_resolutions.map((r, i) => (
                      <option key={i} value={String(r.height)}>
                        {r.label} {r.badge ? `[${r.badge}]` : ''}
                      </option>
                    ))}
                  </select>
                  {(() => {
                    const selected = probeResult.available_resolutions.find(r => String(r.height) === videoQuality)
                    if (selected && selected.badge) {
                      return (
                        <div className="flex items-center gap-2 mt-1.5 text-xs text-gray-500 dark:text-gray-400" title={selected.badge_tooltip}>
                          <span className={`px-2 py-0.5 rounded-full text-[11px] font-medium ${
                            selected.is_direct ? 'bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-300' : 'bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300'
                          }`}>
                            {selected.badge}
                          </span>
                          <span className="text-[11px]">{selected.badge_tooltip}</span>
                        </div>
                      )
                    }
                    return null
                  })()}
                </div>
              )}

              {/* Audio Preset */}
              {extractMode !== 'video_only' && (
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-gray-700 dark:text-gray-300">
                    Audio Extraction Quality Preset
                  </label>
                  <select
                    value={audioFormat}
                    onChange={(e) => setAudioFormat(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-xs bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                  >
                    <option value="copy">Native Copy (Fastest & Lossless)</option>
                    <option value="mp3_best">MP3 Best Quality (VBR ~320 kbps)</option>
                    <option value="opus">Opus Audio (160 kbps)</option>
                    <option value="flac">FLAC (Lossless)</option>
                    <option value="m4a">M4A AAC (256 kbps)</option>
                  </select>
                </div>
              )}
            </div>

            {/* Destination Folder Path with Smart Combobox & Browse Button */}
            <div className="space-y-2 pt-2 border-t border-gray-200 dark:border-gray-700">
              <div className="flex items-center justify-between">
                <label className="text-xs font-semibold text-gray-700 dark:text-gray-300 flex items-center gap-1.5">
                  <Folder className="w-3.5 h-3.5 text-amber-500" />
                  <span>Destination Folder</span>
                </label>
                <span className="text-[11px] text-gray-500 dark:text-gray-400">
                  Mounted container storage
                </span>
              </div>

              <div className="flex gap-2">
                <div ref={comboboxRef} className="relative flex-1">
                  <div className="relative">
                    <input
                      type="text"
                      value={isComboboxOpen ? searchFilterQuery : selectedDirectoryPath}
                      onFocus={() => {
                        setIsComboboxOpen(true)
                        setSearchFilterQuery('')
                      }}
                      onClick={() => {
                        if (!isComboboxOpen) {
                          setIsComboboxOpen(true)
                          setSearchFilterQuery('')
                        }
                      }}
                      onChange={(e) => {
                        setSearchFilterQuery(e.target.value)
                        setIsComboboxOpen(true)
                      }}
                      onKeyDown={(e) => {
                        if (e.key === 'Escape') {
                          setIsComboboxOpen(false)
                          setSearchFilterQuery('')
                        } else if (e.key === 'Enter') {
                          const queryNorm = searchFilterQuery.trim().toLowerCase()
                          const matches = trackedDirectories.filter((d: TrackedDirectory) => {
                            if (!queryNorm) return true
                            return (
                              d.path.toLowerCase().includes(queryNorm) ||
                              d.display_name.toLowerCase().includes(queryNorm)
                            )
                          })
                          if (matches.length > 0) {
                            handleCommitDirectory(matches[0].path)
                          }
                        }
                      }}
                      placeholder={selectedDirectoryPath || "Search or select destination path..."}
                      className="w-full pl-8 pr-8 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-xs bg-white dark:bg-gray-700 text-gray-900 dark:text-white font-mono placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/50"
                    />
                    <Search className="w-3.5 h-3.5 text-gray-400 absolute left-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
                    <button
                      type="button"
                      onClick={() => {
                        if (isComboboxOpen) {
                          setIsComboboxOpen(false)
                          setSearchFilterQuery('')
                        } else {
                          setIsComboboxOpen(true)
                          setSearchFilterQuery('')
                        }
                      }}
                      className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-200 p-0.5 rounded transition-colors"
                      tabIndex={-1}
                    >
                      <ChevronDown className={`w-3.5 h-3.5 transition-transform duration-200 ${isComboboxOpen ? 'rotate-180' : ''}`} />
                    </button>
                  </div>

                  {/* Dropdown Panel */}
                  {isComboboxOpen && (
                    <div className="absolute left-0 right-0 top-full mt-1.5 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl shadow-2xl max-h-72 overflow-y-auto divide-y divide-gray-100 dark:divide-gray-700/60 p-1.5 z-50">
                      {(() => {
                        const queryNorm = searchFilterQuery.trim().toLowerCase()
                        const matches = trackedDirectories.filter((d: TrackedDirectory) => {
                          if (!queryNorm) return true
                          return (
                            d.path.toLowerCase().includes(queryNorm) ||
                            d.display_name.toLowerCase().includes(queryNorm)
                          )
                        })

                        const tier1 = matches.filter((d: TrackedDirectory) => d.tier === 'default' || d.is_default)
                        const tier2 = matches.filter((d: TrackedDirectory) => d.tier === 'recent_adhoc' && !d.is_default)
                        const tier3 = matches.filter((d: TrackedDirectory) => d.tier === 'unmanaged' && !d.is_default)

                        const renderItem = (d: TrackedDirectory, icon: React.ReactNode, tierBadge?: React.ReactNode) => {
                          const isSelected = selectedDirectoryPath === d.path
                          return (
                            <button
                              key={d.path}
                              type="button"
                              onClick={() => handleCommitDirectory(d.path)}
                              className={`w-full text-left px-2.5 py-1.5 rounded-lg flex items-center justify-between text-xs transition-colors ${
                                isSelected
                                  ? 'bg-indigo-50 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300 font-semibold'
                                  : 'hover:bg-gray-100 dark:hover:bg-gray-700/60 text-gray-800 dark:text-gray-200'
                              }`}
                            >
                              <div className="flex items-center gap-2 truncate">
                                <span className="shrink-0">{icon}</span>
                                <span className="font-mono text-[11px] truncate">{d.path}</span>
                              </div>
                              <div className="flex items-center gap-1.5 shrink-0 pl-2">
                                {tierBadge}
                                {d.item_count > 0 && (
                                  <span className="text-[10px] text-gray-400">
                                    {d.item_count} files
                                  </span>
                                )}
                                {isSelected && <Check className="w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400 shrink-0 ml-1" />}
                              </div>
                            </button>
                          )
                        }

                        if (matches.length === 0) {
                          return (
                            <div className="p-3 text-center text-xs text-gray-500 dark:text-gray-400 space-y-1">
                              <AlertCircle className="w-4 h-4 mx-auto text-amber-500" />
                              <p className="font-medium text-gray-700 dark:text-gray-300">No matching directories found</p>
                              <p className="text-[11px] text-gray-400">
                                New folders can be created using the &quot;Browse...&quot; button.
                              </p>
                            </div>
                          )
                        }

                        return (
                          <div className="space-y-2">
                            {/* Tier 1: Active Default */}
                            {tier1.length > 0 && (
                              <div className="space-y-1">
                                <div className="px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-amber-600 dark:text-amber-400 flex items-center gap-1">
                                  <Star className="w-3 h-3 fill-amber-400 text-amber-500" />
                                  <span>Active Default Ad-hoc</span>
                                </div>
                                {tier1.map((d) =>
                                  renderItem(
                                    d,
                                    <Folder className="w-3.5 h-3.5 text-amber-500" />,
                                    <span className="px-1.5 py-0.5 rounded text-[10px] bg-amber-100 dark:bg-amber-900/50 text-amber-700 dark:text-amber-300 font-semibold">
                                      Default
                                    </span>
                                  )
                                )}
                              </div>
                            )}

                            {/* Tier 2: Recently Used (Top 5) */}
                            {tier2.length > 0 && (
                              <div className="space-y-1">
                                <div className="px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-cyan-600 dark:text-cyan-400 flex items-center gap-1">
                                  <History className="w-3 h-3 text-cyan-500" />
                                  <span>Recently Used Ad-hoc</span>
                                </div>
                                {tier2.map((d) =>
                                  renderItem(
                                    d,
                                    <Folder className="w-3.5 h-3.5 text-cyan-500" />,
                                    <span className="px-1.5 py-0.5 rounded text-[10px] bg-cyan-100 dark:bg-cyan-900/40 text-cyan-700 dark:text-cyan-300">
                                      Recent
                                    </span>
                                  )
                                )}
                              </div>
                            )}

                            {/* Tier 3: Unmanaged Library Folders */}
                            {tier3.length > 0 && (
                              <div className="space-y-1">
                                <div className="px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-gray-500 dark:text-gray-400 flex items-center gap-1">
                                  <Folder className="w-3 h-3 text-gray-400" />
                                  <span>Available Unmanaged Folders</span>
                                </div>
                                {tier3.map((d) =>
                                  renderItem(
                                    d,
                                    <Folder className="w-3.5 h-3.5 text-gray-400" />
                                  )
                                )}
                              </div>
                            )}
                          </div>
                        )
                      })()}
                    </div>
                  )}
                </div>

                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setIsPickerOpen(true)}
                  icon={<Folder className="w-3.5 h-3.5 text-amber-500" />}
                >
                  Browse...
                </Button>
              </div>
            </div>

            {/* Download Execution Button */}
            <div className="flex justify-end pt-2">
              <Button
                variant="primary"
                size="md"
                onClick={handleStartDownload}
                disabled={startMutation.isPending}
                className="bg-indigo-600 hover:bg-indigo-700 px-6 flex items-center gap-2 shadow-md"
              >
                {startMutation.isPending ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Enqueuing Download...</span>
                  </>
                ) : (
                  <>
                    <Download className="w-4 h-4" />
                    <span>Start Quick Download</span>
                  </>
                )}
              </Button>
            </div>
          </div>
        )}

        {/* Active Download Progress Card */}
        {activeAdhocJob && (
          <div className="bg-gradient-to-br from-indigo-50/70 to-blue-50/70 dark:from-indigo-950/30 dark:to-blue-950/30 border border-indigo-200 dark:border-indigo-800 rounded-2xl p-5 shadow-sm space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <div className="p-2.5 bg-indigo-600 text-white rounded-xl shadow-sm">
                  {activeAdhocJob.status === 'running' ? (
                    <Loader2 className="w-5 h-5 animate-spin" />
                  ) : (
                    <Film className="w-5 h-5" />
                  )}
                </div>
                <div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <h3 className="text-sm font-bold text-gray-900 dark:text-white">
                      {activeAdhocJob.current_video_title || (probeResult && probeResult.title) || `Quick Download #${activeAdhocJob.id}`}
                    </h3>
                    <StatusBadge status={activeAdhocJob.status} />
                    <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-indigo-100 dark:bg-indigo-900/60 text-indigo-700 dark:text-indigo-300 font-semibold">
                      Job #{activeAdhocJob.id}
                    </span>
                  </div>
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5 flex items-center gap-2">
                    <span>Format: {activeAdhocJob.job_type.replace('adhoc_', '').toUpperCase()}</span>
                    {activeAdhocJob.current_video_speed && activeAdhocJob.current_video_speed > 0 && (
                      <>
                        <span>•</span>
                        <span className="font-semibold text-indigo-600 dark:text-indigo-400">
                          {(activeAdhocJob.current_video_speed / (1024 * 1024)).toFixed(1)} MB/s
                        </span>
                      </>
                    )}
                    {activeAdhocJob.current_video_eta && activeAdhocJob.current_video_eta > 0 && (
                      <>
                        <span>•</span>
                        <span>ETA: {activeAdhocJob.current_video_eta}s</span>
                      </>
                    )}
                  </p>
                </div>
              </div>

              {/* Action buttons */}
              <div className="flex items-center gap-2 self-end sm:self-auto">
                {onViewJobLogs && (
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => onViewJobLogs(activeAdhocJob.id)}
                    icon={<Terminal className="w-3.5 h-3.5 text-blue-500" />}
                    title="View real-time job log terminal"
                  >
                    View Log
                  </Button>
                )}

                {activeAdhocJob.status === 'completed' && (
                  <a
                    href={`/api/downloads/adhoc/${activeAdhocJob.id}/download`}
                    download
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white shadow-sm transition-colors"
                    title="Direct browser download to your device"
                  >
                    <Download className="w-3.5 h-3.5" />
                    Download File
                  </a>
                )}

                {(activeAdhocJob.status === 'running' || activeAdhocJob.status === 'pending') && (
                  <Button
                    variant="danger"
                    size="sm"
                    onClick={() => handleCancelJob(activeAdhocJob.id)}
                    disabled={cancellingJobId === activeAdhocJob.id}
                    icon={cancellingJobId === activeAdhocJob.id ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <XCircle className="w-3.5 h-3.5" />
                    )}
                  >
                    Cancel
                  </Button>
                )}
              </div>
            </div>

            {/* Live Dual-Tier Progress Bar */}
            <div className="bg-white dark:bg-gray-800 p-3.5 rounded-xl border border-indigo-100 dark:border-indigo-900/50">
              <DualTierProgressBar
                itemCompleted={activeAdhocJob.completed_items || 0}
                itemTotal={activeAdhocJob.total_items || 1}
                itemLabel="Quick Download"
                currentTitle={activeAdhocJob.current_video_title || undefined}
                bytesDownloaded={activeAdhocJob.current_video_bytes_downloaded || undefined}
                bytesTotal={activeAdhocJob.current_video_bytes_total || undefined}
                speed={activeAdhocJob.current_video_speed || undefined}
                eta={activeAdhocJob.current_video_eta || undefined}
                variant="blue"
              />
            </div>

            {activeAdhocJob.error && (
              <div className="p-3 bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 rounded-xl text-xs text-rose-700 dark:text-rose-300">
                <strong>Error:</strong> {activeAdhocJob.error}
              </div>
            )}
          </div>
        )}

        {/* Success Confirmation Toast when no active job is selected */}
        {!activeAdhocJob && successJobId && (
          <div className="p-4 bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-300 dark:border-emerald-700 rounded-xl flex items-center justify-between gap-3">
            <div className="flex items-center gap-2.5 text-xs text-emerald-900 dark:text-emerald-200">
              <CheckCircle2 className="w-5 h-5 text-emerald-500 shrink-0" />
              <div>
                <p className="font-bold text-sm">Download Started (Job #{successJobId})</p>
                <p>Track progress live in the background job queue or Activity Logs tab.</p>
              </div>
            </div>
            {onViewJobLogs && (
              <Button
                variant="secondary"
                size="sm"
                onClick={() => onViewJobLogs(successJobId)}
                icon={<ListOrdered className="w-3.5 h-3.5 text-indigo-500" />}
              >
                View in Queue
              </Button>
            )}
          </div>
        )}

        {/* Unified Ad-Hoc Media Gallery Table */}
        <AdhocMediaViewer
          refreshTrigger={mediaRefreshTrigger}
          onMediaDeleted={() => refetchDirectories()}
        />
      </div>

      {/* Sandboxed Server Directory Browser Modal */}
      <DirectoryPickerModal
        isOpen={isPickerOpen}
        onClose={() => setIsPickerOpen(false)}
        excludeManaged={true}
        onSelect={(path: string) => {
          handleCommitDirectory(path)
          refetchDirectories()
        }}
      />
    </div>
  )
}
