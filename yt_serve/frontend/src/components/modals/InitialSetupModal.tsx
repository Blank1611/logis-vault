import React, { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { configApi, onboardingApi, type Config, type DiscoveredLibraryPreview } from '../../services/api'
import { Modal } from '../ui/Modal'
import { Button } from '../ui/Button'
import { FieldHeader } from './SettingsModal'
import { Sparkles, Search, Check, FolderCheck, Music } from 'lucide-react'

export interface InitialSetupModalProps {
  onComplete: () => void
}

export const InitialSetupModal: React.FC<InitialSetupModalProps> = ({ onComplete }) => {
  const queryClient = useQueryClient()
  const [formData, setFormData] = useState<Partial<Config>>({
    base_download_path: '',
    temp_download_path: '',
    audio_extract_mode: 'copy',
    max_extraction_workers: 4,
    batch_size: 200,
    use_browser_cookies: false,
    browser_name: 'chrome',
    cookies_file: null,
  })

  const [scanResult, setScanResult] = useState<DiscoveredLibraryPreview | null>(null)

  const scanMutation = useMutation({
    mutationFn: (path?: string) => onboardingApi.scan(path),
    onSuccess: (res) => {
      setScanResult(res.data)
    },
  })

  const updateConfig = useMutation({
    mutationFn: async (data: Partial<Config>) => {
      await configApi.update(data)
      if (scanResult && scanResult.discovered_playlists.length > 0) {
        await onboardingApi.confirm({ base_path: data.base_download_path, items: scanResult.discovered_playlists })
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['playlists'] })
      queryClient.invalidateQueries({ queryKey: ['track-index'] })
      onComplete()
    },
    onError: (error) => {
      alert(`Setup failed: ${error}`)
    },
  })

  const handleScan = () => {
    if (!formData.base_download_path?.trim()) {
      alert('Please enter a download directory path first')
      return
    }
    scanMutation.mutate(formData.base_download_path)
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!formData.base_download_path?.trim()) {
      alert('Please enter a download directory path')
      return
    }
    updateConfig.mutate(formData)
  }

  return (
    <Modal
      isOpen={true}
      onClose={() => {}}
      title={
        <span className="flex items-center gap-2">
          <Sparkles className="w-6 h-6 text-blue-600 dark:text-blue-400" />
          Welcome to Playlist Manager Setup
        </span>
      }
      subtitle="Configure your storage preferences or auto-discover existing music libraries on your drive in seconds."
      maxWidth="2xl"
    >
      <form onSubmit={handleSubmit} className="space-y-5">
        {/* Required: Download Path */}
        <div className="border-2 border-blue-500/80 dark:border-blue-400/80 rounded-xl p-4 bg-blue-50/50 dark:bg-blue-900/10 space-y-3">
          <FieldHeader
            label="Main Download Directory"
            required={true}
            infoText="The permanent storage destination for your music and playlists (e.g. E:\Music\Playlists or /downloads)."
          />
          <div className="flex gap-2">
            <input
              type="text"
              value={formData.base_download_path || ''}
              onChange={(e) => {
                setFormData({ ...formData, base_download_path: e.target.value })
                setScanResult(null)
              }}
              className="flex-1 px-3.5 py-2.5 border border-blue-300 dark:border-blue-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white font-medium text-sm focus:ring-2 focus:ring-blue-500"
              placeholder="E:\Music\Playlists or /downloads"
              required
            />
            <Button
              type="button"
              variant="secondary"
              size="sm"
              loading={scanMutation.isPending}
              disabled={!formData.base_download_path?.trim()}
              onClick={handleScan}
              icon={<Search className="w-4 h-4" />}
            >
              Scan Library
            </Button>
          </div>

          {/* Auto-Discovery Preview Banner */}
          {scanResult && (
            <div className="pt-2">
              {scanResult.discovered_playlists.length > 0 ? (
                <div className="p-3 bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-300 dark:border-emerald-700 rounded-lg text-xs space-y-2">
                  <div className="flex items-center gap-1.5 text-emerald-800 dark:text-emerald-300 font-bold">
                    <FolderCheck className="w-4 h-4" />
                    <span>
                      Discovered {scanResult.discovered_playlists.length} existing playlists ({scanResult.total_estimated_tracks} tracks)
                    </span>
                  </div>
                  <div className="max-h-32 overflow-y-auto space-y-1 divide-y divide-emerald-200 dark:divide-emerald-800/60 pt-1">
                    {scanResult.discovered_playlists.map((pl, idx) => (
                      <div key={idx} className="pt-1 flex items-center justify-between text-gray-700 dark:text-gray-300">
                        <span className="font-semibold truncate max-w-xs flex items-center gap-1">
                          <Music className="w-3 h-3 text-emerald-600" />
                          {pl.title}
                        </span>
                        <span className="text-gray-500 font-mono text-[11px]">
                          {pl.video_count || pl.audio_count || pl.archived_count} tracks
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="p-2.5 bg-gray-100 dark:bg-gray-800 rounded-lg text-xs text-gray-600 dark:text-gray-400">
                  Folder is empty or clean. New playlists created in the app will be saved here.
                </div>
              )}
            </div>
          )}
        </div>

        {/* Optional: Temp Directory */}
        <div>
          <FieldHeader
            label="Temp Working Directory (Optional)"
            recommended="Fast SSD Buffer"
            infoText="If specified, active chunk downloads and FFmpeg audio transcoding occur on this fast SSD drive before moving to your main storage."
          />
          <input
            type="text"
            value={formData.temp_download_path || ''}
            onChange={(e) => setFormData({ ...formData, temp_download_path: e.target.value })}
            className="w-full px-3.5 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm"
            placeholder="e.g. C:\temp\yt_downloads or /tmp/yt_downloads"
          />
        </div>

        {/* Audio Extract Mode */}
        <div>
          <FieldHeader
            label="Audio Extraction Format"
            recommended="Recommended: Direct Stream Copy"
            infoText="Choose whether to extract original audio tracks without transcoding (lossless, instant) or transcode to MP3."
          />
          <select
            value={formData.audio_extract_mode || 'copy'}
            onChange={(e) => setFormData({ ...formData, audio_extract_mode: e.target.value })}
            className="w-full px-3.5 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm"
          >
            <option value="copy">Direct Stream Copy (Fastest, Lossless original M4A/Opus)</option>
            <option value="mp3_best">MP3 Best Quality (VBR ~250–320 kbps)</option>
            <option value="mp3_high">MP3 High Quality (VBR ~190–250 kbps)</option>
            <option value="opus">Opus (128 kbps)</option>
          </select>
        </div>

        <div className="pt-2">
          <Button
            type="submit"
            loading={updateConfig.isPending}
            disabled={!formData.base_download_path?.trim()}
            className="w-full py-2.5 text-base"
            icon={scanResult?.discovered_playlists.length ? <FolderCheck className="w-5 h-5" /> : <Check className="w-5 h-5" />}
          >
            {scanResult && scanResult.discovered_playlists.length > 0
              ? `Import ${scanResult.discovered_playlists.length} Playlists & Start`
              : 'Complete Setup & Start'}
          </Button>
        </div>
      </form>
    </Modal>
  )
}
