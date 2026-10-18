import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { 
  housekeepingApi, playlistsApi, 
  type DeduplicationScanResult 
} from '../../services/api'
import type { Playlist, PlaylistTrack } from '../../services/types'
import { Modal } from '../ui/Modal'
import { Button } from '../ui/Button'
import { 
  Sparkles, RefreshCw, HardDrive, Check, Loader2, Music, Search, ShieldCheck, 
  Trash2, Star, Layers, Film
} from 'lucide-react'
import { useConfirm } from '../../context/ConfirmContext'
import { useToast } from '../../context/ToastContext'

export interface DeduplicateModalProps {
  isOpen: boolean
  onClose: () => void
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
}

export const DeduplicateModal: React.FC<DeduplicateModalProps> = ({ isOpen, onClose }) => {
  const queryClient = useQueryClient()
  const confirm = useConfirm()
  const { toast } = useToast()
  const [modalTab, setModalTab] = useState<'hardlinks' | 'quality_versions'>('hardlinks')
  const [searchTerm, setSearchTerm] = useState('')
  const [selectedPlaylistId, setSelectedPlaylistId] = useState<number | 'all'>('all')
  const [selectedTrackIds, setSelectedTrackIds] = useState<Set<string>>(new Set())
  const [isDeletingVersions, setIsDeletingVersions] = useState(false)

  // 1. Fetch library duplicate scan for hardlinks
  const { data: scanData, isLoading: isScanning, refetch: rescan } = useQuery<DeduplicationScanResult>({
    queryKey: ['deduplicate-scan'],
    queryFn: async () => {
      const res = await housekeepingApi.scanDuplicates()
      return res.data
    },
    enabled: isOpen && modalTab === 'hardlinks',
    staleTime: 60000,
  })

  // 2. Fetch playlists for quality versions cleanup
  const { data: playlists = [] } = useQuery<Playlist[]>({
    queryKey: ['playlists'],
    queryFn: async () => {
      const res = await playlistsApi.list()
      return res.data
    },
    enabled: isOpen,
  })

  // 3. Fetch tracks for quality versions cleanup
  const { data: allTracks = [], isLoading: isLoadingTracks, refetch: refetchTracks } = useQuery<PlaylistTrack[]>({
    queryKey: ['quality-versions-tracks', selectedPlaylistId],
    queryFn: async () => {
      if (selectedPlaylistId === 'all') {
        const trackPromises = playlists.map(p => playlistsApi.getTracks(p.id).then(r => r.data).catch(() => []))
        const results = await Promise.all(trackPromises)
        // Flatten and deduplicate by video_id
        const map = new Map<string, PlaylistTrack>()
        results.flat().forEach(t => map.set(t.video_id, t))
        return Array.from(map.values())
      } else {
        const res = await playlistsApi.getTracks(selectedPlaylistId)
        return res.data
      }
    },
    enabled: isOpen && modalTab === 'quality_versions' && playlists.length > 0,
  })

  // 5. Hardlink conversion mutation
  const applyMutation = useMutation({
    mutationFn: async () => {
      const res = await housekeepingApi.applyDeduplication({
        duplicate_groups: scanData?.duplicate_groups,
      })
      return res.data
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['deduplicate-scan'] })
      queryClient.invalidateQueries({ queryKey: ['track-index'] })
      toast.success(`Successfully converted ${data?.files_converted || 0} duplicates into hardlinks!`)
    },
  })

  const groups = scanData?.duplicate_groups || []
  const filteredGroups = groups.filter(g => 
    g.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
    g.video_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
    g.playlists.some(p => p.toLowerCase().includes(searchTerm.toLowerCase()))
  )

  // Tracks with multiple resolution versions on disk
  const multiVersionTracks = allTracks.filter(t => 
    (t.disk_versions && t.disk_versions.length > 1) || 
    (t.downloaded_resolutions && t.downloaded_resolutions.length > 1)
  )

  const filteredMultiTracks = multiVersionTracks.filter(t => 
    t.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
    t.video_id.toLowerCase().includes(searchTerm.toLowerCase())
  )

  const handleApplyHardlinks = async () => {
    if (!scanData || scanData.total_duplicate_files === 0) return
    const ok = await confirm({
      title: 'Deduplicate Files',
      message: `Convert ${scanData.total_duplicate_files} duplicate files into zero-space NTFS/ext4 hardlinks?\n\nThis will safely reclaim ~${scanData.formatted_reclaimable_space} of physical disk space while keeping all songs playable in their playlists.`,
      confirmText: 'Convert to Hardlinks',
      isDestructive: false,
    })
    if (ok) {
      applyMutation.mutate()
    }
  }

  const handleSetPrimary = async (playlistId: number, videoId: string, resolution: string) => {
    try {
      await playlistsApi.setPrimaryVersion(playlistId, videoId, resolution)
      toast.success(`Set ${resolution} as primary copy`)
      refetchTracks()
    } catch (err: any) {
      toast.error(`Failed to set primary: ${err.message}`)
    }
  }

  const handleDeleteVersion = async (playlistId: number, videoId: string, resolution: string) => {
    const ok = await confirm({
      title: 'Delete Quality Copy',
      message: `Are you sure you want to permanently delete the ${resolution} file for this video from disk?`,
      confirmText: 'Delete Copy',
      isDestructive: true,
    })
    if (!ok) return

    try {
      await playlistsApi.deleteTrackVersion(playlistId, videoId, resolution)
      toast.success(`Deleted ${resolution} version`)
      refetchTracks()
    } catch (err: any) {
      toast.error(`Failed to delete version: ${err.message}`)
    }
  }

  const handleDeleteAllOlderVersions = async () => {
    const targets = filteredMultiTracks.filter(t => selectedTrackIds.size === 0 || selectedTrackIds.has(t.video_id))
    if (targets.length === 0) return

    const ok = await confirm({
      title: 'Batch Clean Older Quality Copies',
      message: `Permanently delete all secondary / older resolution copies for ${targets.length} video(s), keeping only the primary resolution file?`,
      confirmText: 'Delete Older Copies',
      isDestructive: true,
    })
    if (!ok) return

    setIsDeletingVersions(true)
    let deletedCount = 0
    try {
      for (const track of targets) {
        const plId = (selectedPlaylistId !== 'all') ? selectedPlaylistId : (playlists[0]?.id || 1)
        const primaryRes = track.primary_resolution || (track.disk_versions[0]?.resolution)
        for (const v of track.disk_versions) {
          if (v.resolution !== primaryRes) {
            try {
              await playlistsApi.deleteTrackVersion(plId, track.video_id, v.resolution)
              deletedCount++
            } catch (e) {
              console.error(e)
            }
          }
        }
      }
      toast.success(`Cleaned up ${deletedCount} older video versions!`)
      setSelectedTrackIds(new Set())
      refetchTracks()
    } finally {
      setIsDeletingVersions(false)
    }
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={
        <span className="flex items-center gap-2">
          <HardDrive className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
          <span>Storage Management & Redundancy Cleanup</span>
        </span>
      }
      subtitle="Clean redundant file copies, manage multi-resolution tracks, or hardlink identical songs across playlists."
      maxWidth="4xl"
    >
      <div className="space-y-4 py-2">
        {/* Tab Switcher */}
        <div className="flex border-b border-gray-200 dark:border-gray-700 gap-4">
          <button
            onClick={() => setModalTab('hardlinks')}
            className={`pb-2.5 text-xs font-bold border-b-2 flex items-center gap-1.5 transition-all ${
              modalTab === 'hardlinks'
                ? 'border-indigo-600 text-indigo-600 dark:text-indigo-400'
                : 'border-transparent text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'
            }`}
          >
            <Layers className="w-4 h-4" />
            <span>Cross-Playlist Inode Hardlinks</span>
          </button>
          <button
            onClick={() => setModalTab('quality_versions')}
            className={`pb-2.5 text-xs font-bold border-b-2 flex items-center gap-1.5 transition-all ${
              modalTab === 'quality_versions'
                ? 'border-indigo-600 text-indigo-600 dark:text-indigo-400'
                : 'border-transparent text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'
            }`}
          >
            <Film className="w-4 h-4" />
            <span>Multi-Quality Versions Cleanup</span>
            {multiVersionTracks.length > 0 && (
              <span className="px-1.5 py-0.2 bg-amber-500 text-white rounded-full text-[10px]">
                {multiVersionTracks.length}
              </span>
            )}
          </button>
        </div>

        {/* Tab 1: Cross-Playlist Hardlinks */}
        {modalTab === 'hardlinks' && (
          <div className="space-y-4">
            <div className="bg-indigo-50 dark:bg-indigo-950/30 border border-indigo-200 dark:border-indigo-800 rounded-xl p-3.5 flex items-start gap-3">
              <ShieldCheck className="w-5 h-5 text-indigo-600 dark:text-indigo-400 shrink-0 mt-0.5" />
              <div className="text-xs text-indigo-900 dark:text-indigo-200 space-y-1">
                <p className="font-semibold">Zero-Space Inode Hardlinking</p>
                <p className="text-indigo-700 dark:text-indigo-300">
                  Converting duplicates to hardlinks creates direct pointers to the same physical disk sector. Each song remains in its playlist folder, but redundant copies consume <strong>0 MB</strong> extra hard drive space.
                </p>
              </div>
            </div>

            {isScanning ? (
              <div className="py-12 flex flex-col items-center justify-center gap-3 text-center">
                <Loader2 className="w-8 h-8 animate-spin text-indigo-600" />
                <p className="text-sm font-semibold text-gray-700 dark:text-gray-300">
                  Scanning library folders for duplicate media files...
                </p>
              </div>
            ) : (
              <>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  <div className="bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-800 rounded-xl p-3 text-center">
                    <span className="text-[11px] font-bold text-emerald-700 dark:text-emerald-300 uppercase tracking-wider">
                      Space Reclaimable
                    </span>
                    <p className="text-2xl font-black text-emerald-600 dark:text-emerald-400 font-mono mt-0.5">
                      {scanData?.formatted_reclaimable_space || '0 B'}
                    </p>
                  </div>
                  <div className="bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800 rounded-xl p-3 text-center">
                    <span className="text-[11px] font-bold text-blue-700 dark:text-blue-300 uppercase tracking-wider">
                      Redundant Files
                    </span>
                    <p className="text-2xl font-black text-blue-600 dark:text-blue-400 font-mono mt-0.5">
                      {scanData?.total_duplicate_files || 0}
                    </p>
                  </div>
                  <div className="bg-purple-50 dark:bg-purple-950/30 border border-purple-200 dark:border-purple-800 rounded-xl p-3 text-center">
                    <span className="text-[11px] font-bold text-purple-700 dark:text-purple-300 uppercase tracking-wider">
                      Duplicate Tracks
                    </span>
                    <p className="text-2xl font-black text-purple-600 dark:text-purple-400 font-mono mt-0.5">
                      {scanData?.duplicate_groups_count || 0}
                    </p>
                  </div>
                </div>

                <div className="flex flex-col sm:flex-row items-center justify-between gap-3">
                  <div className="relative flex-1 w-full">
                    <Search className="w-4 h-4 absolute left-3 top-2.5 text-gray-400" />
                    <input
                      type="text"
                      placeholder="Filter duplicate songs..."
                      value={searchTerm}
                      onChange={(e) => setSearchTerm(e.target.value)}
                      className="w-full pl-9 pr-3.5 py-1.5 border border-gray-300 dark:border-gray-600 rounded-lg text-xs bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                    />
                  </div>
                  <div className="flex items-center gap-2 w-full sm:w-auto">
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => rescan()}
                      disabled={isScanning || applyMutation.isPending}
                      className="flex items-center gap-1.5"
                    >
                      <RefreshCw className="w-3.5 h-3.5" />
                      <span>Rescan</span>
                    </Button>
                    <Button
                      variant="primary"
                      size="sm"
                      onClick={handleApplyHardlinks}
                      disabled={isScanning || applyMutation.isPending || (scanData?.total_duplicate_files || 0) === 0}
                      className="flex items-center gap-1.5 bg-indigo-600 hover:bg-indigo-700"
                    >
                      {applyMutation.isPending ? (
                        <>
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          <span>Reclaiming Space...</span>
                        </>
                      ) : (
                        <>
                          <Sparkles className="w-3.5 h-3.5" />
                          <span>Reclaim Space Now</span>
                        </>
                      )}
                    </Button>
                  </div>
                </div>

                {filteredGroups.length === 0 ? (
                  <div className="py-10 text-center border border-dashed border-gray-300 dark:border-gray-700 rounded-xl">
                    <Check className="w-8 h-8 text-emerald-500 mx-auto mb-2" />
                    <p className="text-sm font-semibold text-gray-700 dark:text-gray-300">
                      {groups.length === 0
                        ? 'Your library is 100% deduplicated! No redundant physical files found.'
                        : 'No duplicate songs matched your filter.'}
                    </p>
                  </div>
                ) : (
                  <div className="border border-gray-200 dark:border-gray-700 rounded-xl overflow-hidden max-h-80 overflow-y-auto">
                    <table className="w-full text-left text-xs text-gray-700 dark:text-gray-300">
                      <thead className="bg-gray-100 dark:bg-gray-800 text-[11px] uppercase font-bold text-gray-600 dark:text-gray-400 sticky top-0">
                        <tr>
                          <th className="px-3.5 py-2.5">Duplicate Track</th>
                          <th className="px-3.5 py-2.5">Primary Playlist</th>
                          <th className="px-3.5 py-2.5">Redundant Copies</th>
                          <th className="px-3.5 py-2.5 text-right">Reclaimable</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-200 dark:divide-gray-700/60 bg-white dark:bg-gray-900/60">
                        {filteredGroups.map((g) => (
                          <tr key={g.video_id} className="hover:bg-gray-50 dark:hover:bg-gray-800/40">
                            <td className="px-3.5 py-2.5 font-semibold text-gray-900 dark:text-white max-w-xs truncate">
                              <div className="flex items-center gap-1.5">
                                <Music className="w-3.5 h-3.5 text-indigo-500 shrink-0" />
                                <span title={g.title}>{g.title}</span>
                              </div>
                              <span className="text-[10px] text-gray-400 font-mono pl-5">
                                {g.video_id} • {g.media_type}
                              </span>
                            </td>
                            <td className="px-3.5 py-2.5">
                              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium bg-gray-100 dark:bg-gray-800 text-gray-800 dark:text-gray-300">
                                {g.master_file.playlist_folder}
                              </span>
                            </td>
                            <td className="px-3.5 py-2.5 space-y-1">
                              {g.redundant_copies.map((r, rIdx) => (
                                <span
                                  key={rIdx}
                                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium bg-amber-50 dark:bg-amber-950/40 text-amber-800 dark:text-amber-300 border border-amber-200 dark:border-amber-800 mr-1 mb-0.5"
                                >
                                  {r.playlist_folder}
                                </span>
                              ))}
                            </td>
                            <td className="px-3.5 py-2.5 text-right font-mono font-bold text-emerald-600 dark:text-emerald-400">
                              +{g.formatted_reclaimable_space}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </>
            )}
          </div>
        )}

        {/* Tab 2: Quality Versions Cleanup */}
        {modalTab === 'quality_versions' && (
          <div className="space-y-4">
            <div className="bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 rounded-xl p-3.5 flex items-start gap-3">
              <Film className="w-5 h-5 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
              <div className="text-xs text-amber-900 dark:text-amber-200 space-y-1">
                <p className="font-semibold">Side-by-Side Quality Version Management</p>
                <p className="text-amber-700 dark:text-amber-300">
                  When upgrading a track (e.g. from 720p to 1080p), both copies are preserved for inspection. Here you can set the primary copy (e.g. keeping 720p if 1080p has negligible quality difference but larger size) or batch delete redundant copies.
                </p>
              </div>
            </div>

            <div className="flex flex-col sm:flex-row items-center justify-between gap-3">
              <div className="flex items-center gap-2 w-full sm:w-auto">
                <select
                  value={selectedPlaylistId}
                  onChange={(e) => setSelectedPlaylistId(e.target.value === 'all' ? 'all' : Number(e.target.value))}
                  className="px-3 py-1.5 border border-gray-300 dark:border-gray-600 rounded-lg text-xs bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                >
                  <option value="all">All Playlists ({playlists.length})</option>
                  {playlists.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.title}
                    </option>
                  ))}
                </select>

                <div className="relative flex-1 sm:w-64">
                  <Search className="w-4 h-4 absolute left-3 top-2 text-gray-400" />
                  <input
                    type="text"
                    placeholder="Search multi-version tracks..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    className="w-full pl-9 pr-3.5 py-1.5 border border-gray-300 dark:border-gray-600 rounded-lg text-xs bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                  />
                </div>
              </div>

              <div className="flex items-center gap-2 w-full sm:w-auto">
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => refetchTracks()}
                  disabled={isLoadingTracks}
                  className="flex items-center gap-1.5"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                  <span>Refresh</span>
                </Button>

                {filteredMultiTracks.length > 0 && (
                  <Button
                    variant="danger"
                    size="sm"
                    onClick={handleDeleteAllOlderVersions}
                    disabled={isDeletingVersions}
                    className="flex items-center gap-1.5"
                  >
                    {isDeletingVersions ? (
                      <>
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        <span>Deleting...</span>
                      </>
                    ) : (
                      <>
                        <Trash2 className="w-3.5 h-3.5" />
                        <span>Delete Older Copies (Keep Primary)</span>
                      </>
                    )}
                  </Button>
                )}
              </div>
            </div>

            {isLoadingTracks ? (
              <div className="py-12 flex flex-col items-center justify-center gap-3 text-center">
                <Loader2 className="w-8 h-8 animate-spin text-indigo-600" />
                <p className="text-sm font-semibold text-gray-700 dark:text-gray-300">
                  Scanning playlist folders for multi-resolution files...
                </p>
              </div>
            ) : filteredMultiTracks.length === 0 ? (
              <div className="py-10 text-center border border-dashed border-gray-300 dark:border-gray-700 rounded-xl">
                <Check className="w-8 h-8 text-emerald-500 mx-auto mb-2" />
                <p className="text-sm font-semibold text-gray-700 dark:text-gray-300">
                  No multi-version tracks found!
                </p>
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                  Each song has exactly one video version on disk.
                </p>
              </div>
            ) : (
              <div className="border border-gray-200 dark:border-gray-700 rounded-xl overflow-hidden max-h-96 overflow-y-auto">
                <table className="w-full text-left text-xs text-gray-700 dark:text-gray-300">
                  <thead className="bg-gray-100 dark:bg-gray-800 text-[11px] uppercase font-bold text-gray-600 dark:text-gray-400 sticky top-0">
                    <tr>
                      <th className="px-3.5 py-2.5 w-8">
                        <input
                          type="checkbox"
                          checked={selectedTrackIds.size === filteredMultiTracks.length && filteredMultiTracks.length > 0}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setSelectedTrackIds(new Set(filteredMultiTracks.map(t => t.video_id)))
                            } else {
                              setSelectedTrackIds(new Set())
                            }
                          }}
                          className="rounded border-gray-300"
                        />
                      </th>
                      <th className="px-3.5 py-2.5">Track Title</th>
                      <th className="px-3.5 py-2.5">Detected Versions on Disk</th>
                      <th className="px-3.5 py-2.5 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200 dark:divide-gray-700/60 bg-white dark:bg-gray-900/60">
                    {filteredMultiTracks.map((track) => {
                      const isSelected = selectedTrackIds.has(track.video_id)
                      const plId = (selectedPlaylistId !== 'all') ? selectedPlaylistId : (playlists[0]?.id || 1)
                      return (
                        <tr key={track.video_id} className="hover:bg-gray-50 dark:hover:bg-gray-800/40">
                          <td className="px-3.5 py-2.5">
                            <input
                              type="checkbox"
                              checked={isSelected}
                              onChange={(e) => {
                                const newSet = new Set(selectedTrackIds)
                                if (e.target.checked) newSet.add(track.video_id)
                                else newSet.delete(track.video_id)
                                setSelectedTrackIds(newSet)
                              }}
                              className="rounded border-gray-300"
                            />
                          </td>
                          <td className="px-3.5 py-2.5 max-w-xs truncate">
                            <div className="font-semibold text-gray-900 dark:text-white" title={track.title}>
                              {track.title}
                            </div>
                            <div className="text-[10px] text-gray-400 font-mono">
                              {track.video_id} • Primary: {track.primary_resolution || 'highest'}
                            </div>
                          </td>
                          <td className="px-3.5 py-2.5">
                            <div className="flex items-center gap-2 flex-wrap">
                              {track.disk_versions.map((ver, vIdx) => {
                                const isPrimary = track.primary_filepath === ver.filepath
                                return (
                                  <div
                                    key={vIdx}
                                    className={`px-2 py-1 rounded border text-[11px] flex items-center gap-1.5 ${
                                      isPrimary
                                        ? 'bg-indigo-50 dark:bg-indigo-950/60 border-indigo-300 dark:border-indigo-700 text-indigo-900 dark:text-indigo-200 font-bold'
                                        : 'bg-gray-100 dark:bg-gray-800 border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-300'
                                    }`}
                                  >
                                    {isPrimary && <Star className="w-3 h-3 text-amber-500 fill-amber-500" />}
                                    <span>{ver.resolution}</span>
                                    <span className="text-gray-400 font-mono text-[10px]">
                                      ({formatBytes(ver.size_bytes)})
                                    </span>
                                    {!isPrimary && (
                                      <button
                                        onClick={() => handleSetPrimary(plId, track.video_id, ver.resolution)}
                                        className="text-xs text-blue-600 hover:text-blue-800 dark:text-blue-400 ml-1"
                                        title="Make this copy the primary version"
                                      >
                                        Set Primary
                                      </button>
                                    )}
                                    <button
                                      onClick={() => handleDeleteVersion(plId, track.video_id, ver.resolution)}
                                      className="text-xs text-red-500 hover:text-red-700 ml-1"
                                      title="Delete this copy from disk"
                                    >
                                      <Trash2 className="w-3 h-3" />
                                    </button>
                                  </div>
                                )
                              })}
                            </div>
                          </td>
                          <td className="px-3.5 py-2.5 text-right">
                            <Button
                              variant="secondary"
                              size="sm"
                              onClick={() => {
                                const pl = playlists.find(p => p.id === plId)
                                if (pl) playlistsApi.openFolder(pl.id)
                              }}
                              className="text-[10px] py-1 px-2.5"
                            >
                              Open Folder
                            </Button>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </div>
    </Modal>
  )
}
