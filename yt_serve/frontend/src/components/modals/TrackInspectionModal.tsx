import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { playlistsApi, jobsApi } from '../../services/api'
import type { Playlist, PlaylistTrack } from '../../services/types'
import { Modal } from '../ui/Modal'
import { useToast } from '../../context/ToastContext'
import { 
  Search, 
  RefreshCw, 
  Sparkles, 
  ExternalLink,
  Film,
  Music,
  Loader2,
  Trash2,
  Download,
  Zap
} from 'lucide-react'

export interface TrackInspectionModalProps {
  playlist: Playlist
  onClose: () => void
}

export const TrackInspectionModal: React.FC<TrackInspectionModalProps> = ({ playlist, onClose }) => {
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const [search, setSearch] = useState('')
  const [upgradingVideoId, setUpgradingVideoId] = useState<string | null>(null)
  const [exportFormat, setExportFormat] = useState('mp3')
  const [extractingAudioVideoId, setExtractingAudioVideoId] = useState<string | null>(null)

  const hasLocalTracks = (playlist.local_count || 0) > 0

  // Fetch playlist tracks (instant render with 0ms delay if local_count === 0)
  const { data: tracks = [], isLoading } = useQuery({
    queryKey: ['playlistTracks', playlist.id],
    queryFn: async () => {
      const res = await playlistsApi.getTracks(playlist.id)
      return res.data
    },
    enabled: hasLocalTracks,
    initialData: hasLocalTracks ? undefined : [],
  })

  // Refresh available resolutions mutation
  const refreshResolutions = useMutation({
    mutationFn: () => playlistsApi.refreshResolutions(playlist.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['playlistTracks', playlist.id] })
      toast.success('Resolutions refreshed from YouTube')
    },
    onError: (err: any) => {
      toast.error(`Failed to refresh resolutions: ${err.message}`)
    },
  })

  // Upgrade track resolution mutation
  const upgradeTrack = useMutation({
    mutationFn: async ({ videoId, targetResolution }: { videoId: string; targetResolution: number }) => {
      setUpgradingVideoId(videoId)
      return playlistsApi.upgradeTrack(playlist.id, videoId, { 
        target_resolution: targetResolution,
        delete_older: false 
      })
    },
    onSuccess: (_, vars) => {
      queryClient.invalidateQueries({ queryKey: ['playlistTracks', playlist.id] })
      queryClient.invalidateQueries({ queryKey: ['playlists'] })
      toast.success(`Track upgraded to ${vars.targetResolution}p successfully!`)
      setUpgradingVideoId(null)
    },
    onError: (err: any) => {
      const msg = err.response?.data?.detail || err.message
      toast.error(`Upgrade failed: ${msg}`)
      setUpgradingVideoId(null)
    },
  })

  // Delete version mutation
  const deleteVersion = useMutation({
    mutationFn: ({ videoId, resolution }: { videoId: string; resolution: string }) =>
      playlistsApi.deleteTrackVersion(playlist.id, videoId, resolution),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['playlistTracks', playlist.id] })
      toast.success('Track version removed')
    },
    onError: (err: any) => {
      toast.error(`Delete failed: ${err.message}`)
    },
  })

  // Full playlist audio extraction mutation
  const extractPlaylistAudio = useMutation({
    mutationFn: (fmt: string) => jobsApi.create(playlist.id, 'extract', fmt),
    onSuccess: () => {
      toast.success(`Audio extraction job started (${exportFormat.toUpperCase()})! View live progress in Activity Logs.`)
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
    },
    onError: (err: any) => {
      const msg = err.response?.data?.detail || err.message
      toast.error(`Failed to start extraction: ${msg}`)
    },
  })

  // Per-track single audio extraction mutation
  const extractTrackAudio = useMutation({
    mutationFn: async ({ videoId, fmt }: { videoId: string; fmt: string }) => {
      setExtractingAudioVideoId(videoId)
      return playlistsApi.extractTrackAudio(playlist.id, videoId, fmt)
    },
    onSuccess: (_, vars) => {
      queryClient.invalidateQueries({ queryKey: ['playlistTracks', playlist.id] })
      toast.success(`Audio extracted for track in ${vars.fmt.toUpperCase()}!`)
      setExtractingAudioVideoId(null)
    },
    onError: (err: any) => {
      const msg = err.response?.data?.detail || err.message
      toast.error(`Audio extraction failed: ${msg}`)
      setExtractingAudioVideoId(null)
    },
  })

  const handleDownloadZip = () => {
    const url = playlistsApi.getExportAudioZipUrl(playlist.id, exportFormat)
    window.open(url, '_blank')
  }

  const filteredTracks = tracks.filter((t: PlaylistTrack) => {
    const q = search.toLowerCase()
    return t.title.toLowerCase().includes(q) || t.video_id.toLowerCase().includes(q)
  })

  const formatDuration = (seconds?: number) => {
    if (!seconds) return ''
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  const formatBytes = (bytes?: number) => {
    if (!bytes) return '0 MB'
    const mb = bytes / (1024 * 1024)
    return mb >= 1024 ? `${(mb / 1024).toFixed(1)} GB` : `${mb.toFixed(1)} MB`
  }

  return (
    <Modal
      isOpen={true}
      onClose={onClose}
      title={
        <div className="flex items-center gap-3">
          <Film className="w-6 h-6 text-cyan-400" />
          <span>Track Inspector & Resolution Manager</span>
        </div>
      }
      subtitle={
        <div className="flex items-center gap-2 mt-1">
          <span className="text-white font-medium">{playlist.title}</span>
          <span className="text-slate-500">•</span>
          <span className="text-slate-400">{tracks.length} tracks detected</span>
        </div>
      }
      maxWidth="5xl"
      resizable={true}
      headerActions={
        <button
          onClick={() => refreshResolutions.mutate()}
          disabled={refreshResolutions.isPending}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-cyan-300 border border-cyan-500/30 transition-all disabled:opacity-50"
          title="Scan YouTube to check if 4K or 1440p resolutions are available for these tracks"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${refreshResolutions.isPending ? 'animate-spin' : ''}`} />
          <span className="hidden sm:inline">Refresh YouTube Resolutions</span>
        </button>
      }
    >
      <div className="space-y-4">
        {/* Audio Export & Offline Sync Bar */}
        <div className="flex flex-col sm:flex-row items-center justify-between gap-3 p-3.5 rounded-xl bg-gradient-to-r from-emerald-950/40 via-slate-900/60 to-indigo-950/40 border border-emerald-500/20 shadow-xs">
          <div className="flex items-center gap-2.5 text-xs">
            <div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 shadow-xs">
              <Music className="w-4 h-4" />
            </div>
            <div>
              <span className="font-semibold text-white">Audio Export &amp; Offline Sync</span>
              <p className="text-[11px] text-slate-400">Phone-ready folders with dual UTF-8 .m3u8 &amp; .m3u playlists</p>
            </div>
          </div>

          <div className="flex items-center gap-2 flex-wrap w-full sm:w-auto justify-end">
            <select
              value={exportFormat}
              onChange={(e) => setExportFormat(e.target.value)}
              className="px-2.5 py-1.5 rounded-lg text-xs bg-slate-800 text-slate-200 border border-emerald-500/30 focus:outline-none focus:border-emerald-400 font-medium"
              title="Target audio export format and bitrate"
            >
              <option value="mp3">MP3 320k (CBR)</option>
              <option value="mp3_v0">MP3 V0 (VBR High)</option>
              <option value="flac">FLAC (Lossless)</option>
              <option value="aac">AAC (256k M4A)</option>
              <option value="opus">OPUS (Standard)</option>
            </select>

            <button
              onClick={() => extractPlaylistAudio.mutate(exportFormat)}
              disabled={extractPlaylistAudio.isPending || !hasLocalTracks}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-emerald-600 hover:bg-emerald-500 text-white shadow-xs transition-all disabled:opacity-50"
              title="Transcode all tracks into dedicated export folder with YouTube index tags"
            >
              {extractPlaylistAudio.isPending ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <Zap className="w-3.5 h-3.5" />
              )}
              <span>Extract to Folder</span>
            </button>

            <button
              onClick={handleDownloadZip}
              disabled={!hasLocalTracks}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-indigo-600 hover:bg-indigo-500 text-white shadow-xs transition-all disabled:opacity-50"
              title="Stream lossless uncompressed ZIP archive of this format directly to browser"
            >
              <Download className="w-3.5 h-3.5" />
              <span>Download ZIP</span>
            </button>
          </div>
        </div>

        {/* Search & Stats Bar */}
        <div className="flex flex-col sm:flex-row items-center justify-between gap-3 p-3 rounded-xl bg-slate-900/60 border border-white/10">
          <div className="relative w-full sm:w-80">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by title or video ID..."
              className="w-full pl-9 pr-3 py-1.5 rounded-lg text-xs bg-slate-800/80 border border-white/10 text-white placeholder-slate-400 focus:outline-none focus:border-cyan-400"
            />
          </div>
          <div className="flex items-center gap-3 text-xs text-slate-400 w-full sm:w-auto justify-end">
            <span className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-cyan-400 shadow-xs shadow-cyan-400"></span>
              4K Upgradable
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-blue-400 shadow-xs shadow-blue-400"></span>
              1440p Upgradable
            </span>
          </div>
        </div>

        {/* Tracks List */}
        {isLoading ? (
          <div className="flex flex-col items-center justify-center py-16 text-slate-400 gap-3">
            <Loader2 className="w-8 h-8 animate-spin text-cyan-400" />
            <p className="text-sm font-medium">Loading playlist track catalog...</p>
          </div>
        ) : filteredTracks.length === 0 ? (
          <div className="text-center py-12 text-slate-400 bg-slate-900/30 rounded-xl border border-white/5 space-y-1.5">
            {tracks.length === 0 ? (
              <>
                <Film className="w-8 h-8 text-slate-600 mx-auto mb-2" />
                <p className="text-sm font-semibold text-slate-300">No tracks downloaded yet</p>
                <p className="text-xs text-slate-500 max-w-sm mx-auto">
                  Run a download job for this playlist to inspect video tracks, audio codecs, and available resolutions.
                </p>
              </>
            ) : (
              <>
                <Search className="w-8 h-8 text-slate-600 mx-auto mb-2" />
                <p className="text-sm font-semibold text-slate-300">No tracks match "{search}"</p>
                <p className="text-xs text-slate-500">
                  Try searching for a different title or video ID.
                </p>
              </>
            )}
          </div>
        ) : (
          <div className="space-y-2.5 max-h-[60vh] overflow-y-auto pr-1">
            {filteredTracks.map((track: PlaylistTrack) => {
              const isUpgrading = upgradingVideoId === track.video_id
              const currentResHeight = track.primary_resolution ? parseInt(track.primary_resolution.replace(/\D/g, '')) || 0 : 0
              
              // Find if 4K (>=2160) or 1440p (>=1440) is available
              const has4k = track.available_resolutions?.some(r => r.height >= 2160)
              const has1440p = track.available_resolutions?.some(r => r.height === 1440)
              const canUpgrade4k = has4k && currentResHeight < 2160
              const canUpgrade1440p = has1440p && currentResHeight < 1440 && !canUpgrade4k

              return (
                <div
                  key={track.video_id}
                  className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 p-3.5 rounded-xl bg-slate-900/60 hover:bg-slate-900/80 border border-white/10 hover:border-white/20 transition-all shadow-sm"
                >
                  {/* Left: Thumbnail & Details */}
                  <div className="flex items-center gap-3.5 flex-1 min-w-0">
                    <div className="relative w-20 h-12 rounded-lg overflow-hidden bg-slate-800 shrink-0 border border-white/10 shadow-xs">
                      <img
                        src={`https://i.ytimg.com/vi/${track.video_id}/hqdefault.jpg`}
                        alt={track.title}
                        className="w-full h-full object-cover"
                        loading="lazy"
                        onError={(e) => {
                          // Fallback placeholder if image fails to load
                          (e.target as HTMLElement).style.display = 'none'
                        }}
                      />
                      {track.duration && (
                        <span className="absolute bottom-1 right-1 px-1 py-0.2 rounded text-[9px] font-mono bg-black/80 text-white">
                          {formatDuration(track.duration)}
                        </span>
                      )}
                    </div>

                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <h4 className="text-sm font-semibold text-white truncate" title={track.title}>
                          {track.title}
                        </h4>
                        <a
                          href={`https://www.youtube.com/watch?v=${track.video_id}`}
                          target="_blank"
                          rel="noreferrer"
                          className="text-slate-400 hover:text-cyan-300"
                          title="Open on YouTube"
                        >
                          <ExternalLink className="w-3 h-3" />
                        </a>
                      </div>

                      <div className="flex items-center gap-2 mt-1.5 flex-wrap">
                        {/* Current Primary Resolution Pill */}
                        {track.primary_resolution ? (
                          <span className={`px-2 py-0.5 rounded-full text-[11px] font-bold border ${
                            currentResHeight >= 2160
                              ? 'bg-purple-950/70 text-purple-300 border-purple-500/50 shadow-xs shadow-purple-500/30'
                              : currentResHeight >= 1440
                              ? 'bg-cyan-950/70 text-cyan-300 border-cyan-500/50 shadow-xs shadow-cyan-500/30'
                              : 'bg-blue-950/60 text-blue-300 border-blue-700/50'
                          }`}>
                            {track.primary_resolution}
                          </span>
                        ) : (
                          <span className="px-2 py-0.5 rounded-full text-[11px] font-medium bg-slate-800 text-slate-400 border border-slate-700">
                            Not Downloaded
                          </span>
                        )}

                        {/* File size */}
                        {track.video_size_bytes > 0 && (
                          <span className="text-[11px] text-slate-400">
                            {formatBytes(track.video_size_bytes)}
                          </span>
                        )}

                        {/* Audio Pill */}
                        {track.downloaded_audio_codec && (
                          <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-slate-800/80 text-emerald-300 border border-emerald-500/30 flex items-center gap-1">
                            <Music className="w-2.5 h-2.5" />
                            {track.downloaded_audio_codec}
                            {track.downloaded_audio_bitrate ? ` • ${track.downloaded_audio_bitrate}` : ''}
                          </span>
                        )}

                        {/* Hardlink Badge */}
                        {track.is_hardlinked && (
                          <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-indigo-950/60 text-indigo-300 border border-indigo-700/50">
                            Hardlinked
                          </span>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Right: Resolution Upgrade Actions */}
                  <div className="flex items-center gap-2 shrink-0 w-full md:w-auto justify-end border-t md:border-t-0 pt-2 md:pt-0 border-white/5">
                    {/* Primary Upgrade to 4K Button */}
                    {canUpgrade4k && (
                      <button
                        onClick={() => upgradeTrack.mutate({ videoId: track.video_id, targetResolution: 2160 })}
                        disabled={isUpgrading}
                        className="glass-btn-cyan px-3.5 py-1.5 rounded-xl text-xs font-bold flex items-center gap-1.5 disabled:opacity-50"
                        title="Download 4K Ultra HD version of this track"
                      >
                        {isUpgrading ? (
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        ) : (
                          <Sparkles className="w-3.5 h-3.5" />
                        )}
                        <span>Upgrade to 4K</span>
                      </button>
                    )}

                    {/* Upgrade to 1440p Button */}
                    {canUpgrade1440p && (
                      <button
                        onClick={() => upgradeTrack.mutate({ videoId: track.video_id, targetResolution: 1440 })}
                        disabled={isUpgrading}
                        className="glass-btn-purple px-3.5 py-1.5 rounded-xl text-xs font-bold flex items-center gap-1.5 disabled:opacity-50"
                        title="Download 1440p Quad HD version of this track"
                      >
                        {isUpgrading ? (
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        ) : (
                          <Sparkles className="w-3.5 h-3.5" />
                        )}
                        <span>Upgrade to 1440p</span>
                      </button>
                    )}

                    {/* Resolution Switcher / Select if other available */}
                    {track.available_resolutions && track.available_resolutions.length > 0 && (
                      <select
                        defaultValue=""
                        onChange={(e) => {
                          const val = parseInt(e.target.value)
                          if (val) {
                            upgradeTrack.mutate({ videoId: track.video_id, targetResolution: val })
                            e.target.value = ''
                          }
                        }}
                        disabled={isUpgrading}
                        className="px-2.5 py-1.5 rounded-xl text-xs bg-slate-800/90 text-slate-300 border border-white/10 focus:outline-none focus:border-cyan-400 disabled:opacity-50"
                        title="Select explicit target resolution"
                      >
                        <option value="" disabled>Custom Res...</option>
                        {track.available_resolutions.map((opt) => (
                          <option key={opt.height} value={opt.height}>
                            {opt.label || `${opt.height}p`} {opt.fps ? `(${opt.fps}fps)` : ''}
                          </option>
                        ))}
                      </select>
                    )}

                    {/* Per-track Audio Extraction Button */}
                    <button
                      onClick={() => extractTrackAudio.mutate({ videoId: track.video_id, fmt: exportFormat })}
                      disabled={extractingAudioVideoId === track.video_id}
                      className="px-2.5 py-1.5 rounded-xl text-xs font-semibold bg-slate-800/90 hover:bg-emerald-950/60 text-emerald-300 border border-emerald-500/30 hover:border-emerald-400 flex items-center gap-1 transition-all disabled:opacity-50"
                      title={`Extract audio copy in ${exportFormat.toUpperCase()} with ID3 tags and update M3U8`}
                    >
                      {extractingAudioVideoId === track.video_id ? (
                        <Loader2 className="w-3 h-3 animate-spin" />
                      ) : (
                        <Zap className="w-3 h-3 text-emerald-400" />
                      )}
                      <span>{exportFormat.toUpperCase()}</span>
                    </button>

                    {/* Multi-version management: delete version */}
                    {track.downloaded_resolutions && track.downloaded_resolutions.length > 1 && (
                      <button
                        onClick={() => {
                          const older = track.downloaded_resolutions.find(r => r !== track.primary_resolution)
                          if (older && confirm(`Delete secondary downloaded resolution ${older}?`)) {
                            deleteVersion.mutate({ videoId: track.video_id, resolution: older })
                          }
                        }}
                        className="p-2 text-slate-400 hover:text-rose-400 rounded-lg hover:bg-white/5 transition-colors"
                        title="Delete secondary version"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </Modal>
  )
}
