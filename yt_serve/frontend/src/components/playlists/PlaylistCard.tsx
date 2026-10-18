import React from 'react'
import type { Playlist, Job } from '../../services/types'
import { PlaylistActions } from './PlaylistActions'
import { ProgressBar, DualTierProgressBar } from '../ui/ProgressBar'
import { FolderOpen, ExternalLink, Edit3, Loader2 } from 'lucide-react'

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
  const pendingCount = Math.max(0, playlist.playlist_count - playlist.local_count)
  const isCaughtUp = playlist.local_count >= playlist.playlist_count && playlist.playlist_count > 0

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md hover:shadow-lg transition-shadow border border-gray-200 dark:border-gray-700 flex flex-col overflow-hidden">
      <div className="p-6 flex-1 flex flex-col">
        {/* Header */}
        <div className="flex justify-between items-start mb-4">
          <div className="flex-1 min-w-0 pr-2">
            <h3 className="text-lg font-bold text-gray-900 dark:text-white line-clamp-2" title={playlist.title}>
              {playlist.title}
            </h3>
            <div className="flex items-center gap-2 mt-1 flex-wrap">
              <span className="px-2 py-0.5 text-[10px] font-semibold rounded-full bg-indigo-50 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800">
                {playlist.quality_profile_id ? playlist.quality_profile_id.replace(/_/g, ' ').toUpperCase() : 'STANDARD 1080P'}
              </span>
              <a
                href={playlist.url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs text-blue-600 dark:text-blue-400 hover:underline inline-flex items-center gap-1"
              >
                View on YouTube
                <ExternalLink className="w-3 h-3" />
              </a>
            </div>
          </div>

          {/* Open Folder Button */}
          <button
            onClick={() => onOpenFolder(playlist.id)}
            disabled={isOpenFolderPending}
            className="p-2 text-gray-600 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white rounded hover:bg-gray-100 dark:hover:bg-gray-700 disabled:opacity-50 transition-colors"
            title="Open folder in File Explorer"
          >
            <FolderOpen className="w-4 h-4" />
          </button>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-3 gap-4 mb-4 p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
          <div className="text-center">
            <div className="text-2xl font-bold text-blue-600 dark:text-blue-400">
              {playlist.local_count}
            </div>
            <div className="text-xs text-gray-600 dark:text-gray-400">Local Files</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-green-600 dark:text-green-400">
              {playlist.playlist_count}
            </div>
            <div className="text-xs text-gray-600 dark:text-gray-400">Available</div>
          </div>
          <div
            className={`text-center ${
              playlist.unavailable_count > 0
                ? 'cursor-pointer hover:bg-red-50 dark:hover:bg-red-900/30 rounded p-1 transition-colors'
                : ''
            }`}
            onClick={() => {
              if (playlist.unavailable_count > 0) {
                onEditExclusions(playlist)
              }
            }}
            title={playlist.unavailable_count > 0 ? "Click to manage unavailable / excluded videos" : undefined}
          >
            <div className="text-2xl font-bold text-red-600 dark:text-red-400">
              {playlist.unavailable_count}
            </div>
            <div className="text-xs text-gray-600 dark:text-gray-400">Unavailable</div>
          </div>
        </div>

        {/* Status Message */}
        <div className="mb-4 text-sm font-medium">
          {isCaughtUp ? (
            <span className="text-green-600 dark:text-green-400 flex items-center gap-1">
              ✓ Caught up
            </span>
          ) : (
            <span className="text-orange-600 dark:text-orange-400 flex items-center gap-1">
              ! {pendingCount} new video{pendingCount === 1 ? '' : 's'}
            </span>
          )}
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
            onEditExclusions={() => onEditExclusions(playlist)}
            isRefreshing={isRefreshing}
            isCancelling={isCancelling}
          />
        </div>

        {/* Last Activity & Exclusions */}
        <div className="mt-3 text-xs text-gray-500 dark:text-gray-400 space-y-1">
          {playlist.last_download && (
            <div>Last download: {new Date(playlist.last_download).toLocaleString()}</div>
          )}
          {playlist.last_extract && (
            <div>Last extract: {new Date(playlist.last_extract).toLocaleString()}</div>
          )}
          <div className="flex items-center justify-between pt-1 border-t border-gray-100 dark:border-gray-700/50">
            <span>
              {playlist.excluded_ids?.length || 0} excluded
              {playlist.unavailable_count > 0 ? ` • ${playlist.unavailable_count} unavailable` : ''}
            </span>
            <button
              onClick={() => onEditExclusions(playlist)}
              className="text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300 flex items-center gap-1 font-medium"
              title="Manage exclusions"
            >
              <Edit3 className="w-3 h-3" />
              Exclusions
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
