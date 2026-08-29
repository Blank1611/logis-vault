import React from 'react'
import type { Playlist, Job } from '../../services/types'
import { PlaylistCard } from './PlaylistCard'

export interface PlaylistGridProps {
  playlists: Playlist[]
  jobs: Job[]
  isScanning?: boolean
  currentScanningPlaylist?: string | null
  onStartJob: (playlistId: number, jobType: 'download' | 'extract' | 'both') => void
  onCancelJob: (jobId: number) => void
  onRefresh: (playlistId: number) => void
  onDelete: (playlistId: number) => void
  onOpenFolder: (playlistId: number) => void
  onEditExclusions: (playlist: Playlist) => void
  refreshingPlaylistId?: number | null
  cancellingJobId?: number | null
  openFolderPlaylistId?: number | null
}

export const PlaylistGrid: React.FC<PlaylistGridProps> = ({
  playlists,
  jobs,
  isScanning,
  currentScanningPlaylist,
  onStartJob,
  onCancelJob,
  onRefresh,
  onDelete,
  onOpenFolder,
  onEditExclusions,
  refreshingPlaylistId,
  cancellingJobId,
  openFolderPlaylistId,
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
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
      {sortedPlaylists.map((playlist) => {
        const runningJob = getRunningJob(playlist.id)
        return (
          <PlaylistCard
            key={playlist.id}
            playlist={playlist}
            runningJob={runningJob}
            isScanning={isScanning}
            currentScanningPlaylist={currentScanningPlaylist}
            onStartJob={onStartJob}
            onCancelJob={onCancelJob}
            onRefresh={onRefresh}
            onDelete={onDelete}
            onOpenFolder={onOpenFolder}
            onEditExclusions={onEditExclusions}
            isRefreshing={refreshingPlaylistId === playlist.id}
            isCancelling={runningJob ? cancellingJobId === runningJob.id : false}
            isOpenFolderPending={openFolderPlaylistId === playlist.id}
          />
        )
      })}
    </div>
  )
}
