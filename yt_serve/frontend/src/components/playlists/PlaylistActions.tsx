import React from 'react'
import type { Playlist, Job } from '../../services/types'
import { Button } from '../ui/Button'
import { PlayCircle, Download, Music, RefreshCw, Trash2, Edit3 } from 'lucide-react'

export interface PlaylistActionsProps {
  playlist: Playlist
  runningJob?: Job
  isScanning?: boolean
  currentScanningPlaylist?: string | null
  onStartJob: (jobType: 'download' | 'extract' | 'both') => void
  onCancelJob: (jobId: number) => void
  onRefresh: () => void
  onDelete: () => void
  onEditExclusions?: () => void
  isRefreshing?: boolean
  isCancelling?: boolean
  compact?: boolean
}

export const PlaylistActions: React.FC<PlaylistActionsProps> = ({
  playlist,
  runningJob,
  isScanning = false,
  currentScanningPlaylist,
  onStartJob,
  onCancelJob,
  onRefresh,
  onDelete,
  onEditExclusions,
  isRefreshing = false,
  isCancelling = false,
  compact = false,
}) => {
  const isCaughtUp = playlist.local_count >= playlist.playlist_count && playlist.playlist_count > 0

  if (runningJob) {
    return (
      <Button
        variant="danger"
        size={compact ? 'sm' : 'md'}
        onClick={() => {
          if (confirm('Cancel this job? The current video download will complete first.')) {
            onCancelJob(runningJob.id)
          }
        }}
        loading={isCancelling}
        className={compact ? 'w-auto' : 'flex-1'}
      >
        Cancel Job
      </Button>
    )
  }

  const isCurrentScanning = isScanning && currentScanningPlaylist === playlist.title

  return (
    <div className={`flex items-center gap-2 ${compact ? 'flex-wrap' : 'w-full'}`}>
      <Button
        variant="primary"
        size={compact ? 'sm' : 'md'}
        onClick={() => onStartJob('both')}
        disabled={isCaughtUp || isScanning}
        icon={<PlayCircle className="w-4 h-4" />}
        className={compact ? '' : 'flex-[2]'}
        title={
          isScanning
            ? 'Daily scheduled scan is currently in progress. Please wait for it to complete.'
            : isCaughtUp
            ? 'All available videos already downloaded'
            : 'Download and extract all missing tracks'
        }
      >
        {compact ? 'Download & Extract' : 'Download'}
      </Button>

      {compact && (
        <Button
          variant="success"
          size="sm"
          onClick={() => onStartJob('download')}
          disabled={isCaughtUp || isScanning}
          icon={<Download className="w-4 h-4" />}
          title={
            isScanning
              ? 'Daily scheduled scan is currently in progress. Please wait for it to complete.'
              : 'Download videos only without extraction'
          }
        >
          Download Only
        </Button>
      )}

      <Button
        variant="secondary"
        size={compact ? 'sm' : 'md'}
        onClick={() => onStartJob('extract')}
        disabled={isScanning}
        icon={<Music className="w-4 h-4 text-purple-600 dark:text-purple-400" />}
        title={
          isScanning
            ? 'Daily scheduled scan is currently in progress. Please wait for it to complete.'
            : 'Extract Audio Only'
        }
        className={compact ? '' : 'px-3'}
      >
        {compact ? 'Extract' : ''}
      </Button>

      <Button
        variant="secondary"
        size={compact ? 'sm' : 'md'}
        onClick={onRefresh}
        disabled={isRefreshing || isScanning}
        icon={
          <RefreshCw
            className={`w-4 h-4 ${
              isRefreshing || isCurrentScanning ? 'animate-spin text-blue-500' : ''
            }`}
          />
        }
        title={
          isScanning
            ? 'Daily background auto-scan is currently in progress. Please wait for it to complete.'
            : isRefreshing
            ? 'Refreshing playlist metadata...'
            : 'Refresh playlist metadata and check for new tracks'
        }
        className={compact ? '' : 'px-3'}
      >
        {compact ? 'Refresh' : ''}
      </Button>

      {onEditExclusions && (
        <Button
          variant="secondary"
          size={compact ? 'sm' : 'md'}
          onClick={onEditExclusions}
          icon={<Edit3 className="w-4 h-4 text-amber-600 dark:text-amber-400" />}
          title={
            playlist.excluded_ids?.length
              ? `Manage exclusions (${playlist.excluded_ids.length} currently excluded)`
              : 'Manage video exclusions'
          }
          className={compact ? '' : 'px-3'}
        >
          {compact ? `Exclusions ${playlist.excluded_ids?.length ? `(${playlist.excluded_ids.length})` : ''}` : ''}
        </Button>
      )}

      <Button
        variant="ghost"
        size={compact ? 'sm' : 'md'}
        onClick={() => {
          if (
            confirm(
              `Remove "${playlist.title}" from manager?\n\n` +
              'This will only remove the playlist entry from the database.\n' +
              'Downloaded files and folders will remain intact.'
            )
          ) {
            onDelete()
          }
        }}
        icon={<Trash2 className="w-4 h-4 text-rose-600 dark:text-rose-400" />}
        title="Remove playlist entry (files stay intact)"
        className="px-3 hover:bg-rose-50 dark:hover:bg-rose-900/30"
      >
        {compact ? 'Remove' : ''}
      </Button>
    </div>
  )
}
