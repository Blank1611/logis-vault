import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { tracksApi, type PendingMoveItem } from '../../services/api'
import { Modal } from '../ui/Modal'
import { Button } from '../ui/Button'
import {
  Layers, ArrowRight, CheckSquare, Square, Search, History, HardDrive, Check, Loader2
} from 'lucide-react'

export interface ReorganizeModalProps {
  isOpen: boolean
  onClose: () => void
}

export const ReorganizeModal: React.FC<ReorganizeModalProps> = ({ isOpen, onClose }) => {
  const queryClient = useQueryClient()
  const [activeTab, setActiveTab] = useState<'pending' | 'index' | 'history'>('pending')
  const [selectedMoves, setSelectedMoves] = useState<Set<string>>(new Set())
  const [searchQuery, setSearchQuery] = useState('')

  // 1. Fetch pending moves
  const { data: pendingData, isLoading: pendingLoading } = useQuery({
    queryKey: ['pending-moves'],
    queryFn: async () => {
      const res = await tracksApi.getPendingMoves()
      return res.data
    },
    enabled: isOpen,
  })

  // 2. Fetch track index
  const { data: indexData, isLoading: indexLoading } = useQuery({
    queryKey: ['track-index', searchQuery],
    queryFn: async () => {
      const res = await tracksApi.getIndex({ search: searchQuery, limit: 100 })
      return res.data
    },
    enabled: isOpen && activeTab === 'index',
  })

  // 3. Fetch move history
  const { data: historyData, isLoading: historyLoading } = useQuery({
    queryKey: ['move-history'],
    queryFn: async () => {
      const res = await tracksApi.getMoveHistory({ limit: 100 })
      return res.data
    },
    enabled: isOpen && activeTab === 'history',
  })

  // Apply moves mutation
  const applyMutation = useMutation({
    mutationFn: async (moves: PendingMoveItem[]) => {
      const payload = moves.map(m => ({
        video_id: m.video_id,
        from_playlist_id: m.from_playlist_id,
        to_playlist_id: m.to_playlist_id,
        action: 'move',
      }))
      const res = await tracksApi.applyMoves(payload)
      return res.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pending-moves'] })
      queryClient.invalidateQueries({ queryKey: ['move-history'] })
      queryClient.invalidateQueries({ queryKey: ['playlists'] })
      setSelectedMoves(new Set())
    },
  })

  const pendingList = pendingData?.pending || []

  const toggleSelectMove = (vid: string) => {
    const next = new Set(selectedMoves)
    if (next.has(vid)) {
      next.delete(vid)
    } else {
      next.add(vid)
    }
    setSelectedMoves(next)
  }

  const toggleSelectAll = () => {
    if (selectedMoves.size === pendingList.length) {
      setSelectedMoves(new Set())
    } else {
      setSelectedMoves(new Set(pendingList.map(p => p.video_id)))
    }
  }

  const handleApplySelected = () => {
    const movesToApply = pendingList.filter(p => selectedMoves.has(p.video_id))
    if (movesToApply.length > 0) {
      applyMutation.mutate(movesToApply)
    }
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Track Index & Inter-Playlist Reorganization Manager"
      maxWidth="4xl"
    >
      <div className="space-y-4">
        {/* Navigation Tabs */}
        <div className="flex border-b border-gray-200 dark:border-gray-700">
          <button
            onClick={() => setActiveTab('pending')}
            className={`px-4 py-2.5 text-xs font-bold flex items-center gap-1.5 border-b-2 transition-all ${activeTab === 'pending'
                ? 'border-blue-600 text-blue-600 dark:text-blue-400'
                : 'border-transparent text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'
              }`}
          >
            <Layers className="w-3.5 h-3.5" />
            Pending Reorganizations ({pendingList.length})
          </button>

          <button
            onClick={() => setActiveTab('index')}
            className={`px-4 py-2.5 text-xs font-bold flex items-center gap-1.5 border-b-2 transition-all ${activeTab === 'index'
                ? 'border-blue-600 text-blue-600 dark:text-blue-400'
                : 'border-transparent text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'
              }`}
          >
            <HardDrive className="w-3.5 h-3.5" />
            Global Track Index
          </button>

          <button
            onClick={() => setActiveTab('history')}
            className={`px-4 py-2.5 text-xs font-bold flex items-center gap-1.5 border-b-2 transition-all ${activeTab === 'history'
                ? 'border-blue-600 text-blue-600 dark:text-blue-400'
                : 'border-transparent text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'
              }`}
          >
            <History className="w-3.5 h-3.5" />
            Move History Log
          </button>
        </div>

        {/* Tab 1: Pending Reorganizations */}
        {activeTab === 'pending' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <p className="text-xs text-gray-600 dark:text-gray-400">
                Review and apply detected playlist moves or multi-playlist hardlinking without redownloading.
              </p>
              {pendingList.length > 0 && (
                <div className="flex items-center gap-2">
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={toggleSelectAll}
                    icon={selectedMoves.size === pendingList.length ? <CheckSquare className="w-3.5 h-3.5" /> : <Square className="w-3.5 h-3.5" />}
                  >
                    {selectedMoves.size === pendingList.length ? 'Deselect All' : 'Select All'}
                  </Button>

                  <Button
                    variant="primary"
                    size="sm"
                    loading={applyMutation.isPending}
                    disabled={selectedMoves.size === 0}
                    onClick={handleApplySelected}
                    icon={<Check className="w-3.5 h-3.5" />}
                  >
                    Apply Selected ({selectedMoves.size})
                  </Button>
                </div>
              )}
            </div>

            {pendingLoading ? (
              <div className="text-center py-12 text-gray-500">
                <Loader2 className="w-6 h-6 animate-spin mx-auto mb-2 text-blue-500" />
                Analyzing library track index...
              </div>
            ) : pendingList.length > 0 ? (
              <div className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden max-h-[55vh] overflow-y-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-gray-50 dark:bg-gray-800 text-gray-700 dark:text-gray-300 font-bold border-b border-gray-200 dark:border-gray-700">
                    <tr>
                      <th className="p-3 w-10 text-center">#</th>
                      <th className="p-3">Track Title</th>
                      <th className="p-3">Source Playlist</th>
                      <th className="p-3">Destination Playlist</th>
                      <th className="p-3 text-right">Suggested Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100 dark:divide-gray-800 font-medium">
                    {pendingList.map(item => (
                      <tr
                        key={item.video_id}
                        onClick={() => toggleSelectMove(item.video_id)}
                        className={`cursor-pointer transition-colors ${selectedMoves.has(item.video_id)
                            ? 'bg-blue-50/70 dark:bg-blue-950/40'
                            : 'hover:bg-gray-50 dark:hover:bg-gray-800/50'
                          }`}
                      >
                        <td className="p-3 text-center">
                          {selectedMoves.has(item.video_id) ? (
                            <CheckSquare className="w-4 h-4 text-blue-600 mx-auto" />
                          ) : (
                            <Square className="w-4 h-4 text-gray-400 mx-auto" />
                          )}
                        </td>
                        <td className="p-3 text-gray-900 dark:text-white font-semibold">
                          {item.title}
                          <div className="text-[10px] text-gray-500 font-mono">{item.video_id}</div>
                        </td>
                        <td className="p-3 text-gray-600 dark:text-gray-300">
                          {item.from_playlist_title}
                        </td>
                        <td className="p-3 text-blue-600 dark:text-blue-400 font-semibold flex items-center gap-1.5 pt-4">
                          <ArrowRight className="w-3.5 h-3.5 shrink-0" />
                          {item.to_playlist_title}
                        </td>
                        <td className="p-3 text-right">
                          <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200">
                            ⚡ Zero-Space Hardlink
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="text-center py-16 bg-gray-50 dark:bg-gray-800/40 rounded-lg border border-dashed border-gray-300 dark:border-gray-700">
                <Check className="w-8 h-8 text-emerald-500 mx-auto mb-2" />
                <p className="text-sm font-semibold text-gray-700 dark:text-gray-300">All Playlists In Sync</p>
                <p className="text-xs text-gray-500 mt-0.5">No moved or pending tracks requiring reorganization.</p>
              </div>
            )}
          </div>
        )}

        {/* Tab 2: Global Track Index */}
        {activeTab === 'index' && (
          <div className="space-y-4">
            <div className="relative w-full">
              <Search className="w-3.5 h-3.5 absolute left-3 top-2.5 text-gray-400" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search tracks in index by title or YouTube video ID..."
                className="w-full pl-9 pr-3 py-1.5 bg-gray-50 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg text-xs text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            {indexLoading ? (
              <div className="text-center py-12 text-gray-500">
                <Loader2 className="w-6 h-6 animate-spin mx-auto mb-2 text-blue-500" />
                Loading global track index...
              </div>
            ) : (indexData?.items || []).length > 0 ? (
              <div className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden max-h-[55vh] overflow-y-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-gray-50 dark:bg-gray-800 text-gray-700 dark:text-gray-300 font-bold border-b border-gray-200 dark:border-gray-700">
                    <tr>
                      <th className="p-3">Track Title</th>
                      <th className="p-3">Video ID</th>
                      <th className="p-3">Playlists</th>
                      <th className="p-3">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100 dark:divide-gray-800 font-medium">
                    {indexData?.items.map(t => (
                      <tr key={t.video_id} className="hover:bg-gray-50 dark:hover:bg-gray-800/50">
                        <td className="p-3 text-gray-900 dark:text-white font-semibold">
                          {t.title}
                        </td>
                        <td className="p-3 text-gray-500 font-mono text-[11px]">
                          {t.video_id}
                        </td>
                        <td className="p-3">
                          <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300">
                            {t.playlists.length} Playlist{t.playlists.length === 1 ? '' : 's'}
                          </span>
                        </td>
                        <td className="p-3">
                          {t.is_hardlinked ? (
                            <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-cyan-100 text-cyan-800 dark:bg-cyan-900 dark:text-cyan-200">
                              ⚡ Hardlinked
                            </span>
                          ) : (
                            <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-100 text-emerald-800 dark:bg-emerald-900 dark:text-emerald-200">
                              ✓ Primary
                            </span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="text-center py-12 text-gray-500">
                No indexed tracks found matching query.
              </div>
            )}
          </div>
        )}

        {/* Tab 3: Move History */}
        {activeTab === 'history' && (
          <div className="space-y-4">
            {historyLoading ? (
              <div className="text-center py-12 text-gray-500">
                <Loader2 className="w-6 h-6 animate-spin mx-auto mb-2 text-blue-500" />
                Loading reorganization audit log...
              </div>
            ) : (historyData?.items || []).length > 0 ? (
              <div className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden max-h-[55vh] overflow-y-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-gray-50 dark:bg-gray-800 text-gray-700 dark:text-gray-300 font-bold border-b border-gray-200 dark:border-gray-700">
                    <tr>
                      <th className="p-3">Timestamp</th>
                      <th className="p-3">Track Title</th>
                      <th className="p-3">From</th>
                      <th className="p-3">To</th>
                      <th className="p-3">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100 dark:divide-gray-800 font-medium">
                    {historyData?.items.map(h => (
                      <tr key={h.id} className="hover:bg-gray-50 dark:hover:bg-gray-800/50">
                        <td className="p-3 text-gray-500 font-mono text-[11px]">
                          {h.moved_at ? new Date(h.moved_at).toLocaleString() : ''}
                        </td>
                        <td className="p-3 text-gray-900 dark:text-white font-semibold">
                          {h.title}
                        </td>
                        <td className="p-3 text-gray-600 dark:text-gray-300">
                          {h.from_playlist_title}
                        </td>
                        <td className="p-3 text-blue-600 dark:text-blue-400 font-semibold">
                          {h.to_playlist_title}
                        </td>
                        <td className="p-3">
                          <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-100 text-emerald-800 dark:bg-emerald-900 dark:text-emerald-200">
                            {h.status}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="text-center py-12 text-gray-500">
                No track moves recorded yet in history.
              </div>
            )}
          </div>
        )}
      </div>
    </Modal>
  )
}
