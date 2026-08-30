import React, { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { 
  adhocApi, type AdhocProbeResult, type AdhocDownloadParams 
} from '../../services/api'
import { Button } from '../ui/Button'
import { 
  Download, Search, Film, Music, Layers, CheckCircle2, AlertCircle, Loader2, Sparkles, Folder, Clock, Eye 
} from 'lucide-react'

export interface QuickDownloadCardProps {
  onJobStarted?: (jobId: number) => void
}

export const QuickDownloadCard: React.FC<QuickDownloadCardProps> = ({ onJobStarted }) => {
  const queryClient = useQueryClient()
  const [url, setUrl] = useState('')
  const [probeResult, setProbeResult] = useState<AdhocProbeResult | null>(null)
  const [extractMode, setExtractMode] = useState<'video_only' | 'audio_only' | 'both'>('both')
  const [videoQuality, setVideoQuality] = useState<string>('best')
  const [audioFormat, setAudioFormat] = useState<string>('copy')
  const [useCustomPath, setUseCustomPath] = useState(false)
  const [customPath, setCustomPath] = useState('')
  const [successJobId, setSuccessJobId] = useState<number | null>(null)

  // 1. Probe Mutation
  const probeMutation = useMutation({
    mutationFn: (targetUrl: string) => adhocApi.probe(targetUrl),
    onSuccess: (res) => {
      setProbeResult(res.data)
      setSuccessJobId(null)
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
      if (onJobStarted) {
        onJobStarted(res.data.job_id)
      }
    },
  })

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
      custom_download_path: useCustomPath && customPath.trim() ? customPath.trim() : undefined,
    })
  }

  return (
    <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-sm border border-gray-200 dark:border-gray-700 overflow-hidden mb-8">
      {/* Header Banner */}
      <div className="bg-gradient-to-r from-blue-600 via-indigo-600 to-purple-600 p-6 text-white">
        <div className="flex items-center gap-3">
          <div className="p-2.5 bg-white/10 rounded-xl backdrop-blur-sm">
            <Sparkles className="w-6 h-6 text-yellow-300" />
          </div>
          <div>
            <h2 className="text-xl font-bold">Quick / Single Video Downloader</h2>
            <p className="text-xs text-blue-100 mt-0.5">
              Download individual YouTube videos without creating a playlist. Includes format probing, resolution choice, and audio extraction.
            </p>
          </div>
        </div>
      </div>

      <div className="p-6 space-y-6">
        {/* URL Input Form */}
        <form onSubmit={handleProbe} className="space-y-2">
          <label className="text-xs font-bold text-gray-700 dark:text-gray-300 uppercase tracking-wider">
            YouTube Video URL
          </label>
          <div className="flex gap-2">
            <input
              type="text"
              placeholder="https://www.youtube.com/watch?v=... or https://youtu.be/..."
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              className="flex-1 px-4 py-2.5 rounded-xl border border-gray-300 dark:border-gray-600 bg-gray-50 dark:bg-gray-700/50 text-gray-900 dark:text-white text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none"
            />
            <Button
              type="submit"
              variant="primary"
              disabled={!url.trim() || probeMutation.isPending}
              className="px-5 bg-indigo-600 hover:bg-indigo-700 flex items-center gap-2 shrink-0"
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
            </Button>
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
                        {r.label}
                      </option>
                    ))}
                  </select>
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

            {/* Destination Folder Path */}
            <div className="space-y-2 pt-2 border-t border-gray-200 dark:border-gray-700">
              <div className="flex items-center justify-between">
                <label className="text-xs font-semibold text-gray-700 dark:text-gray-300 flex items-center gap-1.5">
                  <Folder className="w-3.5 h-3.5 text-gray-500" />
                  <span>Destination Folder</span>
                </label>
                <label className="flex items-center gap-1.5 text-xs text-gray-600 dark:text-gray-400 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={useCustomPath}
                    onChange={(e) => setUseCustomPath(e.target.checked)}
                    className="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
                  />
                  <span>Custom Folder</span>
                </label>
              </div>

              {useCustomPath ? (
                <input
                  type="text"
                  placeholder="Enter custom folder path (e.g. D:/QuickDownloads)"
                  value={customPath}
                  onChange={(e) => setCustomPath(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-xs bg-white dark:bg-gray-700 text-gray-900 dark:text-white font-mono"
                />
              ) : (
                <div className="px-3 py-2 bg-gray-100 dark:bg-gray-800 rounded-lg text-xs text-gray-600 dark:text-gray-400 font-mono truncate">
                  {probeResult.default_download_path}
                </div>
              )}
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

        {/* Success Confirmation Toast */}
        {successJobId && (
          <div className="p-4 bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-300 dark:border-emerald-700 rounded-xl flex items-center justify-between gap-3">
            <div className="flex items-center gap-2.5 text-xs text-emerald-900 dark:text-emerald-200">
              <CheckCircle2 className="w-5 h-5 text-emerald-500 shrink-0" />
              <div>
                <p className="font-bold text-sm">Download Started (Job #{successJobId})</p>
                <p>Track progress live in the background job queue or Activity Logs tab.</p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
