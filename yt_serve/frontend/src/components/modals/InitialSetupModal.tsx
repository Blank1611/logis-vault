import React, { useState, useEffect } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { configApi, onboardingApi, type Config, type DiscoveredLibraryPreview, type OnboardingResult } from '../../services/api'
import { useToast } from '../../context/ToastContext'
import { Modal } from '../ui/Modal'
import { Button } from '../ui/Button'
import { FieldHeader } from '../ui/FormField'
import { IntervalPicker } from '../ui/IntervalPicker'
import { 
  Sparkles, ArrowRight, Check, FolderCheck, Loader2, Music, Folder,
  ChevronDown, ChevronUp, Settings2, ExternalLink
} from 'lucide-react'

export interface InitialSetupModalProps {
  onComplete: () => void
}

export const InitialSetupModal: React.FC<InitialSetupModalProps> = ({ onComplete }) => {
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const [currentStep, setCurrentStep] = useState<'config' | 'ingestion' | 'summary'>('config')
  const [showAdvanced, setShowAdvanced] = useState(false)

  // Fetch pre-populated config from backend
  const { data: initialConfig } = useQuery({
    queryKey: ['config'],
    queryFn: async () => {
      const res = await configApi.get()
      return res.data
    },
  })

  const [formData, setFormData] = useState<Partial<Config>>({
    base_download_path: '',
    temp_download_path: '',
    audio_extract_mode: 'copy',
    max_extraction_workers: 4,
    batch_size: 200,
    use_browser_cookies: false,
    browser_name: 'chrome',
    cookies_file: null,
    enable_auto_discovery: true,
    auto_discovery_interval_minutes: 1440,
    adhoc_download_path: '',
    use_custom_adhoc_path: false,
    flaresolverr_url: '',
  })

  // Pre-fill state as soon as backend returns discovered .env config
  useEffect(() => {
    if (initialConfig) {
      setFormData(prev => ({
        ...prev,
        base_download_path: initialConfig.base_download_path || prev.base_download_path || '',
        temp_download_path: initialConfig.temp_download_path || prev.temp_download_path || '',
        audio_extract_mode: initialConfig.audio_extract_mode || prev.audio_extract_mode || 'copy',
        max_extraction_workers: initialConfig.max_extraction_workers || prev.max_extraction_workers || 4,
        batch_size: initialConfig.batch_size || prev.batch_size || 200,
        enable_auto_discovery: initialConfig.enable_auto_discovery ?? prev.enable_auto_discovery ?? true,
        auto_discovery_interval_minutes: initialConfig.auto_discovery_interval_minutes ?? prev.auto_discovery_interval_minutes ?? 1440,
        adhoc_download_path: initialConfig.adhoc_download_path || prev.adhoc_download_path || '',
        use_custom_adhoc_path: initialConfig.use_custom_adhoc_path ?? prev.use_custom_adhoc_path ?? false,
        flaresolverr_url: initialConfig.flaresolverr_url || prev.flaresolverr_url || '',
      }))
    }
  }, [initialConfig])

  // Ingestion state
  const [ingestionState, setIngestionState] = useState<{
    status: 'idle' | 'scanning' | 'ingesting' | 'completed' | 'error'
    discovered: DiscoveredLibraryPreview | null
    result: OnboardingResult | null
    progressPercent: number
    currentPlaylistTitle: string
    error?: string
  }>({
    status: 'idle',
    discovered: null,
    result: null,
    progressPercent: 0,
    currentPlaylistTitle: '',
  })

  const runDiscoveryAndIngestion = async (configPayload: Partial<Config>) => {
    setCurrentStep('ingestion')
    setIngestionState(prev => ({ ...prev, status: 'scanning', progressPercent: 20 }))

    try {
      // 1. Save config with setup_completed=true
      await configApi.update({ ...configPayload, setup_completed: true })
      setIngestionState(prev => ({ ...prev, progressPercent: 40 }))

      // 2. Scan directory
      const scanRes = await onboardingApi.scan(configPayload.base_download_path)
      const scanData = scanRes.data
      setIngestionState(prev => ({
        ...prev,
        discovered: scanData,
        status: 'ingesting',
        progressPercent: 60,
      }))

      // 3. Confirm ingestion if playlists discovered
      let confirmData: OnboardingResult | null = null
      if (scanData.discovered_playlists.length > 0) {
        setIngestionState(prev => ({
          ...prev,
          currentPlaylistTitle: scanData.discovered_playlists[0]?.title || '',
          progressPercent: 80,
        }))
        const confirmRes = await onboardingApi.confirm({
          base_path: configPayload.base_download_path,
          items: scanData.discovered_playlists,
        })
        confirmData = confirmRes.data
      }

      setIngestionState(prev => ({
        ...prev,
        result: confirmData,
        status: 'completed',
        progressPercent: 100,
      }))

      // Invalidate queries so dashboard reflects newly added data
      queryClient.invalidateQueries({ queryKey: ['config'] })
      queryClient.invalidateQueries({ queryKey: ['playlists'] })
      queryClient.invalidateQueries({ queryKey: ['track-index'] })

      // Industry-standard transition to Step 3 Summary screen (no asynchronous auto-close timer)
      setCurrentStep('summary')
    } catch (err: any) {
      setIngestionState(prev => ({
        ...prev,
        status: 'error',
        error: err?.message || 'Failed to complete discovery and ingestion.',
      }))
    }
  }

  const handleConfigSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!formData.base_download_path?.trim()) {
      toast.info('Please enter a valid main download directory')
      return
    }
    runDiscoveryAndIngestion(formData)
  }

  return (
    <Modal
      isOpen={true}
      onClose={() => {}}
      title={
        <span className="flex items-center gap-2">
          <Sparkles className="w-6 h-6 text-blue-600 dark:text-blue-400" />
          {currentStep === 'config' ? 'Initial Setup & Configuration' : 'Auto-Discovery & Library Ingestion'}
        </span>
      }
      subtitle={
        currentStep === 'config'
          ? 'Review your storage settings pre-populated from your environment. You can change these anytime in Settings.'
          : 'Scanning your download directory and populating your SQLite database and track index...'
      }
      maxWidth="3xl"
    >
      {currentStep === 'config' ? (
        <form onSubmit={handleConfigSubmit} className="space-y-5">
          {/* Step Indicator */}
          <div className="flex items-center justify-between text-xs font-semibold text-gray-500 pb-2 border-b border-gray-100 dark:border-gray-700">
            <span className="text-blue-600 dark:text-blue-400 font-bold flex items-center gap-1.5">
              <span className="w-5 h-5 rounded-full bg-blue-600 text-white flex items-center justify-center text-[10px]">1</span>
              Configuration Review
            </span>
            <span className="flex items-center gap-1.5 text-gray-400">
              <span className="w-5 h-5 rounded-full bg-gray-200 dark:bg-gray-700 text-gray-600 dark:text-gray-300 flex items-center justify-center text-[10px]">2</span>
              Library Auto-Discovery
            </span>
          </div>

          {/* Required: Download Path */}
          <div className="border-2 border-blue-500/80 dark:border-blue-400/80 rounded-xl p-4 bg-blue-50/50 dark:bg-blue-900/10 space-y-2">
            <FieldHeader
              label="Main Download Directory"
              required={true}
              infoText="The permanent storage destination for your music and playlists (e.g. E:\Music\Playlists or /downloads)."
              id="base_download_path"
            />
            <input
              id="base_download_path"
              type="text"
              value={formData.base_download_path || ''}
              onChange={(e) => setFormData({ ...formData, base_download_path: e.target.value })}
              className="w-full px-3.5 py-2.5 border border-blue-300 dark:border-blue-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white font-medium text-sm focus:ring-2 focus:ring-blue-500"
              placeholder="E:\Music\Playlists or /downloads"
              required
            />
            <p className="text-xs text-gray-500 dark:text-gray-400">
              Playlists will be organized into dedicated subfolders inside this path.
            </p>
          </div>

          {/* Optional: Temp Directory */}
          <div>
            <FieldHeader
              label="Temp Working Directory (Optional)"
              recommended="Fast SSD Buffer"
              infoText="If specified, active chunk downloads and FFmpeg audio transcoding occur on this fast SSD drive before moving to your main storage."
              id="temp_download_path"
            />
            <input
              id="temp_download_path"
              type="text"
              value={formData.temp_download_path || ''}
              onChange={(e) => setFormData({ ...formData, temp_download_path: e.target.value })}
              className="w-full px-3.5 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm"
              placeholder="e.g. C:\temp\yt_downloads or /tmp/yt_downloads"
            />
          </div>

          {/* Audio Extract Mode & Concurrency Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <FieldHeader
                label="Audio Extraction Format"
                recommended="Recommended: Direct Stream Copy"
                infoText="Choose whether to extract original audio tracks without transcoding (lossless, instant) or transcode to MP3."
                id="audio_extract_mode"
              />
              <select
                id="audio_extract_mode"
                value={formData.audio_extract_mode || 'copy'}
                onChange={(e) => setFormData({ ...formData, audio_extract_mode: e.target.value })}
                className="w-full px-3.5 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm"
              >
                <option value="copy">Direct Stream Copy (Fastest, Lossless original)</option>
                <option value="mp3_best">MP3 Best Quality (VBR ~250–320 kbps)</option>
                <option value="mp3_high">MP3 High Quality (VBR ~190–250 kbps)</option>
                <option value="opus">Opus (128 kbps)</option>
              </select>
            </div>

            <div>
              <FieldHeader
                label="Extraction Worker Threads"
                recommended="Recommended: 4 Threads"
                infoText="Number of parallel audio extraction threads to run simultaneously."
                id="max_extraction_workers"
              />
              <input
                id="max_extraction_workers"
                type="number"
                min="1"
                max="16"
                value={formData.max_extraction_workers || 4}
                onChange={(e) => setFormData({ ...formData, max_extraction_workers: parseInt(e.target.value, 10) || 4 })}
                className="w-full px-3.5 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm"
              />
            </div>
          </div>

          {/* Collapsible Advanced Configuration */}
          <div className="border border-gray-200 dark:border-gray-700 rounded-xl overflow-hidden bg-gray-50/50 dark:bg-gray-800/40">
            <button
              type="button"
              onClick={() => setShowAdvanced(!showAdvanced)}
              className="w-full px-4 py-3 flex items-center justify-between text-left text-xs font-semibold text-gray-700 dark:text-gray-300 hover:bg-gray-100/60 dark:hover:bg-gray-800 transition-colors"
            >
              <div className="flex items-center gap-2">
                <Settings2 className="w-4 h-4 text-blue-500" />
                <span>Advanced Configuration (Optional)</span>
                <span className="text-[11px] text-gray-500 dark:text-gray-400 font-normal">
                  — Ad-Hoc folders, FlareSolverr, Auto-Discovery interval
                </span>
              </div>
              {showAdvanced ? (
                <ChevronUp className="w-4 h-4 text-gray-500" />
              ) : (
                <ChevronDown className="w-4 h-4 text-gray-500" />
              )}
            </button>

            {showAdvanced && (
              <div className="p-4 pt-2 space-y-4 border-t border-gray-200 dark:border-gray-700 animate-in fade-in duration-150">
                {/* Custom Ad-Hoc Downloads Path */}
                <div>
                  <FieldHeader
                    label="Custom Ad-Hoc Downloads Directory"
                    infoText="Directory for standalone single-video downloads outside of playlists. Leave empty to use default _adhoc_downloads folder."
                    id="adhoc_download_path"
                  />
                  <input
                    id="adhoc_download_path"
                    type="text"
                    value={formData.adhoc_download_path || ''}
                    onChange={(e) => setFormData({
                      ...formData,
                      adhoc_download_path: e.target.value,
                      use_custom_adhoc_path: Boolean(e.target.value.trim())
                    })}
                    className="w-full px-3.5 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm"
                    placeholder="e.g. /downloads/_singles or E:\Music\Singles"
                  />
                </div>

                {/* FlareSolverr Proxy */}
                <div>
                  <FieldHeader
                    label="FlareSolverr Proxy URL"
                    infoText="Optional FlareSolverr endpoint if running behind Cloudflare challenge solvers (e.g. http://flaresolverr:8191/v1)."
                    id="flaresolverr_url"
                  />
                  <input
                    id="flaresolverr_url"
                    type="text"
                    value={formData.flaresolverr_url || ''}
                    onChange={(e) => setFormData({ ...formData, flaresolverr_url: e.target.value })}
                    className="w-full px-3.5 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm font-mono"
                    placeholder="http://flaresolverr:8191/v1"
                  />
                </div>

                {/* Auto-Discovery Interval */}
                <div>
                  <FieldHeader
                    label="Background Auto-Discovery Cadence"
                    infoText="How frequently the background worker scans your download directory for new subfolders."
                  />
                  <IntervalPicker
                    valueMinutes={formData.auto_discovery_interval_minutes ?? 1440}
                    onChange={(mins) => setFormData({ ...formData, auto_discovery_interval_minutes: mins })}
                    minMinutes={5}
                  />
                </div>
              </div>
            )}
          </div>

          <div className="pt-3">
            <Button
              type="submit"
              disabled={!formData.base_download_path?.trim()}
              className="w-full py-2.5 text-base flex items-center justify-center gap-2"
            >
              <span>Save & Continue to Auto-Discovery</span>
              <ArrowRight className="w-4 h-4" />
            </Button>
          </div>
        </form>
      ) : currentStep === 'ingestion' ? (
        /* Step 2: Live Ingestion & Visual Progress Screen */
        <div className="space-y-6 py-4">
          {/* Step Indicator */}
          <div className="flex items-center justify-between text-xs font-semibold text-gray-500 pb-2 border-b border-gray-100 dark:border-gray-700">
            <span className="text-emerald-600 dark:text-emerald-400 font-bold flex items-center gap-1.5">
              <Check className="w-4 h-4" />
              1. Configuration Saved
            </span>
            <span className="text-blue-600 dark:text-blue-400 font-bold flex items-center gap-1.5">
              <span className="w-5 h-5 rounded-full bg-blue-600 text-white flex items-center justify-center text-[10px]">2</span>
              Library Auto-Discovery
            </span>
            <span className="text-gray-400 flex items-center gap-1.5">
              <span className="w-5 h-5 rounded-full bg-gray-200 dark:bg-gray-700 text-gray-600 dark:text-gray-400 flex items-center justify-center text-[10px]">3</span>
              Summary
            </span>
          </div>

          {/* Animated Progress Bar */}
          <div className="space-y-2">
            <div className="flex justify-between text-xs font-bold text-gray-700 dark:text-gray-300">
              <span className="flex items-center gap-1.5">
                <Loader2 className="w-4 h-4 animate-spin text-blue-500" />
                {ingestionState.status === 'scanning' && 'Scanning download directory...'}
                {ingestionState.status === 'ingesting' && 'Populating SQLite database & track index...'}
                {ingestionState.status === 'error' && 'Error during ingestion'}
              </span>
              <span className="font-mono">{ingestionState.progressPercent}%</span>
            </div>

            <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-3 overflow-hidden">
              <div
                className="bg-gradient-to-r from-blue-600 to-indigo-600 h-3 rounded-full transition-all duration-500 ease-out"
                style={{ width: `${ingestionState.progressPercent}%` }}
              />
            </div>
          </div>

          {/* Error Message */}
          {ingestionState.status === 'error' && (
            <div className="p-4 bg-rose-50 dark:bg-rose-950/40 border border-rose-300 dark:border-rose-700 rounded-xl text-center space-y-2">
              <p className="text-xs font-semibold text-rose-700 dark:text-rose-300">
                {ingestionState.error}
              </p>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setCurrentStep('config')}
              >
                Back to Configuration
              </Button>
            </div>
          )}
        </div>
      ) : (
        /* Step 3: Industry-Standard Setup Complete & Summary Screen (No Auto-Dismissal) */
        <div className="space-y-6 py-4 animate-in fade-in duration-200">
          {/* Step Indicator */}
          <div className="flex items-center justify-between text-xs font-semibold pb-2 border-b border-gray-100 dark:border-gray-700">
            <span className="text-emerald-600 dark:text-emerald-400 font-bold flex items-center gap-1.5">
              <Check className="w-4 h-4" />
              1. Configuration
            </span>
            <span className="text-emerald-600 dark:text-emerald-400 font-bold flex items-center gap-1.5">
              <Check className="w-4 h-4" />
              2. Discovery Complete
            </span>
            <span className="text-blue-600 dark:text-blue-400 font-bold flex items-center gap-1.5">
              <span className="w-5 h-5 rounded-full bg-blue-600 text-white flex items-center justify-center text-[10px]">3</span>
              Library Summary
            </span>
          </div>

          {/* Success Banner */}
          <div className="p-5 bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-300 dark:border-emerald-700 rounded-2xl text-center space-y-2">
            <div className="w-12 h-12 rounded-full bg-emerald-100 dark:bg-emerald-900/60 flex items-center justify-center mx-auto text-emerald-600 dark:text-emerald-400">
              <Check className="w-7 h-7" />
            </div>
            <h3 className="text-lg font-bold text-emerald-900 dark:text-emerald-200">
              Initial Setup & Discovery Complete!
            </h3>
            <p className="text-xs text-emerald-700 dark:text-emerald-400 max-w-md mx-auto">
              Your server configuration has been saved and your download directory has been indexed.
            </p>
          </div>

          {/* Discovered Library Cards */}
          <div className="space-y-3">
            {ingestionState.discovered && ingestionState.discovered.discovered_playlists.length > 0 ? (
              <div className="border border-gray-200 dark:border-gray-700 rounded-xl p-4 bg-gray-50 dark:bg-gray-800/60 space-y-3">
                <div className="flex items-center justify-between text-xs font-bold text-gray-700 dark:text-gray-300">
                  <span className="flex items-center gap-1.5 text-blue-600 dark:text-blue-400">
                    <FolderCheck className="w-4 h-4" />
                    Imported {ingestionState.discovered.discovered_playlists.length} Managed Playlists
                  </span>
                  <span className="text-[11px] text-gray-500 font-mono">
                    {ingestionState.result?.tracks_indexed ?? ingestionState.discovered.total_estimated_tracks} tracks indexed
                  </span>
                </div>

                <div className="max-h-40 overflow-y-auto space-y-1.5 divide-y divide-gray-200 dark:divide-gray-700/60 pr-1">
                  {ingestionState.discovered.discovered_playlists.map((pl, idx) => (
                    <div key={idx} className="pt-1.5 flex items-center justify-between text-xs text-gray-800 dark:text-gray-200">
                      <span className="font-semibold truncate max-w-sm flex items-center gap-2">
                        <Music className="w-3.5 h-3.5 text-blue-500 shrink-0" />
                        {pl.title}
                      </span>
                      <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-blue-100 dark:bg-blue-900/50 text-blue-800 dark:text-blue-300 font-mono">
                        {pl.video_count || pl.audio_count || pl.archived_count} tracks
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="p-4 bg-gray-100 dark:bg-gray-800/60 border border-gray-200 dark:border-gray-700 rounded-xl text-center text-xs text-gray-600 dark:text-gray-400">
                0 existing managed playlists found in this directory. You can add new playlists anytime via the top bar.
              </div>
            )}

            {/* Unmanaged Folders Alert Card */}
            {ingestionState.discovered && ingestionState.discovered.unmanaged_folders && ingestionState.discovered.unmanaged_folders.length > 0 && (
              <div className="border border-amber-200 dark:border-amber-800/80 rounded-xl p-4 bg-amber-50/70 dark:bg-amber-950/40 space-y-2">
                <div className="flex items-center gap-2 text-xs font-bold text-amber-900 dark:text-amber-300">
                  <Folder className="w-4 h-4 text-amber-500 shrink-0" />
                  <span>
                    Detected {ingestionState.discovered.unmanaged_folders.length} Unmanaged Folder(s)
                  </span>
                </div>
                <p className="text-xs text-amber-800 dark:text-amber-400 leading-relaxed">
                  These folders do not have a <code>playlist_info.json</code> file yet. They were safely indexed as unmanaged folders so you can easily link them to YouTube playlists without redownloading tracks.
                </p>
                <div className="flex flex-wrap gap-2 pt-1">
                  {ingestionState.discovered.unmanaged_folders.map((f, i) => (
                    <span
                      key={i}
                      className="px-2.5 py-1 rounded-lg text-xs font-mono font-semibold bg-amber-100 dark:bg-amber-900/60 text-amber-900 dark:text-amber-200 border border-amber-300 dark:border-amber-800"
                    >
                      📁 {f.folder_name} ({f.total_files} files)
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Explicit User Actions */}
          <div className="pt-4 border-t border-gray-200 dark:border-gray-700 flex flex-col sm:flex-row items-center justify-end gap-3">
            <Button
              type="button"
              variant="secondary"
              onClick={() => {
                onComplete()
                window.location.href = '/settings?tab=storage'
              }}
              className="w-full sm:w-auto text-xs py-2.5 flex items-center justify-center gap-1.5"
            >
              <ExternalLink className="w-3.5 h-3.5" />
              <span>Manage Folders in Storage Settings</span>
            </Button>
            <Button
              type="button"
              onClick={onComplete}
              className="w-full sm:w-auto text-xs py-2.5 flex items-center justify-center gap-1.5 shadow-lg shadow-blue-600/30"
            >
              <span>Finish & Open Dashboard</span>
              <ArrowRight className="w-4 h-4" />
            </Button>
          </div>
        </div>
      )}
    </Modal>
  )
}

