import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { type Playlist, type Job, type QualityProfile, formatProfileOptionLabel } from '../../services/types'
import { playlistsApi, profilesApi } from '../../services/api'
import { PlaylistActions } from './PlaylistActions'
import { ProgressBar, DualTierProgressBar } from '../ui/ProgressBar'
import { FolderOpen, ExternalLink, Edit3, Loader2, Film } from 'lucide-react'
import { TrackInspectionModal } from '../modals/TrackInspectionModal'
import { useToast } from '../../context/ToastContext'

export interface PlaylistCardProps {
  playlist: Playlist
  runningJob?: Job
  isScanning?: boolean
  currentScanningPlaylist?: string | null
  onStartJob: (playlistId: number, jobType: 'download' | 'extract' | 'both') => void
  onCancelJob: (jobId: number) => void
  onRefresh: (playlistId: number) => void
  onDelete: (playlistId: number) => void
  onOpenFolder: (playlistId: number) => void
  onEditExclusions: (playlist: Playlist) => void
  isRefreshing?: boolean
  isCancelling?: boolean
  isOpenFolderPending?: boolean
}

export const PlaylistCard: React.FC<PlaylistCardProps> = ({
  playlist,
  runningJob,
  isScanning,
  currentScanningPlaylist,
  onStartJob,
  onCancelJob,
  onRefresh,
  onDelete,
  onOpenFolder,
  onEditExclusions,
  isRefreshing,
  isCancelling,
  isOpenFolderPending,
}) => {
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const [showInspectModal, setShowInspectModal] = useState(false)

  const effectiveAvailable = Math.max(0, playlist.playlist_count - (playlist.unavailable_count || 0))
  const isCaughtUp = playlist.playlist_count > 0 && playlist.local_count >= effectiveAvailable

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
    mutationFn: (newProfileId: string) => 
      playlistsApi.update(playlist.id, { quality_profile_id: newProfileId }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['playlists'] })
      toast.success('Quality profile updated')
    },
    onError: (err: any) => {
      toast.error(`Failed to update profile: ${err.message}`)
    },
  })

  return (
    <>
      <div
        className={`rounded-2xl transition-all duration-300 flex flex-col overflow-hidden ${
          isCaughtUp ? 'glass-tile-complete' : 'glass-tile-pending'
        }`}
      >
        <div className="p-5 flex-1 flex flex-col">
          {/* Header */}
          <div className="flex justify-between items-start mb-4">
            <div className="flex-1 min-w-0 pr-2">
              <div className="flex items-center gap-2 flex-wrap">
                <h3 className="text-base font-bold text-white truncate max-w-[210px]" title={playlist.title}>
                  {playlist.title}
                </h3>
                {isCaughtUp && (
                  <span className="text-emerald-300 font-semibold text-[11px] px-2 py-0.5 rounded-full bg-emerald-950/80 border border-emerald-500/50 inline-flex items-center gap-1 shadow-sm">
                    ✓ Caught up
                  </span>
                )}
              </div>

              {/* Meta & Interactive Profile Dropdown */}
              <div className="flex items-center gap-2 mt-2 flex-wrap">
                <div className="relative inline-flex items-center">
                  <select
                    value={playlist.quality_profile_id || 'standard_1080p'}
                    onChange={(e) => updateProfileMutation.mutate(e.target.value)}
                    disabled={updateProfileMutation.isPending}
                    className="appearance-none pl-2 pr-6 py-0.5 text-[10px] font-bold tracking-wider uppercase rounded-full bg-slate-900/90 text-cyan-300 border border-cyan-500/40 hover:border-cyan-400 focus:outline-none focus:ring-1 focus:ring-cyan-400 cursor-pointer transition-all shadow-xs"
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

                <a
                  href={playlist.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-slate-400 hover:text-cyan-300 inline-flex items-center gap-1 transition-colors"
                >
                  YouTube
                  <ExternalLink className="w-3 h-3" />
                </a>

                {/* Inspect Tracks Button */}
                <button
                  onClick={() => setShowInspectModal(true)}
                  className="px-2 py-0.5 text-[10px] font-semibold rounded-full bg-slate-800/80 hover:bg-slate-700 text-slate-300 hover:text-cyan-300 border border-white/10 hover:border-cyan-500/40 inline-flex items-center gap-1 transition-all ml-auto"
                  title="Inspect individual tracks, check available resolutions, and upgrade"
                >
                  <Film className="w-3 h-3 text-cyan-400" />
                  <span>Inspect</span>
                </button>
              </div>
            </div>

            {/* Open Folder Button */}
            <button
              onClick={() => onOpenFolder(playlist.id)}
              disabled={isOpenFolderPending}
              className="p-2 text-slate-400 hover:text-white rounded-xl hover:bg-white/10 disabled:opacity-50 transition-colors border border-transparent hover:border-white/10"
              title="Open folder in File Explorer"
            >
              <FolderOpen className="w-4 h-4" />
            </button>
          </div>

          {/* Frosted Jewel Stats Pills */}
          <div className="grid grid-cols-3 gap-2.5 mb-4">
            {/* Local Pill */}
            <div className="glass-pill-emerald text-center p-2.5 rounded-xl flex flex-col justify-center">
              <div className="text-xl font-extrabold leading-tight">
                {playlist.local_count}
              </div>
              <div className="text-[11px] font-semibold tracking-wide uppercase mt-0.5 opacity-90">
                Local
              </div>
            </div>

            {/* Available Pill */}
            <div className="glass-pill-blue text-center p-2.5 rounded-xl flex flex-col justify-center">
              <div className="text-xl font-extrabold leading-tight">
                {playlist.playlist_count}
              </div>
              <div className="text-[11px] font-semibold tracking-wide uppercase mt-0.5 opacity-90">
                Available
              </div>
            </div>

            {/* Unavailable Pill */}
            <div className="glass-pill-rose text-center p-2.5 rounded-xl flex flex-col justify-center">
              <div className="text-xl font-extrabold leading-tight">
                {playlist.unavailable_count}
              </div>
              <div className="text-[11px] font-semibold tracking-wide uppercase mt-0.5 opacity-90">
                Unavailable
              </div>
            </div>
          </div>

          {/* Spacer */}
          <div className="flex-1" />

        {/* Running Job Status */}
        {runningJob && (
          <div className="mb-4 p-3 bg-blue-50 dark:bg-blue-900/30 rounded border border-blue-200 dark:border-blue-800">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-blue-900 dark:text-blue-100 flex items-center gap-2">
                <Loader2 className="w-4 h-4 animate-spin" />
                {runningJob.job_type === 'both'
                  ? 'Downloading & Extracting'
                  : runningJob.job_type === 'download'
                  ? 'Downloading'
                  : 'Extracting'}
              </span>
              <span className="text-xs text-blue-700 dark:text-blue-300">
                Job #{runningJob.id}
              </span>
            </div>

            {/* Download Progress */}
            {runningJob.job_type !== 'extract' && runningJob.download_total > 0 && (
              <div className="mb-2">
                <DualTierProgressBar
                  itemCompleted={runningJob.download_completed}
                  itemTotal={runningJob.download_total}
                  itemLabel="Downloading Videos"
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

            {/* Extraction Progress */}
            {runningJob.job_type !== 'download' && runningJob.extract_total > 0 && (
              <div>
                <ProgressBar
                  completed={runningJob.extract_completed}
                  total={runningJob.extract_total}
                  variant="purple"
                  height="sm"
                  showLabel={true}
                  label="Extracting Audio"
                />
              </div>
            )}
          </div>
        )}

        {/* Actions */}
        <div className="mt-4">
          <PlaylistActions
            playlist={playlist}
            runningJob={runningJob}
            isScanning={isScanning}
            currentScanningPlaylist={currentScanningPlaylist}
            onStartJob={(type) => onStartJob(playlist.id, type)}
            onCancelJob={onCancelJob}
            onRefresh={() => onRefresh(playlist.id)}
            onDelete={() => onDelete(playlist.id)}
            isRefreshing={isRefreshing}
            isCancelling={isCancelling}
          />
        </div>

        {/* Last Activity & Exclusions */}
        <div className="mt-3 text-xs text-gray-400 space-y-1">
          {playlist.last_download && (
            <div>Last download: {new Date(playlist.last_download).toLocaleString()}</div>
          )}
          {playlist.last_extract && (
            <div>Last extract: {new Date(playlist.last_extract).toLocaleString()}</div>
          )}
          <div className="flex items-center justify-between pt-1 border-t border-white/10">
            <span className="text-gray-400">
              {playlist.excluded_ids?.length || 0} video{(playlist.excluded_ids?.length || 0) === 1 ? '' : 's'} excluded
            </span>
            <button
              onClick={() => onEditExclusions(playlist)}
              className="text-blue-400 hover:text-blue-300 flex items-center gap-1 font-medium text-xs transition-colors"
              title="Edit exclusions"
            >
              <Edit3 className="w-3.5 h-3.5" />
              <span>Edit</span>
            </button>
          </div>
        </div>
      </div>
    </div>

      {/* Track Inspection & Resolution Upgrade Modal */}
      {showInspectModal && (
        <TrackInspectionModal
          playlist={playlist}
          onClose={() => setShowInspectModal(false)}
        />
      )}
    </>
  )
}
