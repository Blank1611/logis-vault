import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { profilesApi } from '../../services/api'
import type { QualityProfile } from '../../services/types'
import { Modal } from '../ui/Modal'
import { useToast } from '../../context/ToastContext'
import { 
  Sliders, 
  Plus, 
  Trash2, 
  Edit3, 
  Sparkles, 
  Music, 
  CheckCircle2, 
  Loader2 
} from 'lucide-react'

const DEFAULT_PRESET_PROFILES: QualityProfile[] = [
  {
    id: 'ultra_4k',
    name: 'Ultra 4K',
    description: '4K Ultra HD resolution with highest available audio quality',
    max_resolution: 2160,
    audio_format: 'copy',
    cipher_strategy: 'web_decipher',
    is_audio_only: false,
    is_builtin: true,
  },
  {
    id: 'qhd_1440p',
    name: 'Quad HD 1440p',
    description: '2K Quad HD resolution with highest available audio quality',
    max_resolution: 1440,
    audio_format: 'copy',
    cipher_strategy: 'web_decipher',
    is_audio_only: false,
    is_builtin: true,
  },
  {
    id: 'standard_1080p',
    name: 'Standard HD 1080p',
    description: '1080p Full HD resolution with highest available audio quality',
    max_resolution: 1080,
    audio_format: 'copy',
    cipher_strategy: 'web_decipher',
    is_audio_only: false,
    is_builtin: true,
  },
  {
    id: 'standard_720p',
    name: 'Standard HD 720p',
    description: '720p HD resolution with high quality audio and balanced file sizes',
    max_resolution: 720,
    audio_format: 'copy',
    cipher_strategy: 'web_decipher',
    is_audio_only: false,
    is_builtin: true,
  },
  {
    id: 'fast_mixtape_360p',
    name: 'Fast / Mixtape 360p (Challenge-Free)',
    description: '360p progressive stream, zero JS challenge deciphering, ideal for long background mixtapes',
    max_resolution: 360,
    audio_format: 'copy',
    cipher_strategy: 'direct_format18',
    is_audio_only: false,
    is_builtin: true,
  },
  {
    id: 'audio_only',
    name: 'Audio Only Vault',
    description: 'Direct audio stream extraction, no video file stored on disk',
    max_resolution: 0,
    audio_format: 'copy',
    cipher_strategy: 'web_decipher',
    is_audio_only: true,
    is_builtin: true,
  },
]

export interface QualityProfilesManagerProps {
  initialProfiles?: QualityProfile[]
}

export const QualityProfilesManager: React.FC<QualityProfilesManagerProps> = ({ initialProfiles }) => {
  const queryClient = useQueryClient()
  const { toast } = useToast()

  const [modalOpen, setModalOpen] = useState(false)
  const [editingProfile, setEditingProfile] = useState<QualityProfile | null>(null)

  // Form state for creating / editing
  const [name, setName] = useState('')
  const [maxResolution, setMaxResolution] = useState(1080)
  const [audioFormat, setAudioFormat] = useState('copy')
  const [isAudioOnly, setIsAudioOnly] = useState(false)
  const [description, setDescription] = useState('')

  // Query profiles with cache & fallback
  const { data: rawProfiles = initialProfiles || [], isLoading } = useQuery({
    queryKey: ['profiles'],
    queryFn: async () => {
      const res = await profilesApi.getAll()
      return res.data
    },
    staleTime: 5 * 60 * 1000,
    retry: 1,
    initialData: initialProfiles,
  })

  // Ensure profiles array falls back to DEFAULT_PRESET_PROFILES if empty
  const profiles = rawProfiles && rawProfiles.length > 0 ? rawProfiles : DEFAULT_PRESET_PROFILES

  // Create mutation
  const createMutation = useMutation({
    mutationFn: (data: Partial<QualityProfile>) => profilesApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['profiles'] })
      toast.success('Custom profile created successfully!')
      handleCloseModal()
    },
    onError: (err: any) => {
      const msg = err.response?.data?.detail || err.message
      toast.error(`Failed to create profile: ${msg}`)
    },
  })

  // Update mutation
  const updateMutation = useMutation({
    mutationFn: ({ profileId, data }: { profileId: string; data: Partial<QualityProfile> }) =>
      profilesApi.update(profileId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['profiles'] })
      toast.success('Custom profile updated successfully!')
      handleCloseModal()
    },
    onError: (err: any) => {
      const msg = err.response?.data?.detail || err.message
      toast.error(`Failed to update profile: ${msg}`)
    },
  })

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: (profileId: string) => profilesApi.delete(profileId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['profiles'] })
      toast.success('Profile deleted')
    },
    onError: (err: any) => {
      const msg = err.response?.data?.detail || err.message
      toast.error(`Failed to delete profile: ${msg}`)
    },
  })

  const handleOpenCreate = () => {
    setEditingProfile(null)
    setName('')
    setMaxResolution(1440)
    setAudioFormat('copy')
    setIsAudioOnly(false)
    setDescription('')
    setModalOpen(true)
  }

  const handleOpenEdit = (profile: QualityProfile) => {
    setEditingProfile(profile)
    setName(profile.name)
    setMaxResolution(profile.max_resolution)
    setAudioFormat(profile.audio_format || 'copy')
    setIsAudioOnly(Boolean(profile.is_audio_only))
    setDescription(profile.description || '')
    setModalOpen(true)
  }

  const handleCloseModal = () => {
    setModalOpen(false)
    setEditingProfile(null)
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const payload = {
      name: name.trim(),
      max_resolution: isAudioOnly ? 0 : Number(maxResolution),
      audio_format: audioFormat,
      is_audio_only: isAudioOnly,
      description: description.trim(),
      cipher_strategy: 'challenge_solver',
    }

    if (editingProfile) {
      updateMutation.mutate({ profileId: editingProfile.id, data: payload })
    } else {
      createMutation.mutate(payload)
    }
  }

  return (
    <div className="space-y-6">
      {/* Header Bar */}
      <div className="glass-panel p-6 rounded-2xl border border-white/10 shadow-xl flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h3 className="text-xl font-bold text-white flex items-center gap-2.5">
            <Sliders className="w-5 h-5 text-cyan-400" />
            <span>Quality Profiles Manager</span>
          </h3>
          <p className="text-xs text-slate-400 mt-1 max-w-xl">
            Configure preset and custom transcoding targets (4K, 1440p, 1080p, Audio Only). Playlists inherit these rules to govern video resolution and audio containers.
          </p>
        </div>

        <button
          onClick={handleOpenCreate}
          className="glass-btn-cyan px-4 py-2.5 rounded-xl text-xs font-bold flex items-center gap-2 cursor-pointer shadow-lg"
        >
          <Plus className="w-4 h-4" />
          <span>Create Custom Profile</span>
        </button>
      </div>

      {/* Profiles Grid */}
      {isLoading && profiles.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-slate-400 gap-3">
          <Loader2 className="w-8 h-8 animate-spin text-cyan-400" />
          <p className="text-sm font-medium">Loading quality profiles...</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {profiles.map((p: QualityProfile) => {
            const isBuiltin = p.is_builtin
            const is4k = p.max_resolution >= 2160
            const is1440p = p.max_resolution === 1440

            return (
              <div
                key={p.id}
                className="glass-panel rounded-2xl p-5 border border-white/10 hover:border-cyan-500/40 transition-all flex flex-col justify-between shadow-lg group"
              >
                <div>
                  {/* Top Badges */}
                  <div className="flex items-center justify-between gap-2 mb-3">
                    <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-extrabold uppercase tracking-wider border ${
                      isBuiltin
                        ? 'bg-slate-800/80 text-slate-300 border-white/10'
                        : 'bg-cyan-500/15 text-cyan-300 border-cyan-500/40 shadow-xs shadow-cyan-500/30'
                    }`}>
                      {isBuiltin ? 'Preset' : 'Custom'}
                    </span>

                    {/* Resolution Jewel Pill */}
                    <span className={`px-2.5 py-0.5 rounded-full text-[11px] font-bold border ${
                      p.is_audio_only
                        ? 'glass-pill-emerald'
                        : is4k
                        ? 'glass-pill-rose font-mono'
                        : is1440p
                        ? 'glass-pill-blue font-mono'
                        : 'glass-pill-blue font-mono'
                    }`}>
                      {p.is_audio_only ? 'Audio Only' : `${p.max_resolution}p`}
                    </span>
                  </div>

                  {/* Profile Title */}
                  <h4 className="text-base font-bold text-white group-hover:text-cyan-300 transition-colors">
                    {p.name}
                  </h4>

                  {/* Description */}
                  <p className="text-xs text-slate-400 mt-2 line-clamp-2 min-h-[32px]">
                    {p.description || `Target resolution up to ${p.max_resolution}p with ${p.audio_format || 'copy'} audio.`}
                  </p>

                  {/* Attributes Badges */}
                  <div className="flex flex-wrap gap-1.5 mt-4">
                    <span
                      className="px-2 py-0.5 rounded-md text-[10px] font-medium bg-slate-900/80 text-slate-300 border border-white/10 flex items-center gap-1 cursor-help"
                      title="Extracts YouTube's native audio stream (AAC or Opus) instantaneously without re-encoding"
                    >
                      <Music className="w-2.5 h-2.5 text-cyan-400" />
                      {p.audio_format === 'copy' ? 'Direct Copy' : p.audio_format.toUpperCase()}
                    </span>

                    {!p.is_audio_only && (
                      <span
                        className="px-2 py-0.5 rounded-md text-[10px] font-medium bg-slate-900/80 text-emerald-300 border border-emerald-500/30 flex items-center gap-1 cursor-help"
                        title="Resolution Ceiling: If the target resolution is not available for a video, automatically falls back to the highest available resolution without failing"
                      >
                        <CheckCircle2 className="w-2.5 h-2.5" />
                        Downscale Fallback
                      </span>
                    )}
                  </div>
                </div>

                {/* Footer Actions */}
                <div className="mt-5 pt-3 border-t border-white/10 flex items-center justify-between text-xs">
                  <span className={`text-[10px] font-semibold ${isBuiltin ? 'text-slate-500' : 'text-cyan-400'}`}>
                    {isBuiltin ? 'System Preset' : 'Custom Profile'}
                  </span>

                  {!isBuiltin && (
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => handleOpenEdit(p)}
                        className="p-1.5 rounded-lg text-slate-400 hover:text-cyan-300 hover:bg-white/5 transition-colors"
                        title="Edit profile"
                      >
                        <Edit3 className="w-3.5 h-3.5" />
                      </button>
                      <button
                        onClick={() => {
                          if (confirm(`Delete custom profile "${p.name}"?`)) {
                            deleteMutation.mutate(p.id)
                          }
                        }}
                        className="p-1.5 rounded-lg text-slate-400 hover:text-rose-400 hover:bg-white/5 transition-colors"
                        title="Delete profile"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Create / Edit Modal */}
      {modalOpen && (
        <Modal
          isOpen={true}
          onClose={handleCloseModal}
          title={
            <div className="flex items-center gap-2.5">
              <Sparkles className="w-5 h-5 text-cyan-400" />
              <span>{editingProfile ? 'Edit Quality Profile' : 'Create Custom Quality Profile'}</span>
            </div>
          }
          subtitle="Configure maximum target resolution, fallback behavior, and audio preferences"
          maxWidth="lg"
        >
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Name */}
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                Profile Name
              </label>
              <input
                type="text"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Cinema 4K Master, Gaming 1440p, Mobile Mixtape"
                className="w-full glass-input px-3.5 py-2.5 rounded-xl text-sm"
              />
            </div>

            {/* Audio Only Toggle */}
            <div className="flex items-center justify-between p-3.5 rounded-xl bg-slate-900/60 border border-white/10">
              <div>
                <span className="text-xs font-bold text-white block">Audio Only Mode</span>
                <span className="text-[11px] text-slate-400">Skip video entirely and retain audio stream only</span>
              </div>
              <input
                type="checkbox"
                checked={isAudioOnly}
                onChange={(e) => setIsAudioOnly(e.target.checked)}
                className="w-4 h-4 rounded text-cyan-500 focus:ring-cyan-400"
              />
            </div>

            {/* Resolution Selector (if not audio only) */}
            {!isAudioOnly && (
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">
                  Maximum Target Resolution
                </label>
                <p className="text-[11px] text-slate-400 mb-1.5">
                  Resolution Ceiling: Videos will download in this resolution, or automatically fall back to the highest available resolution if this ceiling is not met.
                </p>
                <select
                  value={maxResolution}
                  onChange={(e) => setMaxResolution(Number(e.target.value))}
                  className="w-full glass-select px-3.5 py-2.5 rounded-xl text-sm cursor-pointer"
                >
                  <option value={4320} className="bg-slate-900">4320p (8K Ultra HD)</option>
                  <option value={2160} className="bg-slate-900">2160p (4K Ultra HD)</option>
                  <option value={1440} className="bg-slate-900">1440p (2K Quad HD)</option>
                  <option value={1080} className="bg-slate-900">1080p (Full HD)</option>
                  <option value={720} className="bg-slate-900">720p (HD)</option>
                  <option value={480} className="bg-slate-900">480p (Standard Definition)</option>
                  <option value={360} className="bg-slate-900">360p (Fast / Lightweight)</option>
                </select>
              </div>
            )}

            {/* Audio Format */}
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                Audio Container & Extraction
              </label>
              <select
                value={audioFormat}
                onChange={(e) => setAudioFormat(e.target.value)}
                className="w-full glass-select px-3.5 py-2.5 rounded-xl text-sm cursor-pointer"
              >
                <option value="copy" className="bg-slate-900">Direct Stream Copy (Fastest, Lossless original AAC/Opus)</option>
                <option value="flac" className="bg-slate-900">FLAC (Lossless Archive)</option>
                <option value="mp3" className="bg-slate-900">MP3 High Quality (320 kbps)</option>
                <option value="opus" className="bg-slate-900">Opus Audio (~160 kbps)</option>
                <option value="m4a" className="bg-slate-900">M4A (AAC)</option>
              </select>
            </div>

            {/* Description */}
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                Description
              </label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Optional notes regarding this profile's intended use..."
                rows={2}
                className="w-full glass-input px-3.5 py-2 rounded-xl text-xs"
              />
            </div>

            {/* Footer buttons */}
            <div className="flex items-center justify-end gap-2.5 pt-3 border-t border-white/10">
              <button
                type="button"
                onClick={handleCloseModal}
                className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-400 hover:text-white transition-colors"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={createMutation.isPending || updateMutation.isPending}
                className="glass-btn-cyan px-5 py-2 rounded-xl text-xs font-bold disabled:opacity-50"
              >
                {createMutation.isPending || updateMutation.isPending ? 'Saving...' : 'Save Profile'}
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  )
}
