import React, { useState, useEffect, useMemo } from 'react'
import {
  adhocApi,
  type AdhocMediaItem,
  type AdhocItemsResponse
} from '../../services/api'
import { MediaPreviewModal } from '../modals/MediaPreviewModal'
import { Button } from '../ui/Button'
import { Modal } from '../ui/Modal'
import {
  Folder,
  RefreshCw,
  Search,
  Play,
  Download,
  Trash2,
  Film,
  Music,
  Filter,
  Layers,
  CheckSquare,
  Square,
  AlertTriangle,
  Loader2,
  ArrowUpDown,
  ArrowUp,
  ArrowDown
} from 'lucide-react'
import { useToast } from '../../context'

export interface AdhocMediaViewerProps {
  refreshTrigger?: number
  onMediaDeleted?: () => void
}

export type AdhocSortField = 'title' | 'directory' | 'format' | 'size' | 'date'

export const AdhocMediaViewer: React.FC<AdhocMediaViewerProps> = ({
  refreshTrigger = 0,
  onMediaDeleted,
}) => {
  const { toast } = useToast()
  const [data, setData] = useState<AdhocItemsResponse | null>(null)
  const [isLoading, setIsLoading] = useState<boolean>(true)

  // Filters
  const [selectedDirectory, setSelectedDirectory] = useState<string>('all')
  const [selectedType, setSelectedType] = useState<string>('all')
  const [searchQuery, setSearchQuery] = useState<string>('')

  // Sorting state
  const [sortField, setSortField] = useState<AdhocSortField>('date')
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc')

  const handleSort = (field: AdhocSortField) => {
    if (sortField === field) {
      setSortDirection((prev) => (prev === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortField(field)
      setSortDirection('asc')
    }
  }

  const renderSortIcon = (field: AdhocSortField) => {
    if (sortField !== field) {
      return <ArrowUpDown className="w-3.5 h-3.5 text-gray-500 opacity-60" />
    }
    return sortDirection === 'asc' ? (
      <ArrowUp className="w-3.5 h-3.5 text-blue-400" />
    ) : (
      <ArrowDown className="w-3.5 h-3.5 text-blue-400" />
    )
  }

  // Preview & Delete Modals
  const [previewItem, setPreviewItem] = useState<AdhocMediaItem | null>(null)
  const [itemToDelete, setItemToDelete] = useState<AdhocMediaItem | null>(null)
  const [isDeleting, setIsDeleting] = useState<boolean>(false)

  // Playlist Promotion Modal
  const [showPromoteModal, setShowPromoteModal] = useState<boolean>(false)
  const [promoteTitle, setPromoteTitle] = useState<string>('')
  const [selectedFilepaths, setSelectedFilepaths] = useState<string[]>([])
  const [isPromoting, setIsPromoting] = useState<boolean>(false)

  const fetchItems = async () => {
    setIsLoading(true)
    try {
      const res = await adhocApi.getItems()
      setData(res.data)
    } catch (err: any) {
      toast.error('Failed to load ad-hoc media items')
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    fetchItems()
  }, [refreshTrigger])

  const formatBytes = (bytes: number) => {
    if (!bytes) return '0 B'
    const k = 1024
    const sizes = ['B', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`
  }

  const formatDuration = (seconds?: number) => {
    if (!seconds) return '00:00'
    const m = Math.floor(seconds / 60)
    const s = Math.floor(seconds % 60)
    return `${m}:${s < 10 ? '0' : ''}${s}`
  }

  const formatDate = (isoString?: string) => {
    if (!isoString) return ''
    try {
      const d = new Date(isoString)
      return d.toLocaleDateString(undefined, {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      })
    } catch {
      return isoString
    }
  }

  // Filtered & Sorted Items
  const filteredItems = useMemo(() => {
    if (!data?.items) return []
    const filtered = data.items.filter((item) => {
      // Directory Filter
      if (selectedDirectory !== 'all' && item.directory_display !== selectedDirectory && item.directory !== selectedDirectory) {
        return false
      }
      // Type Filter
      if (selectedType !== 'all' && item.media_type !== selectedType) {
        return false
      }
      // Search Query
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase().trim()
        const matchesTitle = item.title?.toLowerCase().includes(q)
        const matchesId = item.id?.toLowerCase().includes(q)
        const matchesUploader = item.uploader?.toLowerCase().includes(q)
        const matchesFilename = item.filename?.toLowerCase().includes(q)
        if (!matchesTitle && !matchesId && !matchesUploader && !matchesFilename) {
          return false
        }
      }
      return true
    })

    return filtered.sort((a: AdhocMediaItem, b: AdhocMediaItem) => {
      let comparison = 0
      switch (sortField) {
        case 'title':
          comparison = (a.title || '').localeCompare(b.title || '')
          break
        case 'directory':
          comparison = (a.directory_display || a.directory || '').localeCompare(
            b.directory_display || b.directory || ''
          )
          break
        case 'format':
          comparison = (a.format || '').localeCompare(b.format || '')
          break
        case 'size':
          comparison = (a.size_bytes || 0) - (b.size_bytes || 0)
          break
        case 'date':
          comparison =
            new Date(a.downloaded_at || 0).getTime() -
            new Date(b.downloaded_at || 0).getTime()
          break
        default:
          comparison = 0
      }
      return sortDirection === 'asc' ? comparison : -comparison
    })
  }, [data, selectedDirectory, selectedType, searchQuery, sortField, sortDirection])

  // Delete Action
  const handleDeleteConfirm = async () => {
    if (!itemToDelete) return
    setIsDeleting(true)
    const targetFile = itemToDelete.filepath || itemToDelete.audio_filepath || ''
    try {
      await adhocApi.deleteItem(targetFile)
      toast.success(`Deleted ${itemToDelete.title}`)
      setItemToDelete(null)
      fetchItems()
      if (onMediaDeleted) onMediaDeleted()
    } catch (err: any) {
      toast.error('Failed to delete media file')
    } finally {
      setIsDeleting(false)
    }
  }

  // Promote Action
  const handlePromoteConfirm = async () => {
    const title = promoteTitle.trim()
    if (!title) {
      toast.error('Please enter a playlist title')
      return
    }

    const filesToPromote = selectedFilepaths.length > 0
      ? selectedFilepaths
      : filteredItems.map((it) => it.filepath || it.audio_filepath || '').filter(Boolean)

    if (filesToPromote.length === 0) {
      toast.error('No valid media files found to promote')
      return
    }

    const firstItem = filteredItems.find((it) => (it.filepath || it.audio_filepath) === filesToPromote[0])
    const sourceDir = firstItem?.directory || data?.directories[0] || '/downloads'

    setIsPromoting(true)
    try {
      const res = await adhocApi.promoteToPlaylist({
        source_directory: sourceDir,
        filepaths: filesToPromote,
        playlist_title: title,
      })
      toast.success(`Promoted ${res.data.tracks_added} tracks to playlist "${res.data.playlist_title}"`)
      setShowPromoteModal(false)
      setPromoteTitle('')
      setSelectedFilepaths([])
    } catch (err: any) {
      toast.error('Failed to promote media to playlist')
    } finally {
      setIsPromoting(false)
    }
  }

  const toggleSelectAll = () => {
    const allPaths = filteredItems.map((it) => it.filepath || it.audio_filepath || '').filter(Boolean)
    if (selectedFilepaths.length === allPaths.length) {
      setSelectedFilepaths([])
    } else {
      setSelectedFilepaths(allPaths)
    }
  }

  const toggleSelectItem = (path: string) => {
    setSelectedFilepaths((prev) =>
      prev.includes(path) ? prev.filter((p) => p !== path) : [...prev, path]
    )
  }

  return (
    <div className="space-y-3 pt-4 border-t border-gray-800">
      {/* Header bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Folder className="w-5 h-5 text-amber-400" />
          <h3 className="text-base font-semibold text-gray-100">
            Ad-Hoc Media Gallery
          </h3>
          {data && (
            <span className="text-xs px-2 py-0.5 rounded-full bg-gray-800 text-gray-300 font-medium border border-gray-700">
              {data.total_items} {data.total_items === 1 ? 'file' : 'files'} across {data.directories.length} {data.directories.length === 1 ? 'dir' : 'dirs'} • {formatBytes(data.total_size_bytes)}
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          {filteredItems.length > 0 && (
            <Button
              variant="secondary"
              size="sm"
              onClick={() => {
                setPromoteTitle(selectedDirectory !== 'all' ? selectedDirectory : 'Ad-hoc Collection')
                setShowPromoteModal(true)
              }}
              icon={<Layers className="w-3.5 h-3.5 text-blue-400" />}
            >
              Promote to Playlist {selectedFilepaths.length > 0 ? `(${selectedFilepaths.length})` : ''}
            </Button>
          )}

          <Button
            variant="ghost"
            size="sm"
            onClick={fetchItems}
            disabled={isLoading}
            icon={<RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />}
            title="Refresh from disk"
          >
            Refresh
          </Button>
        </div>
      </div>

      {/* Filter Toolbar */}
      <div className="grid grid-cols-1 sm:grid-cols-12 gap-2 bg-gray-900/60 p-2.5 rounded-lg border border-gray-800">
        {/* Directory filter dropdown */}
        <div className="sm:col-span-4 flex items-center gap-2">
          <Folder className="w-4 h-4 text-gray-400 flex-shrink-0" />
          <select
            value={selectedDirectory}
            onChange={(e) => setSelectedDirectory(e.target.value)}
            className="w-full bg-gray-950 border border-gray-800 rounded px-2.5 py-1.5 text-xs text-gray-200 focus:outline-none focus:border-blue-500"
          >
            <option value="all">All Directories ({data?.directories.length || 0})</option>
            {data?.directories.map((dir) => (
              <option key={dir} value={dir}>
                {dir}
              </option>
            ))}
          </select>
        </div>

        {/* Media Type filter */}
        <div className="sm:col-span-3 flex items-center gap-2">
          <Filter className="w-4 h-4 text-gray-400 flex-shrink-0" />
          <select
            value={selectedType}
            onChange={(e) => setSelectedType(e.target.value)}
            className="w-full bg-gray-950 border border-gray-800 rounded px-2.5 py-1.5 text-xs text-gray-200 focus:outline-none focus:border-blue-500"
          >
            <option value="all">All Types (Video & Audio)</option>
            <option value="video">Videos Only</option>
            <option value="audio">Audios Only</option>
          </select>
        </div>

        {/* Search Input */}
        <div className="sm:col-span-5 relative flex items-center">
          <Search className="w-4 h-4 text-gray-400 absolute left-2.5 pointer-events-none" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search by title, video ID, uploader..."
            className="w-full bg-gray-950 border border-gray-800 rounded pl-8 pr-2.5 py-1.5 text-xs text-gray-200 placeholder-gray-500 focus:outline-none focus:border-blue-500"
          />
        </div>
      </div>

      {/* Media Table */}
      <div className="bg-gray-950/80 border border-gray-800 rounded-lg overflow-hidden shadow-inner">
        {isLoading ? (
          <div className="flex flex-col items-center justify-center py-16 text-gray-400 space-y-2">
            <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
            <p className="text-xs">Scanning ad-hoc directories...</p>
          </div>
        ) : filteredItems.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-gray-500 space-y-2">
            <Film className="w-10 h-10 text-gray-700" />
            <p className="text-sm font-medium text-gray-400">No ad-hoc media items found</p>
            <p className="text-xs text-gray-600 max-w-sm text-center">
              Downloaded videos or audio using the downloader above will appear here across all your tracked directories.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-gray-900/90 text-gray-400 font-medium border-b border-gray-800">
                <tr>
                  <th className="py-2.5 px-3 w-10 text-center">
                    <button
                      type="button"
                      onClick={toggleSelectAll}
                      className="text-gray-400 hover:text-gray-200 transition-colors"
                      title="Select / Deselect all"
                    >
                      {selectedFilepaths.length === filteredItems.length && filteredItems.length > 0 ? (
                        <CheckSquare className="w-4 h-4 text-blue-400" />
                      ) : (
                        <Square className="w-4 h-4" />
                      )}
                    </button>
                  </th>
                  <th className="py-2.5 px-3 w-16">Preview</th>
                  <th
                    className="py-2.5 px-3 cursor-pointer hover:text-gray-200 transition-colors select-none"
                    onClick={() => handleSort('title')}
                  >
                    <div className="flex items-center gap-1.5">
                      <span>Title & Channel</span>
                      {renderSortIcon('title')}
                    </div>
                  </th>
                  <th
                    className="py-2.5 px-3 cursor-pointer hover:text-gray-200 transition-colors select-none"
                    onClick={() => handleSort('directory')}
                  >
                    <div className="flex items-center gap-1.5">
                      <span>Directory</span>
                      {renderSortIcon('directory')}
                    </div>
                  </th>
                  <th
                    className="py-2.5 px-3 cursor-pointer hover:text-gray-200 transition-colors select-none"
                    onClick={() => handleSort('format')}
                  >
                    <div className="flex items-center gap-1.5">
                      <span>Quality / Format</span>
                      {renderSortIcon('format')}
                    </div>
                  </th>
                  <th
                    className="py-2.5 px-3 cursor-pointer hover:text-gray-200 transition-colors select-none"
                    onClick={() => handleSort('size')}
                  >
                    <div className="flex items-center gap-1.5">
                      <span>Size</span>
                      {renderSortIcon('size')}
                    </div>
                  </th>
                  <th
                    className="py-2.5 px-3 cursor-pointer hover:text-gray-200 transition-colors select-none"
                    onClick={() => handleSort('date')}
                  >
                    <div className="flex items-center gap-1.5">
                      <span>Date</span>
                      {renderSortIcon('date')}
                    </div>
                  </th>
                  <th className="py-2.5 px-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800/60 text-gray-200">
                {filteredItems.map((item) => {
                  const targetPath = item.filepath || item.audio_filepath || ''
                  const isSelected = selectedFilepaths.includes(targetPath)
                  const streamUrl = adhocApi.getStreamUrl(targetPath)

                  return (
                    <tr
                      key={targetPath || item.id}
                      className={`hover:bg-gray-900/50 transition-colors ${
                        isSelected ? 'bg-blue-950/20' : ''
                      }`}
                    >
                      {/* Checkbox */}
                      <td className="py-2.5 px-3 text-center">
                        <button
                          type="button"
                          onClick={() => toggleSelectItem(targetPath)}
                          className="text-gray-400 hover:text-gray-200 transition-colors"
                        >
                          {isSelected ? (
                            <CheckSquare className="w-4 h-4 text-blue-400" />
                          ) : (
                            <Square className="w-4 h-4" />
                          )}
                        </button>
                      </td>

                      {/* Thumbnail / Media icon */}
                      <td className="py-2.5 px-3">
                        <div
                          onClick={() => setPreviewItem(item)}
                          className="w-14 h-9 bg-gray-900 rounded overflow-hidden flex items-center justify-center relative cursor-pointer group border border-gray-800 flex-shrink-0"
                          title="Click to preview"
                        >
                          {item.thumbnail ? (
                            <img
                              src={item.thumbnail}
                              alt={item.title}
                              className="w-full h-full object-cover group-hover:scale-105 transition-transform"
                            />
                          ) : item.media_type === 'video' ? (
                            <Film className="w-5 h-5 text-blue-400" />
                          ) : (
                            <Music className="w-5 h-5 text-purple-400" />
                          )}
                          <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 flex items-center justify-center transition-opacity">
                            <Play className="w-4 h-4 text-white fill-white" />
                          </div>
                        </div>
                      </td>

                      {/* Title & Channel */}
                      <td className="py-2.5 px-3">
                        <div className="font-medium text-gray-100 break-words" title={item.title}>
                          {item.title}
                        </div>
                        <div className="flex items-center gap-2 text-[11px] text-gray-400 mt-0.5">
                          <span className="truncate">{item.uploader}</span>
                          {item.duration > 0 && <span>• {formatDuration(item.duration)}</span>}
                          {item.id && !item.id.startsWith('file_') && (
                            <span className="font-mono text-gray-500">[{item.id}]</span>
                          )}
                        </div>
                      </td>

                      {/* Directory Column */}
                      <td className="py-2.5 px-3">
                        <button
                          type="button"
                          onClick={() => setSelectedDirectory(item.directory_display)}
                          className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-mono bg-amber-950/30 text-amber-400 border border-amber-900/40 hover:bg-amber-950/60 transition-colors"
                          title={`Path: ${item.directory}\nClick to filter by this directory`}
                        >
                          <Folder className="w-3 h-3 flex-shrink-0" />
                          <span>{item.directory_display}</span>
                        </button>
                      </td>

                      {/* Quality / Format */}
                      <td className="py-2.5 px-3">
                        <div className="flex flex-wrap items-center gap-1.5">
                          {item.format ? (
                            <span
                              className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-mono font-semibold uppercase border ${
                                item.media_type === 'video'
                                  ? 'bg-cyan-950/40 text-cyan-400 border-cyan-800/60'
                                  : 'bg-purple-950/40 text-purple-400 border-purple-800/60'
                              }`}
                            >
                              {item.format}
                            </span>
                          ) : (
                            <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-mono font-semibold uppercase border bg-gray-800/60 text-gray-400 border-gray-700/60">
                              {item.media_type === 'video' ? 'VIDEO' : 'AUDIO'}
                            </span>
                          )}
                          {item.resolution && (
                            <span className="inline-flex items-center px-1.5 py-0.5 rounded bg-gray-800 text-gray-300 text-[10px] font-medium border border-gray-700/60">
                              {item.resolution}
                            </span>
                          )}
                        </div>
                        {(item.audio_codec || item.audio_bitrate) && (
                          <div className="text-[10px] text-gray-400 mt-0.5">
                            {item.audio_codec?.toUpperCase()} {item.audio_bitrate ? `${item.audio_bitrate}k` : ''}
                          </div>
                        )}
                      </td>

                      {/* Size */}
                      <td className="py-2.5 px-3 whitespace-nowrap text-gray-300 font-mono">
                        {formatBytes(item.size_bytes)}
                      </td>

                      {/* Date */}
                      <td className="py-2.5 px-3 whitespace-nowrap text-gray-400">
                        {formatDate(item.downloaded_at)}
                      </td>

                      {/* Actions */}
                      <td className="py-2.5 px-3 text-right whitespace-nowrap">
                        <div className="flex items-center justify-end gap-1">
                          <button
                            type="button"
                            onClick={() => setPreviewItem(item)}
                            className="p-1 rounded text-gray-400 hover:text-blue-400 hover:bg-gray-800/80 transition-colors"
                            title="Play / Preview in browser"
                          >
                            <Play className="w-3.5 h-3.5" />
                          </button>

                          <a
                            href={streamUrl}
                            download={item.filename}
                            className="p-1 rounded text-gray-400 hover:text-green-400 hover:bg-gray-800/80 transition-colors"
                            title="Download file directly"
                          >
                            <Download className="w-3.5 h-3.5" />
                          </a>

                          <button
                            type="button"
                            onClick={() => setItemToDelete(item)}
                            className="p-1 rounded text-gray-400 hover:text-red-400 hover:bg-gray-800/80 transition-colors"
                            title="Delete file"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Preview Modal */}
      <MediaPreviewModal
        isOpen={Boolean(previewItem)}
        onClose={() => setPreviewItem(null)}
        item={previewItem}
      />

      {/* Delete Confirmation Modal */}
      {itemToDelete && (
        <Modal
          isOpen={true}
          onClose={() => setItemToDelete(null)}
          title={
            <div className="flex items-center gap-2 text-red-400">
              <AlertTriangle className="w-5 h-5" />
              <span>Delete Ad-Hoc File?</span>
            </div>
          }
          maxWidth="sm"
          footer={
            <div className="flex items-center justify-end gap-2 w-full">
              <Button variant="secondary" size="sm" onClick={() => setItemToDelete(null)}>
                Cancel
              </Button>
              <Button
                variant="danger"
                size="sm"
                onClick={handleDeleteConfirm}
                disabled={isDeleting}
                icon={isDeleting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : undefined}
              >
                Delete File
              </Button>
            </div>
          }
        >
          <div className="space-y-2 text-xs text-gray-300">
            <p>
              Are you sure you want to permanently delete:
            </p>
            <div className="p-2.5 bg-gray-900 border border-gray-800 rounded font-medium text-white truncate">
              {itemToDelete.title}
            </div>
            <p className="text-gray-400 text-[11px]">
              This removes the file from disk and prunes its metadata from <span className="font-mono text-gray-300">adhoc_info.json</span>.
            </p>
          </div>
        </Modal>
      )}

      {/* Promote to Playlist Modal */}
      {showPromoteModal && (
        <Modal
          isOpen={true}
          onClose={() => setShowPromoteModal(false)}
          title={
            <div className="flex items-center gap-2 text-blue-400">
              <Layers className="w-5 h-5" />
              <span>Promote to Managed Playlist</span>
            </div>
          }
          subtitle="Convert staged ad-hoc media into a permanent SQLite playlist"
          maxWidth="md"
          footer={
            <div className="flex items-center justify-end gap-2 w-full">
              <Button variant="secondary" size="sm" onClick={() => setShowPromoteModal(false)}>
                Cancel
              </Button>
              <Button
                variant="primary"
                size="sm"
                onClick={handlePromoteConfirm}
                disabled={!promoteTitle.trim() || isPromoting}
                icon={isPromoting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : undefined}
              >
                Promote {selectedFilepaths.length > 0 ? `(${selectedFilepaths.length})` : 'All'}
              </Button>
            </div>
          }
        >
          <div className="space-y-3 text-xs text-gray-300">
            <div>
              <label className="block text-gray-400 mb-1 font-medium">
                Playlist Title
              </label>
              <input
                type="text"
                value={promoteTitle}
                onChange={(e) => setPromoteTitle(e.target.value)}
                placeholder="e.g. Synthwave Gems, Dev Tutorials"
                className="w-full bg-gray-950 border border-gray-700 rounded px-3 py-2 text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:border-blue-500"
                autoFocus
              />
            </div>

            <div className="p-3 bg-gray-900/80 border border-gray-800 rounded text-[11px] text-gray-400 space-y-1">
              <div className="flex justify-between">
                <span>Items to convert:</span>
                <span className="font-semibold text-white">
                  {selectedFilepaths.length > 0 ? selectedFilepaths.length : filteredItems.length} tracks
                </span>
              </div>
              <p className="text-gray-500">
                These media files will be formally indexed into the Track table and placed in a new Playlist.
              </p>
            </div>
          </div>
        </Modal>
      )}
    </div>
  )
}
