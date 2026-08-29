import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { playlistsApi } from '../../services/api'
import type { Playlist } from '../../services/types'
import { Modal } from '../ui/Modal'
import { Button } from '../ui/Button'
import { StatusBadge } from '../ui/StatusBadge'
import { X, Search } from 'lucide-react'

export interface ExclusionsModalProps {
  playlist: Playlist
  onClose: () => void
}

export const ExclusionsModal: React.FC<ExclusionsModalProps> = ({ playlist, onClose }) => {
  const queryClient = useQueryClient()
  const [excludedIds, setExcludedIds] = useState<string[]>(playlist.excluded_ids || [])
  const [newId, setNewId] = useState('')

  // Fetch video info (titles) for the playlist
  const { data: videoInfo } = useQuery({
    queryKey: ['videoInfo', playlist.id],
    queryFn: async () => {
      const res = await playlistsApi.getVideoInfo(playlist.id)
      return res.data
    },
  })

  const updatePlaylist = useMutation({
    mutationFn: (data: Partial<Playlist>) => playlistsApi.update(playlist.id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['playlists'] })
      alert('Exclusions updated successfully!')
      onClose()
    },
  })

  const handleAdd = () => {
    const id = newId.trim()
    if (id && !excludedIds.includes(id)) {
      setExcludedIds([...excludedIds, id])
      setNewId('')
    }
  }

  const handleRemove = (id: string) => {
    setExcludedIds(excludedIds.filter(eid => eid !== id))
  }

  const handleSave = () => {
    updatePlaylist.mutate({ excluded_ids: excludedIds })
  }

  return (
    <Modal
      isOpen={true}
      onClose={onClose}
      title={`Edit Exclusions: ${playlist.title}`}
      subtitle="Excluded videos will be skipped during downloads"
      maxWidth="2xl"
      footer={
        <div className="flex gap-2">
          <Button
            onClick={handleSave}
            loading={updatePlaylist.isPending}
            className="flex-1"
          >
            Save Changes
          </Button>
          <Button
            variant="secondary"
            onClick={onClose}
          >
            Cancel
          </Button>
        </div>
      }
    >
      {/* Add New ID */}
      <div className="mb-6">
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
          Add Video ID to Exclude
        </label>
        <div className="flex gap-2">
          <input
            type="text"
            value={newId}
            onChange={(e) => setNewId(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleAdd()}
            placeholder="Enter video ID (e.g., dQw4w9WgXcQ)"
            className="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:outline-none"
          />
          <Button
            onClick={handleAdd}
            disabled={!newId.trim()}
          >
            Add
          </Button>
        </div>
      </div>

      {/* Excluded IDs List */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Excluded Video IDs ({excludedIds.length})
          </label>
          {excludedIds.length > 0 && (
            <button
              onClick={() => {
                excludedIds.forEach((id) => {
                  const info = videoInfo?.[id]
                  const title = info?.title || id
                  const searchQuery = encodeURIComponent(title)
                  window.open(`https://www.youtube.com/results?search_query=${searchQuery}`, '_blank')
                })
              }}
              className="text-xs px-3 py-1 bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-400 hover:bg-yellow-200 dark:hover:bg-yellow-900/50 rounded-full transition-colors flex items-center gap-1"
              title={`Search for all ${excludedIds.length} excluded video titles on YouTube`}
            >
              <Search className="w-3 h-3" />
              Search All ({excludedIds.length})
            </button>
          )}
        </div>

        {excludedIds.length === 0 ? (
          <div className="text-center py-8 text-gray-500 dark:text-gray-400">
            No videos excluded
          </div>
        ) : (
          <ol className="space-y-2 max-h-96 overflow-y-auto pr-2 -mr-2">
            {excludedIds
              .slice()
              .sort((a, b) => {
                const infoA = videoInfo?.[a]
                const infoB = videoInfo?.[b]
                const titleA = infoA?.title || a
                const titleB = infoB?.title || b

                const getPriority = (title: string, id: string) => {
                  if (title === id) return 4
                  if (title.includes('[Deleted video]')) return 3
                  if (title.includes('[Private video]')) return 2
                  return 1
                }

                const priorityA = getPriority(titleA, a)
                const priorityB = getPriority(titleB, b)

                if (priorityA !== priorityB) {
                  return priorityA - priorityB
                }
                return titleA.localeCompare(titleB)
              })
              .map((id, index) => {
                const info = videoInfo?.[id]
                const title = info?.title || id

                const getBadgeStatus = () => {
                  if (title === id) return 'Unknown'
                  if (title.includes('[Deleted video]')) return 'Likely Gone'
                  if (title.includes('[Private video]')) return 'Might Return'
                  return 'Searchable'
                }

                return (
                  <li
                    key={id}
                    className="flex items-start gap-3 p-3 bg-gray-50 dark:bg-gray-700/60 rounded-lg border border-gray-100 dark:border-gray-600/50"
                  >
                    <span className="text-sm font-semibold text-gray-600 dark:text-gray-400 min-w-[2rem] mt-0.5">
                      {index + 1}.
                    </span>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1 flex-wrap">
                        <a
                          href={`https://www.youtube.com/watch?v=${id}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-sm text-blue-600 dark:text-blue-400 hover:underline truncate"
                          title={`${title}\n\nClick to view in browser`}
                        >
                          {title}
                        </a>
                        <StatusBadge status={getBadgeStatus()} />
                      </div>
                      <code className="text-xs text-gray-500 dark:text-gray-400 font-mono">
                        {id}
                      </code>
                    </div>
                    <div className="flex gap-1 flex-shrink-0 items-center">
                      <button
                        onClick={() => {
                          const searchQuery = encodeURIComponent(title)
                          window.open(`https://www.youtube.com/results?search_query=${searchQuery}`, '_blank')
                        }}
                        className="p-1 text-yellow-600 dark:text-yellow-400 hover:bg-yellow-100 dark:hover:bg-yellow-900/30 rounded text-xs px-2 py-1 flex items-center gap-1"
                        title={`Search "${title}" on YouTube\n\nUseful if video was removed and re-uploaded`}
                      >
                        <Search className="w-3 h-3" />
                        Search
                      </button>
                      <button
                        onClick={() => handleRemove(id)}
                        className="p-1 text-red-600 dark:text-red-400 hover:bg-red-100 dark:hover:bg-red-900/30 rounded"
                        title="Remove from exclusions"
                      >
                        <X className="w-4 h-4" />
                      </button>
                    </div>
                  </li>
                )
              })}
          </ol>
        )}
      </div>
    </Modal>
  )
}
