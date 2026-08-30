import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { housekeepingApi, type DeduplicationScanResult, type DeduplicationApplyResult } from '../../services/api'
import { Modal } from '../ui/Modal'
import { Button } from '../ui/Button'
import { 
  Sparkles, RefreshCw, HardDrive, Check, Loader2, Music, Search, ShieldCheck 
} from 'lucide-react'

export interface DeduplicateModalProps {
  isOpen: boolean
  onClose: () => void
}

export const DeduplicateModal: React.FC<DeduplicateModalProps> = ({ isOpen, onClose }) => {
  const queryClient = useQueryClient()
  const [searchTerm, setSearchTerm] = useState('')

  // 1. Fetch library duplicate scan
  const { data: scanData, isLoading: isScanning, refetch: rescan } = useQuery<DeduplicationScanResult>({
    queryKey: ['deduplicate-scan'],
    queryFn: async () => {
      const res = await housekeepingApi.scanDuplicates()
      return res.data
    },
    enabled: isOpen,
  })

  // 2. Apply deduplication mutation
  const [applyResult, setApplyResult] = useState<DeduplicationApplyResult | null>(null)
  const applyMutation = useMutation({
    mutationFn: async () => {
      const res = await housekeepingApi.applyDeduplication({
        duplicate_groups: scanData?.duplicate_groups
      })
      return res.data
    },
    onSuccess: (data) => {
      setApplyResult(data)
      queryClient.invalidateQueries({ queryKey: ['deduplicate-scan'] })
      queryClient.invalidateQueries({ queryKey: ['track-index'] })
    },
  })

  const groups = scanData?.duplicate_groups || []
  const filteredGroups = groups.filter(g => 
    g.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
    g.video_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
    g.playlists.some(p => p.toLowerCase().includes(searchTerm.toLowerCase()))
  )

  const handleApply = () => {
    if (!scanData || scanData.total_duplicate_files === 0) return
    if (confirm(
      `Convert ${scanData.total_duplicate_files} duplicate files into zero-space NTFS/ext4 hardlinks?\n\n` +
      `This will safely reclaim ~${scanData.formatted_reclaimable_space} of physical disk space while keeping all songs playable in their playlists.`
    )) {
      setApplyResult(null)
      applyMutation.mutate()
    }
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={
        <span className="flex items-center gap-2">
          <HardDrive className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
          <span>Library Deduplication & Space Reclaimer</span>
        </span>
      }
      subtitle="Scan for identical songs across multiple playlists and convert redundant physical files into zero-space hardlinks."
      maxWidth="3xl"
    >
      <div className="space-y-5 py-2">
        {/* Info Banner */}
        <div className="bg-indigo-50 dark:bg-indigo-950/30 border border-indigo-200 dark:border-indigo-800 rounded-xl p-3.5 flex items-start gap-3">
          <ShieldCheck className="w-5 h-5 text-indigo-600 dark:text-indigo-400 shrink-0 mt-0.5" />
          <div className="text-xs text-indigo-900 dark:text-indigo-200 space-y-1">
            <p className="font-semibold">Zero-Space Inode Hardlinking</p>
            <p className="text-indigo-700 dark:text-indigo-300">
              Converting duplicates to hardlinks creates direct pointers to the same physical disk sector. Each song remains in its playlist folder, but redundant copies consume <strong>0 MB</strong> extra hard drive space.
            </p>
          </div>
        </div>

        {/* Scan Status & Metric Cards */}
        {isScanning ? (
          <div className="py-12 flex flex-col items-center justify-center gap-3 text-center">
            <Loader2 className="w-8 h-8 animate-spin text-indigo-600" />
            <p className="text-sm font-semibold text-gray-700 dark:text-gray-300">
              Scanning library folders for duplicate media files...
            </p>
          </div>
        ) : (
          <>
            {/* Metric Summary Grid */}
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

            {/* Apply Success Toast */}
            {applyResult && (
              <div className="p-4 bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-300 dark:border-emerald-700 rounded-xl flex items-center gap-3">
                <Check className="w-6 h-6 text-emerald-500 shrink-0" />
                <div className="text-xs text-emerald-900 dark:text-emerald-200">
                  <p className="font-bold text-sm">Successfully Reclaimed {applyResult.formatted_space_reclaimed}!</p>
                  <p>Converted {applyResult.files_converted} duplicate files into zero-space hardlinks.</p>
                </div>
              </div>
            )}

            {/* Controls Bar: Search & Action Buttons */}
            <div className="flex flex-col sm:flex-row gap-2 justify-between items-center pt-1">
              <div className="relative w-full sm:w-72">
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
                  onClick={handleApply}
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

            {/* Duplicate Tracks List / Table */}
            {filteredGroups.length === 0 ? (
              <div className="py-10 text-center border border-dashed border-gray-300 dark:border-gray-700 rounded-xl">
                <Check className="w-8 h-8 text-emerald-500 mx-auto mb-2" />
                <p className="text-sm font-semibold text-gray-700 dark:text-gray-300">
                  {groups.length === 0
                    ? 'Your library is 100% deduplicated! No redundant physical files found.'
                    : 'No duplicate songs matched your filter.'}
                </p>
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                  All shared songs across playlists are already using zero-space hardlinks.
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
    </Modal>
  )
}
