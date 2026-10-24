import React from 'react'
import type { Playlist, Job } from '../../services/types'
import { Button } from '../ui/Button'
import { PlayCircle, Download, Music, RefreshCw, Trash2 } from 'lucide-react'
import { useConfirm } from '../../context/ConfirmContext'

export interface PlaylistActionsProps {
  playlist: Playlist
  runningJob?: Job
  isRefreshing?: boolean
  isCancelling?: boolean
  isOpeningFolder?: boolean
  isScanning?: boolean
  currentScanningPlaylist?: string | null
  compact?: boolean
  onStartJob: (type: 'download' | 'extract' | 'both') => void
  onCancelJob: (jobId: number) => void
  onRefresh: () => void
  onDelete: () => void
  onOpenFolder?: () => void
  onEditExclusions?: () => void
}

export const PlaylistActions: React.FC<PlaylistActionsProps> = ({
  playlist,
  runningJob,
  isRefreshing = false,
  isCancelling = false,
  isOpeningFolder: _isOpeningFolder = false,
  isScanning = false,
  currentScanningPlaylist = null,
  compact = false,
  onStartJob,
  onCancelJob,
  onRefresh,
  onDelete,
  onOpenFolder: _onOpenFolder = () => {},
  onEditExclusions: _onEditExclusions,
}) => {
  const confirm = useConfirm()
  const isCaughtUp = playlist.local_count >= playlist.playlist_count && playlist.playlist_count > 0

  if (runningJob) {
    return (
      <Button
        variant="danger"
        size={compact ? 'sm' : 'md'}
        onClick={async () => {
          const ok = await confirm({
            title: 'Cancel Download Job',
            message: 'Cancel this job? The current video download will complete first.',
            confirmText: 'Cancel Job',
            isDestructive: true,
          })
          if (ok) {
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
    <div className={`flex items-center gap-1.5 ${compact ? 'flex-wrap' : 'w-full'}`}>
      {/* 1. Download & Extract (Blue) */}
      <button
        type="button"
        onClick={() => onStartJob('both')}
        disabled={isCaughtUp || isScanning}
        title={
          isScanning
            ? 'Daily scheduled scan is currently in progress. Please wait for it to complete.'
            : isCaughtUp
            ? 'All available videos already downloaded'
            : 'Download and extract all missing tracks'
        }
        className={`flex items-center justify-center gap-1.5 font-bold rounded-lg transition-all text-xs text-white ${
          compact ? 'px-3 py-1.5' : 'flex-[2.5] py-2 px-3'
        } ${
          isCaughtUp || isScanning
            ? 'bg-gray-700/60 text-gray-400 cursor-not-allowed border border-white/5 opacity-40'
            : 'bg-blue-600 hover:bg-blue-500 shadow-md shadow-blue-600/30 active:scale-95'
        }`}
      >
        <PlayCircle className="w-4 h-4 shrink-0" />
        <span className="truncate">Download & Extract</span>
      </button>

      {/* 2. Download Only (Green) */}
      <button
        type="button"
        onClick={() => onStartJob('download')}
        disabled={isCaughtUp || isScanning}
        title={
          isScanning
            ? 'Daily scheduled scan is currently in progress. Please wait for it to complete.'
            : isCaughtUp
            ? 'All available videos already downloaded'
            : 'Download videos only without audio extraction'
        }
        className={`flex items-center justify-center font-bold rounded-lg transition-all text-xs text-white ${
          compact ? 'px-3 py-1.5 gap-1.5' : 'p-2'
        } ${
          isCaughtUp || isScanning
            ? 'bg-gray-700/60 text-gray-400 cursor-not-allowed border border-white/5 opacity-40'
            : 'bg-emerald-600 hover:bg-emerald-500 shadow-md shadow-emerald-600/30 active:scale-95'
        }`}
      >
        <Download className="w-4 h-4 shrink-0" />
        {compact && <span>Download Only</span>}
      </button>

      {/* 3. Extract Audio (Magenta / Purple) - Remains enabled even when caught up! */}
      <button
        type="button"
        onClick={() => onStartJob('extract')}
        disabled={isScanning}
        title={
          isScanning
            ? 'Daily scheduled scan is currently in progress. Please wait for it to complete.'
            : 'Extract Audio Only (Direct stream copy or transcode)'
        }
        className={`flex items-center justify-center font-bold rounded-lg transition-all text-xs text-white ${
          compact ? 'px-3 py-1.5 gap-1.5' : 'p-2'
        } ${
          isScanning
            ? 'bg-gray-700/60 text-gray-400 cursor-not-allowed opacity-40'
            : 'bg-fuchsia-600 hover:bg-fuchsia-500 shadow-md shadow-fuchsia-600/30 active:scale-95'
        }`}
      >
        <Music className="w-4 h-4 shrink-0" />
        {compact && <span>Extract</span>}
      </button>

      {/* 4. Refresh Metadata (Slate / Gray) */}
      <button
        type="button"
        onClick={onRefresh}
        disabled={isRefreshing || isScanning}
        title={
          isScanning
            ? 'Daily background auto-scan is currently in progress. Please wait for it to complete.'
            : isRefreshing
            ? 'Refreshing playlist metadata...'
            : 'Refresh playlist metadata and check for new tracks'
        }
        className={`flex items-center justify-center font-bold rounded-lg transition-all text-xs text-white ${
          compact ? 'px-3 py-1.5 gap-1.5' : 'p-2'
        } ${
          isRefreshing || isScanning
            ? 'bg-gray-700/60 text-gray-400 cursor-not-allowed opacity-40'
            : 'bg-slate-700 hover:bg-slate-600 active:scale-95'
        }`}
      >
        <RefreshCw
          className={`w-4 h-4 shrink-0 ${
            isRefreshing || isCurrentScanning ? 'animate-spin text-blue-400' : ''
          }`}
        />
        {compact && <span>Refresh</span>}
      </button>

      {/* 5. Delete / Remove Playlist (Red) */}
      <button
        type="button"
        onClick={async () => {
          const ok = await confirm({
            title: `Remove "${playlist.title}"`,
            message:
              'Remove this playlist entry from the database?\n\nDownloaded files and folders on disk will remain 100% intact.',
            confirmText: 'Remove Playlist',
            isDestructive: true,
          })
          if (ok) {
            onDelete()
          }
        }}
        title="Remove playlist entry (files stay intact)"
        className={`flex items-center justify-center font-bold rounded-lg transition-all text-xs text-white bg-rose-700 hover:bg-rose-600 active:scale-95 ${
          compact ? 'px-3 py-1.5 gap-1.5' : 'p-2'
        }`}
      >
        <Trash2 className="w-4 h-4 shrink-0" />
        {compact && <span>Remove</span>}
      </button>
    </div>
  )
}
