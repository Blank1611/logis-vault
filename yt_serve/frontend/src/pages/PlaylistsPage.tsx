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
        <div className="flex flex-col sm:flex-row items-center justify-between gap-3 mb-6 glass-panel p-3.5 rounded-2xl border border-white/10 shadow-lg">
          <div className="text-xs font-semibold text-slate-300 flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-cyan-400"></span>
            <span>{playlists.length} {playlists.length === 1 ? 'Playlist' : 'Playlists'} Total</span>
          </div>

          <div className="flex items-center gap-2.5">
            {/* Track Index Button */}
            {onOpenReorganize && (
              <button
                onClick={onOpenReorganize}
                className="px-3.5 py-1.5 rounded-xl bg-slate-900/70 hover:bg-slate-800/90 border border-white/10 hover:border-cyan-500/40 text-slate-200 hover:text-cyan-300 transition-all flex items-center gap-1.5 text-xs font-semibold shadow-xs backdrop-blur-md cursor-pointer"
                title="Track Index & Inter-Playlist Reorganization Manager"
              >
                <Layers className="w-3.5 h-3.5 text-cyan-400" />
                <span>Track Index</span>
              </button>
            )}

            {/* Deduplicate Button */}
            {onOpenDeduplicate && (
              <button
                onClick={onOpenDeduplicate}
                className="px-3.5 py-1.5 rounded-xl bg-slate-900/70 hover:bg-slate-800/90 border border-white/10 hover:border-purple-500/40 text-slate-200 hover:text-purple-300 transition-all flex items-center gap-1.5 text-xs font-semibold shadow-xs backdrop-blur-md cursor-pointer"
                title="Retroactive Library Deduplication & Hardlink Space Reclaimer"
              >
                <Sparkles className="w-3.5 h-3.5 text-purple-400" />
                <span>Deduplicate</span>
              </button>
            )}

            {/* View Mode Toggle (Grid / List) */}
            {onViewModeChange && (
              <div className="flex gap-1 p-1 rounded-xl bg-slate-900/80 border border-white/10">
                <button
                  onClick={() => onViewModeChange('grid')}
                  className={`p-1.5 rounded-lg transition-all ${
                    viewMode === 'grid'
                      ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shadow-xs'
                      : 'text-slate-400 hover:text-white'
                  }`}
                  title="Grid View"
                >
                  <Grid3x3 className="w-4 h-4" />
                </button>
                <button
                  onClick={() => onViewModeChange('list')}
                  className={`p-1.5 rounded-lg transition-all ${
                    viewMode === 'list'
                      ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shadow-xs'
                      : 'text-slate-400 hover:text-white'
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
