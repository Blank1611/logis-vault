import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { type Playlist, type Job, type QualityProfile, formatProfileOptionLabel } from '../../services/types'
import { playlistsApi, profilesApi } from '../../services/api'
import { PlaylistActions } from './PlaylistActions'
import { ProgressBar, DualTierProgressBar } from '../ui/ProgressBar'
import { ExternalLink, FileText as LogIcon, Film } from 'lucide-react'
import { TrackInspectionModal } from '../modals/TrackInspectionModal'
import { useToast } from '../../context/ToastContext'

export interface PlaylistListProps {
  playlists: Playlist[]
  jobs: Job[]
  expandedRows: Set<number>
  onToggleRow: (playlistId: number) => void
  isScanning?: boolean
  currentScanningPlaylist?: string | null
  onStartJob: (playlistId: number, jobType: 'download' | 'extract' | 'both') => void
  onCancelJob: (jobId: number) => void
  onRefresh: (playlistId: number) => void
  onDelete: (playlistId: number) => void
  onOpenFolder?: (playlistId: number) => void
  onEditExclusions: (playlist: Playlist) => void
  onViewLogs: (job: Job) => void
  refreshingPlaylistId?: number | null
  cancellingJobId?: number | null
}

export const PlaylistList: React.FC<PlaylistListProps> = ({
  playlists,
  jobs,
  expandedRows,
  onToggleRow,
  isScanning,
  currentScanningPlaylist,
  onStartJob,
  onCancelJob,
  onRefresh,
  onDelete,
  onOpenFolder: _onOpenFolder,
  onEditExclusions,
  onViewLogs,
  refreshingPlaylistId,
  cancellingJobId,
}) => {
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const [inspectingPlaylist, setInspectingPlaylist] = useState<Playlist | null>(null)

  // Fetch quality profiles
  const { data: profiles = [] } = useQuery({
    queryKey: ['profiles'],
    queryFn: async () => {
      const res = await profilesApi.getAll()
      return res.data
    },
    staleTime: 60000,
  })

  // Update profile mutation
  const updateProfileMutation = useMutation({
    mutationFn: ({ playlistId, newProfileId }: { playlistId: number; newProfileId: string }) =>
      playlistsApi.update(playlistId, { quality_profile_id: newProfileId }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['playlists'] })
      toast.success('Quality profile updated')
    },
    onError: (err: any) => {
      toast.error(`Failed to update profile: ${err.message}`)
    },
  })

  const getRunningJob = (playlistId: number): Job | undefined => {
    return jobs.find(j => j.playlist_id === playlistId && (j.status === 'running' || j.status === 'pending'))
  }

  const sortedPlaylists = [...playlists].sort((a, b) => {
    const aAvailable = Math.max(0, a.playlist_count - (a.unavailable_count || 0))
    const bAvailable = Math.max(0, b.playlist_count - (b.unavailable_count || 0))
    const aPending = Math.max(0, aAvailable - a.local_count)
    const bPending = Math.max(0, bAvailable - b.local_count)

    if (bPending !== aPending) {
      return bPending - aPending
    }
    return a.title.localeCompare(b.title)
  })

  return (
    <>
      <div className="space-y-4">
        {sortedPlaylists.map((playlist) => {
          const runningJob = getRunningJob(playlist.id)
          const effectiveAvailable = Math.max(0, playlist.playlist_count - (playlist.unavailable_count || 0))
          const isCaughtUp = playlist.playlist_count > 0 && playlist.local_count >= effectiveAvailable
          const isExpanded = expandedRows.has(playlist.id)

          return (
            <div
              key={playlist.id}
              className={`rounded-2xl transition-all duration-300 overflow-hidden ${
                isCaughtUp ? 'glass-tile-complete' : 'glass-tile-pending'
              }`}
            >
              {/* Main Row */}
              <div
                onClick={() => onToggleRow(playlist.id)}
                className="px-6 py-4 cursor-pointer hover:bg-white/5 transition-colors rounded-t-2xl"
              >
                <div className="flex items-center justify-between gap-4 flex-wrap">
                  {/* Title & Status */}
                  <div className="flex-1 min-w-[240px]">
                    <div className="flex items-center gap-2 mb-1 flex-wrap">
                      <a
                        href={playlist.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        onClick={(e) => e.stopPropagation()}
                        className="text-lg font-bold text-white hover:text-cyan-400 transition-colors inline-flex items-center gap-1.5 truncate max-w-[280px] group"
                        title={`${playlist.title} (Open on YouTube)`}
                      >
                        <span className="truncate">{playlist.title}</span>
                        <ExternalLink className="w-3.5 h-3.5 text-slate-500 group-hover:text-cyan-400 shrink-0 transition-colors" />
                      </a>

                      {/* Interactive Profile Dropdown */}
                      <div className="relative inline-flex items-center" onClick={(e) => e.stopPropagation()}>
                        <select
                          value={playlist.quality_profile_id || 'standard_1080p'}
                          onChange={(e) => updateProfileMutation.mutate({ playlistId: playlist.id, newProfileId: e.target.value })}
                          disabled={updateProfileMutation.isPending}
                          className="appearance-none pl-2.5 pr-6 py-0.5 text-[10px] font-bold tracking-wider uppercase rounded-full bg-slate-900/90 text-cyan-300 border border-cyan-500/40 hover:border-cyan-400 focus:outline-none focus:ring-1 focus:ring-cyan-400 cursor-pointer transition-all shadow-xs"
                          title="Change default Quality Profile for this playlist"
                        >
                          {profiles.map((p: QualityProfile) => (
                            <option key={p.id} value={p.id} className="bg-slate-900 text-white">
                              {formatProfileOptionLabel(p)}
                            </option>
                          ))}
                          {profiles.length === 0 && (
                            <option value="standard_1080p" className="bg-slate-900 text-white">
                              Standard HD (1080p • Direct Copy)
                            </option>
                          )}
                        </select>
                        <span className="absolute right-1.5 pointer-events-none text-[8px] text-cyan-400">▼</span>
                      </div>

                      {/* Inspect Tracks Button */}
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          setInspectingPlaylist(playlist)
                        }}
                        className="px-2.5 py-0.5 text-[10px] font-semibold rounded-full bg-slate-800/80 hover:bg-slate-700 text-slate-300 hover:text-cyan-300 border border-white/10 hover:border-cyan-500/40 inline-flex items-center gap-1 transition-all cursor-pointer shadow-xs"
                        title="Inspect individual tracks, check available resolutions, and upgrade"
                      >
                        <Film className="w-3 h-3 text-cyan-400" />
                        <span>Inspect</span>
                      </button>

                      {isCaughtUp && (
                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-950/70 text-emerald-400 border border-emerald-500/40 shadow-xs">
                          ✓ Caught up
                        </span>
                      )}
                      {runningJob && (
                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-950/70 text-blue-300 border border-blue-500/40 animate-pulse">
                          ● Running
                        </span>
                      )}
                    </div>

                    {/* Running Job Details */}
                    {runningJob && (
                      <div className="text-xs text-blue-200/80 space-x-3 mt-1 font-mono">
                        {runningJob.download_status === 'running' && (
                          <span>📥 Downloading {runningJob.download_completed}/{runningJob.download_total}</span>
                        )}
                        {runningJob.extract_status === 'running' && (
                          <span>🎵 Extracting {runningJob.extract_completed}/{runningJob.extract_total}</span>
                        )}
                      </div>
                    )}
                  </div>

                  {/* Frosted Jewel Stat Pills */}
                  <div className="flex items-center gap-2.5 flex-wrap">
                    <div className="glass-pill-emerald text-center p-2.5 rounded-xl min-w-[76px] flex flex-col justify-center">
                      <div className="text-xl font-extrabold leading-tight">{playlist.local_count}</div>
                      <div className="text-[11px] font-semibold tracking-wide uppercase mt-0.5 opacity-90">Local</div>
                    </div>
                    <div className="glass-pill-blue text-center p-2.5 rounded-xl min-w-[76px] flex flex-col justify-center">
                      <div className="text-xl font-extrabold leading-tight">{playlist.playlist_count}</div>
                      <div className="text-[11px] font-semibold tracking-wide uppercase mt-0.5 opacity-90">Available</div>
                    </div>
                    <div className="glass-pill-rose text-center p-2.5 rounded-xl min-w-[76px] flex flex-col justify-center">
                      <div className="text-xl font-extrabold leading-tight">{playlist.unavailable_count}</div>
                      <div className="text-[11px] font-semibold tracking-wide uppercase mt-0.5 opacity-90">Unavailable</div>
                    </div>

                    {playlist.last_download && (
                      <div className="hidden lg:block text-center p-2.5 bg-slate-900/60 rounded-xl min-w-[110px] border border-white/5">
                        <div className="text-xs font-semibold text-gray-200">
                          {new Date(playlist.last_download).toLocaleDateString()}
                        </div>
                        <div className="text-[10px] text-gray-400 uppercase tracking-wide mt-0.5">Last Download</div>
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* Expanded Section with Actions */}
              {isExpanded && (
                <div className="px-6 py-4 bg-slate-950/40 backdrop-blur-md border-t border-white/10 rounded-b-2xl">
                  <div className="space-y-4">
                    {/* Progress Bars */}
                    {runningJob && (
                      <div className="space-y-3">
                        {runningJob.download_status && runningJob.download_status !== 'completed' && (
                          <div>
                            <DualTierProgressBar
                              itemCompleted={runningJob.download_completed}
                              itemTotal={runningJob.download_total}
                              itemLabel="📥 Downloading Videos"
                              batchInfo={runningJob.download_batch_info}
                              currentTitle={runningJob.current_video_title}
                              bytesDownloaded={runningJob.current_video_bytes_downloaded}
                              bytesTotal={runningJob.current_video_bytes_total}
                              speed={runningJob.current_video_speed}
                              eta={runningJob.current_video_eta}
                              variant="blue"
                            />
                          </div>
                        )}

                        {runningJob.extract_status && runningJob.extract_status !== 'completed' && (
                          <div>
                            <ProgressBar
                              completed={runningJob.extract_completed}
                              total={runningJob.extract_total}
                              variant="purple"
                              height="md"
                              showLabel={true}
                              label="🎵 Extracting Audio"
                            />
                          </div>
                        )}

                        <button
                          onClick={() => onViewLogs(runningJob)}
                          className="text-xs text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300 flex items-center gap-1 font-medium"
                        >
                          <LogIcon className="w-3.5 h-3.5" />
                          View Logs in Popup
                        </button>
                      </div>
                    )}

                    {/* Actions */}
                    <PlaylistActions
                      playlist={playlist}
                      runningJob={runningJob}
                      isScanning={isScanning}
                      currentScanningPlaylist={currentScanningPlaylist}
                      onStartJob={(type) => onStartJob(playlist.id, type)}
                      onCancelJob={onCancelJob}
                      onRefresh={() => onRefresh(playlist.id)}
                      onDelete={() => onDelete(playlist.id)}
                      onEditExclusions={() => onEditExclusions(playlist)}
                      isRefreshing={refreshingPlaylistId === playlist.id}
                      isCancelling={runningJob ? cancellingJobId === runningJob.id : false}
                      compact={true}
                    />
                  </div>
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* Track Inspection & Resolution Upgrade Modal */}
      {inspectingPlaylist && (
        <TrackInspectionModal
          playlist={inspectingPlaylist}
          onClose={() => setInspectingPlaylist(null)}
        />
      )}
    </>
  )
}

