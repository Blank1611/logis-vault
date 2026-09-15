import React from 'react'
import type { Playlist, Job } from '../services/types'
import { AddPlaylistBar } from '../components/playlists/AddPlaylistBar'
import { PlaylistGrid } from '../components/playlists/PlaylistGrid'
import { PlaylistList } from '../components/playlists/PlaylistList'
import { Loader2, Grid3x3, List, Layers, Sparkles } from 'lucide-react'

export interface PlaylistsPageProps {
  playlists: Playlist[]
  jobs: Job[]
  isLoading: boolean
  viewMode: 'grid' | 'list'
  onViewModeChange?: (mode: 'grid' | 'list') => void
  onOpenReorganize?: () => void
  onOpenDeduplicate?: () => void
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
  onViewModeChange,
  onOpenReorganize,
  onOpenDeduplicate,
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

      {/* Playlist View & Management Toolbar */}
      {!isLoading && playlists.length > 0 && (
        <div className="flex flex-col sm:flex-row items-center justify-between gap-3 mb-6 bg-white dark:bg-gray-800/60 p-3 rounded-xl border border-gray-200/80 dark:border-gray-700/80 shadow-xs">
          <div className="text-xs font-semibold text-gray-500 dark:text-gray-400">
            <span>{playlists.length} {playlists.length === 1 ? 'Playlist' : 'Playlists'} Total</span>
          </div>

          <div className="flex items-center gap-2">
            {/* Track Index Button */}
            {onOpenReorganize && (
              <button
                onClick={onOpenReorganize}
                className="px-3 py-1.5 rounded-lg bg-gray-100 hover:bg-gray-200 dark:bg-gray-700 dark:hover:bg-gray-600 border border-gray-200 dark:border-gray-600 transition-colors flex items-center gap-1.5 text-xs font-semibold text-gray-700 dark:text-gray-200 shadow-2xs"
                title="Track Index & Inter-Playlist Reorganization Manager"
              >
                <Layers className="w-3.5 h-3.5 text-blue-600 dark:text-blue-400" />
                <span>Track Index</span>
              </button>
            )}

            {/* Deduplicate Button */}
            {onOpenDeduplicate && (
              <button
                onClick={onOpenDeduplicate}
                className="px-3 py-1.5 rounded-lg bg-gray-100 hover:bg-gray-200 dark:bg-gray-700 dark:hover:bg-gray-600 border border-gray-200 dark:border-gray-600 transition-colors flex items-center gap-1.5 text-xs font-semibold text-gray-700 dark:text-gray-200 shadow-2xs"
                title="Retroactive Library Deduplication & Hardlink Space Reclaimer"
              >
                <Sparkles className="w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400" />
                <span>Deduplicate</span>
              </button>
            )}

            {/* View Mode Toggle (Grid / List) */}
            {onViewModeChange && (
              <div className="flex gap-1 p-1 rounded-lg bg-gray-100 dark:bg-gray-700/60 border border-gray-200 dark:border-gray-600">
                <button
                  onClick={() => onViewModeChange('grid')}
                  className={`p-1.5 rounded transition-colors ${
                    viewMode === 'grid'
                      ? 'bg-white dark:bg-gray-600 text-blue-600 dark:text-blue-400 shadow-2xs'
                      : 'text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
                  }`}
                  title="Grid View"
                >
                  <Grid3x3 className="w-4 h-4" />
                </button>
                <button
                  onClick={() => onViewModeChange('list')}
                  className={`p-1.5 rounded transition-colors ${
                    viewMode === 'list'
                      ? 'bg-white dark:bg-gray-600 text-blue-600 dark:text-blue-400 shadow-2xs'
                      : 'text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
                  }`}
                  title="List View"
                >
                  <List className="w-4 h-4" />
                </button>
              </div>
            )}
          </div>
        </div>
      )}

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
