import React, { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { configApi, type Config } from '../../services/api'
import { Modal } from '../ui/Modal'
import { Button } from '../ui/Button'
import { FieldHeader } from './SettingsModal'
import { Sparkles } from 'lucide-react'

export interface InitialSetupModalProps {
  onComplete: () => void
}

export const InitialSetupModal: React.FC<InitialSetupModalProps> = ({ onComplete }) => {
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

  const updateConfig = useMutation({
    mutationFn: (data: Partial<Config>) => configApi.update(data),
    onSuccess: () => {
      alert('Setup complete! You can now start using the app.')
      onComplete()
    },
    onError: (error) => {
      alert(`Setup failed: ${error}`)
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    
    // Validate required fields
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
          Initial Setup
        </span>
      }
      subtitle="Configure your storage and download preferences to get started. You can change these anytime in Settings."
      maxWidth="2xl"
    >
      <form onSubmit={handleSubmit} className="space-y-5">
        {/* Required: Download Path */}
        <div className="border-2 border-blue-500/80 dark:border-blue-400/80 rounded-xl p-4 bg-blue-50/50 dark:bg-blue-900/10">
          <FieldHeader
            label="Main Download Directory"
            required={true}
            infoText="The permanent storage destination for your music and playlists (e.g. your 2TB external HDD mounted at /downloads or E:\Music\Playlists)."
          />
          <input
            type="text"
            value={formData.base_download_path || ''}
            onChange={(e) => setFormData({ ...formData, base_download_path: e.target.value })}
            className="w-full px-3.5 py-2.5 border border-blue-300 dark:border-blue-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white font-medium text-sm focus:ring-2 focus:ring-blue-500"
            placeholder="E:\Music\Playlists or /downloads"
            required
          />
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1.5">
            Playlists will be organized into dedicated subfolders inside this path.
          </p>
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
          >
            Complete Setup & Start
          </Button>
        </div>
      </form>
    </Modal>
  )
}
