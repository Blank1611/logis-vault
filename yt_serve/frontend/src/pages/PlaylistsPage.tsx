import React from 'react'
import type { Playlist, Job } from '../services/types'
import { AddPlaylistBar } from '../components/playlists/AddPlaylistBar'
import { PlaylistGrid } from '../components/playlists/PlaylistGrid'
import { PlaylistList } from '../components/playlists/PlaylistList'
import { Loader2 } from 'lucide-react'

export interface PlaylistsPageProps {
  playlists: Playlist[]
  jobs: Job[]
  isLoading: boolean
  viewMode: 'grid' | 'list'
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
  openFolderPlaylistId?: number | null
}

export const PlaylistsPage: React.FC<PlaylistsPageProps> = ({
  playlists,
  jobs,
  isLoading,
  viewMode,
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
  openFolderPlaylistId,
}) => {
  return (
    <>
      {/* Add Playlist Input Bar */}
      <AddPlaylistBar />

      {/* Main Playlists Content */}
      {isLoading ? (
        <div className="text-center py-16">
          <Loader2 className="w-8 h-8 animate-spin mx-auto text-blue-600 mb-2" />
          <p className="text-sm text-gray-600 dark:text-gray-400">Loading playlists...</p>
        </div>
      ) : viewMode === 'grid' ? (
        <PlaylistGrid
          playlists={playlists}
          jobs={jobs}
          isScanning={isScanning}
          currentScanningPlaylist={currentScanningPlaylist}
          onStartJob={onStartJob}
          onCancelJob={onCancelJob}
          onRefresh={onRefresh}
          onDelete={onDelete}
          onOpenFolder={onOpenFolder}
          onEditExclusions={onEditExclusions}
          refreshingPlaylistId={refreshingPlaylistId}
          cancellingJobId={cancellingJobId}
          openFolderPlaylistId={openFolderPlaylistId}
        />
      ) : (
        <PlaylistList
          playlists={playlists}
          jobs={jobs}
          expandedRows={expandedRows}
          onToggleRow={onToggleRow}
          isScanning={isScanning}
          currentScanningPlaylist={currentScanningPlaylist}
          onStartJob={onStartJob}
          onCancelJob={onCancelJob}
          onRefresh={onRefresh}
          onDelete={onDelete}
          onOpenFolder={onOpenFolder}
          onEditExclusions={onEditExclusions}
          onViewLogs={onViewLogs}
          refreshingPlaylistId={refreshingPlaylistId}
          cancellingJobId={cancellingJobId}
        />
      )}

      {/* Empty State */}
      {!isLoading && playlists.length === 0 && (
        <div className="text-center py-16 text-gray-500 dark:text-gray-400 bg-white dark:bg-gray-800/40 rounded-xl border border-dashed border-gray-300 dark:border-gray-700 p-8">
          <p className="font-medium text-base">No playlists added yet</p>
          <p className="text-sm mt-1">Paste a YouTube playlist URL in the box above to get started!</p>
        </div>
      )}
    </>
  )
}
