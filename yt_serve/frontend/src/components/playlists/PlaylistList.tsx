import React from 'react'
import type { Playlist, Job } from '../../services/types'
import { PlaylistActions } from './PlaylistActions'
import { ProgressBar, DualTierProgressBar } from '../ui/ProgressBar'
import { ExternalLink, FileText as LogIcon } from 'lucide-react'

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
  onOpenFolder: (playlistId: number) => void
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
  onOpenFolder,
  onEditExclusions,
  onViewLogs,
  refreshingPlaylistId,
  cancellingJobId,
}) => {
  const getRunningJob = (playlistId: number): Job | undefined => {
    return jobs.find(j => j.playlist_id === playlistId && (j.status === 'running' || j.status === 'pending'))
  }

  const sortedPlaylists = [...playlists].sort((a, b) => {
    const aPending = Math.max(0, a.playlist_count - a.local_count)
    const bPending = Math.max(0, b.playlist_count - b.local_count)
    return bPending - aPending
  })

  return (
    <div className="space-y-3">
      {sortedPlaylists.map((playlist) => {
        const runningJob = getRunningJob(playlist.id)
        const isCaughtUp = playlist.local_count >= playlist.playlist_count && playlist.playlist_count > 0
        const hasPendingDownloads = playlist.local_count < playlist.playlist_count && playlist.playlist_count > 0
        const isExpanded = expandedRows.has(playlist.id)

        return (
          <div
            key={playlist.id}
            className={`rounded-lg shadow-md hover:shadow-lg transition-all border ${
              isCaughtUp
                ? 'bg-gradient-to-r from-green-50 to-green-100 dark:from-green-900/20 dark:to-green-800/20 border-green-200 dark:border-green-800'
                : hasPendingDownloads
                ? 'bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700'
                : 'bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700'
            }`}
          >
            {/* Main Row */}
            <div
              onClick={() => onToggleRow(playlist.id)}
              className="px-6 py-4 cursor-pointer hover:bg-gray-50/50 dark:hover:bg-gray-700/50 transition-colors rounded-t-lg"
            >
              <div className="flex items-center justify-between gap-4 flex-wrap">
                {/* Title & Status */}
                <div className="flex-1 min-w-[240px]">
                  <div className="flex items-center gap-2 mb-1 flex-wrap">
                    <h3
                      className="text-lg font-semibold text-gray-900 dark:text-white truncate cursor-pointer hover:text-blue-600 dark:hover:text-blue-400 transition-colors"
                      onClick={(e) => {
                        e.stopPropagation()
                        onOpenFolder(playlist.id)
                      }}
                      title="Click to open folder in explorer"
                    >
                      {playlist.title}
                    </h3>
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        window.open(playlist.url, '_blank')
                      }}
                      className="p-1 text-gray-400 hover:text-blue-600 dark:hover:text-blue-400 transition-colors"
                      title="Open playlist in browser"
                    >
                      <ExternalLink className="w-4 h-4" />
                    </button>
                    <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold bg-indigo-50 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800">
                      {playlist.quality_profile_id ? playlist.quality_profile_id.replace(/_/g, ' ').toUpperCase() : 'STANDARD 1080P'}
                    </span>
                    {isCaughtUp && (
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">
                        ✓ Complete
                      </span>
                    )}
                    {runningJob && (
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200 animate-pulse">
                        ● Running
                      </span>
                    )}
                  </div>

                  {/* Running Job Details */}
                  {runningJob && (
                    <div className="text-xs text-gray-600 dark:text-gray-400 space-x-3 mt-1">
                      {runningJob.download_status === 'running' && (
                        <span>📥 Downloading {runningJob.download_completed}/{runningJob.download_total}</span>
                      )}
                      {runningJob.extract_status === 'running' && (
                        <span>🎵 Extracting {runningJob.extract_completed}/{runningJob.extract_total}</span>
                      )}
                    </div>
                  )}
                </div>

                {/* Stats with colored backgrounds */}
                <div className="flex items-center gap-3 flex-wrap">
                  <div className="text-center p-3 bg-green-50 dark:bg-green-900/30 rounded-lg min-w-[75px]">
                    <div className="text-2xl font-bold text-green-700 dark:text-green-400">{playlist.local_count}</div>
                    <div className="text-xs text-gray-600 dark:text-gray-400">Local</div>
                  </div>
                  <div className="text-center p-3 bg-blue-50 dark:bg-blue-900/30 rounded-lg min-w-[75px]">
                    <div className="text-2xl font-bold text-blue-700 dark:text-blue-400">{playlist.playlist_count}</div>
                    <div className="text-xs text-gray-600 dark:text-gray-400">Available</div>
                  </div>
                  <div
                    className={`text-center p-3 bg-red-50 dark:bg-red-900/30 rounded-lg min-w-[75px] ${
                      playlist.unavailable_count > 0
                        ? 'cursor-pointer hover:bg-red-100 dark:hover:bg-red-900/50 transition-colors ring-1 ring-red-200 dark:ring-red-800'
                        : ''
                    }`}
                    onClick={(e) => {
                      if (playlist.unavailable_count > 0) {
                        e.stopPropagation()
                        onEditExclusions(playlist)
                      }
                    }}
                    title={playlist.unavailable_count > 0 ? "Click to manage unavailable / excluded videos" : undefined}
                  >
                    <div className="text-2xl font-bold text-red-700 dark:text-red-400">{playlist.unavailable_count}</div>
                    <div className="text-xs text-gray-600 dark:text-gray-400">Unavailable</div>
                  </div>

                  {playlist.last_download && (
                    <div className="hidden lg:block text-center p-3 bg-gray-50 dark:bg-gray-700/30 rounded-lg min-w-[120px]">
                      <div className="text-xs font-semibold text-gray-700 dark:text-gray-300">
                        {new Date(playlist.last_download).toLocaleDateString()}
                      </div>
                      <div className="text-[11px] text-gray-500 dark:text-gray-400">Last Download</div>
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Expanded Section with Actions */}
            {isExpanded && (
              <div className="px-6 py-4 bg-gray-50 dark:bg-gray-900/50 border-t border-gray-200 dark:border-gray-700 rounded-b-lg">
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
  )
}
