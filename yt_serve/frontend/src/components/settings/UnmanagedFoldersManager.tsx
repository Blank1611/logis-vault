import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { configApi, type UnmanagedFolder } from '../../services/api'
import { useToast } from '../../context/ToastContext'
import { useConfirm } from '../../context/ConfirmContext'
import { Button } from '../ui/Button'
import { 
  Folder, Link as LinkIcon, EyeOff, RefreshCw, CheckCircle2, 
  Loader2, Sparkles 
} from 'lucide-react'

interface RowState {
  playlist_url: string
  rename_folder: boolean
  selected: boolean
}

export function UnmanagedFoldersManager() {
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const confirm = useConfirm()

  const [rowStates, setRowStates] = useState<Record<string, RowState>>({})
  const [globalRename, setGlobalRename] = useState<boolean>(false)

  // Fetch unmanaged folders
  const { data, isLoading, isFetching, refetch } = useQuery({
    queryKey: ['unmanagedFolders'],
    queryFn: async () => {
      const res = await configApi.getUnmanagedFolders()
      return res.data
    },
  })

  useEffect(() => {
    if (data?.unmanaged_folders) {
      setRowStates(prev => {
        const next: Record<string, RowState> = { ...prev }
        data.unmanaged_folders.forEach((folder: UnmanagedFolder) => {
          if (!next[folder.folder_name]) {
            next[folder.folder_name] = {
              playlist_url: '',
              rename_folder: globalRename,
              selected: false,
            }
          }
        })
        return next
      })
    }
  }, [data, globalRename])

  // Batch Link Mutation
  const batchLinkMutation = useMutation({
    mutationFn: async ({
      items,
      global_rename,
    }: {
      items: Array<{ folder_name: string; folder_path: string; playlist_url: string; rename_folder?: boolean }>
      global_rename: boolean
    }) => {
      const res = await configApi.batchLinkUnmanagedFolders(items, global_rename)
      return res.data
    },
    onSuccess: (res) => {
      if (res.linked_count > 0) {
        toast.success(`Successfully linked ${res.linked_count} playlist(s)!`)
        queryClient.invalidateQueries({ queryKey: ['playlists'] })
        queryClient.invalidateQueries({ queryKey: ['unmanagedFolders'] })
        refetch()
      }
      if (res.failed_count > 0) {
        toast.warning(`${res.failed_count} folder(s) could not be linked. Check the URLs and try again.`)
      }
    },
    onError: (err: any) => {
      toast.error(`Linking failed: ${err.response?.data?.detail || err.message}`)
    }
  })

  // Bulk Exclude Mutation
  const bulkExcludeMutation = useMutation({
    mutationFn: async (folderNames: string[]) => {
      const res = await configApi.batchExcludeFolders(folderNames)
      return res.data
    },
    onSuccess: (_, folderNames) => {
      toast.success(`Excluded ${folderNames.length} folder(s) from auto-discovery.`)
      queryClient.invalidateQueries({ queryKey: ['config'] })
      queryClient.invalidateQueries({ queryKey: ['unmanagedFolders'] })
      refetch()
    },
    onError: (err: any) => {
      toast.error(`Failed to exclude folders: ${err.response?.data?.detail || err.message}`)
    }
  })

  const folders: UnmanagedFolder[] = data?.unmanaged_folders || []

  const updateRow = (folderName: string, updates: Partial<RowState>) => {
    setRowStates(prev => ({
      ...prev,
      [folderName]: {
        ...(prev[folderName] || { playlist_url: '', rename_folder: globalRename, selected: false }),
        ...updates,
      }
    }))
  }

  const allSelected = folders.length > 0 && folders.every((f: UnmanagedFolder) => rowStates[f.folder_name]?.selected)
  const toggleSelectAll = () => {
    const nextState = !allSelected
    setRowStates(prev => {
      const next: Record<string, RowState> = { ...prev }
      folders.forEach((f: UnmanagedFolder) => {
        next[f.folder_name] = {
          ...(next[f.folder_name] || { playlist_url: '', rename_folder: globalRename, selected: false }),
          selected: nextState,
        }
      })
      return next
    })
  }

  // Count how many have valid URLs entered
  const mappedCount = folders.filter((f: UnmanagedFolder) => (rowStates[f.folder_name]?.playlist_url || '').trim()).length
  const selectedCount = folders.filter((f: UnmanagedFolder) => rowStates[f.folder_name]?.selected).length

  // Handle Apply All Mapped
  const handleApplyMapped = async () => {
    const itemsToLink = folders
      .filter((f: UnmanagedFolder) => (rowStates[f.folder_name]?.playlist_url || '').trim())
      .map((f: UnmanagedFolder) => ({
        folder_name: f.folder_name,
        folder_path: f.folder_path,
        playlist_url: rowStates[f.folder_name].playlist_url.trim(),
        rename_folder: rowStates[f.folder_name].rename_folder ?? globalRename,
      }))

    if (itemsToLink.length === 0) {
      toast.info('Please enter at least one YouTube Playlist URL before linking.')
      return
    }

    batchLinkMutation.mutate({
      items: itemsToLink,
      global_rename: globalRename,
    })
  }

  // Handle Single Row Link
  const handleLinkSingle = (folder: UnmanagedFolder) => {
    const url = (rowStates[folder.folder_name]?.playlist_url || '').trim()
    if (!url) {
      toast.info(`Please enter a YouTube playlist URL for folder "${folder.folder_name}".`)
      return
    }

    batchLinkMutation.mutate({
      items: [{
        folder_name: folder.folder_name,
        folder_path: folder.folder_path,
        playlist_url: url,
        rename_folder: rowStates[folder.folder_name]?.rename_folder ?? globalRename,
      }],
      global_rename: globalRename,
    })
  }

  // Handle Single Row Exclude
  const handleExcludeSingle = async (folder: UnmanagedFolder) => {
    const confirmed = await confirm({
      title: 'Exclude Folder',
      message: `Are you sure you want to exclude "${folder.folder_name}" from future scans? The directory and its files will remain on disk.`,
      confirmText: 'Exclude',
      isDestructive: false,
    })
    if (confirmed) {
      bulkExcludeMutation.mutate([folder.folder_name])
    }
  }

  // Handle Bulk Exclude
  const handleBulkExclude = async () => {
    const selectedFolders = folders.filter((f: UnmanagedFolder) => rowStates[f.folder_name]?.selected).map((f: UnmanagedFolder) => f.folder_name)
    if (selectedFolders.length === 0) {
      toast.info('Please select one or more folders to exclude.')
      return
    }

    const confirmed = await confirm({
      title: 'Bulk Exclude Folders',
      message: `Exclude ${selectedFolders.length} selected folder(s) from auto-discovery? Physical files on disk are never touched.`,
      confirmText: 'Exclude Selected',
      isDestructive: false,
    })
    if (confirmed) {
      bulkExcludeMutation.mutate(selectedFolders)
    }
  }

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6 shadow-xl space-y-6">
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <Folder className="w-5 h-5 text-amber-400" />
            <h3 className="text-lg font-bold text-white">
              Unmanaged Folders
            </h3>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-950/60 text-amber-300 border border-amber-800/80">
              {folders.length} Found
            </span>
          </div>
          <p className="text-xs text-gray-400 mt-1">
            Subdirectories inside your downloads folder that lack YouTube metadata. Map them to playlist URLs or exclude them.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={() => refetch()}
            disabled={isLoading || isFetching}
            className="flex items-center gap-1.5 text-xs bg-gray-800 hover:bg-gray-700 text-gray-200 border border-gray-700"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isFetching ? 'animate-spin' : ''}`} />
            <span>Rescan</span>
          </Button>
        </div>
      </div>

      {isLoading ? (
        <div className="py-12 text-center text-gray-400 flex flex-col items-center justify-center gap-3">
          <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
          <span className="text-sm">Scanning directory for unmanaged folders...</span>
        </div>
      ) : folders.length === 0 ? (
        <div className="py-10 text-center bg-gray-950/40 border border-gray-800/60 rounded-xl">
          <CheckCircle2 className="w-10 h-10 text-emerald-400 mx-auto mb-2 opacity-80" />
          <p className="text-sm font-medium text-gray-200">No unmanaged folders found</p>
          <p className="text-xs text-gray-400 mt-1">
            All subdirectories are managed playlists or excluded.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {/* Action Toolbar */}
          <div className="flex flex-wrap items-center justify-between gap-3 p-3 bg-gray-950/60 border border-gray-800/80 rounded-xl">
            <div className="flex items-center gap-4 flex-wrap">
              <label className="flex items-center gap-2 text-xs font-medium text-gray-300 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={globalRename}
                  onChange={(e) => {
                    const checked = e.target.checked
                    setGlobalRename(checked)
                    // Apply to all rows currently matching old default
                    setRowStates(prev => {
                      const next: Record<string, RowState> = { ...prev }
                      folders.forEach((f: UnmanagedFolder) => {
                        if (next[f.folder_name]) {
                          next[f.folder_name].rename_folder = checked
                        }
                      })
                      return next
                    })
                  }}
                  className="rounded border-gray-700 bg-gray-900 text-blue-600 focus:ring-blue-500 w-4 h-4"
                />
                <span>Rename folder on disk to match playlist title</span>
              </label>

              {selectedCount > 0 && (
                <span className="text-xs text-gray-400">
                  {selectedCount} selected
                </span>
              )}
            </div>

            <div className="flex items-center gap-2 flex-wrap">
              {selectedCount > 0 && (
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={handleBulkExclude}
                  disabled={bulkExcludeMutation.isPending}
                  className="text-xs flex items-center gap-1.5 bg-gray-800 hover:bg-gray-700 text-gray-300 border border-gray-700"
                >
                  <EyeOff className="w-3.5 h-3.5" />
                  <span>Exclude Selected ({selectedCount})</span>
                </Button>
              )}

              <Button
                type="button"
                variant="primary"
                size="sm"
                onClick={handleApplyMapped}
                disabled={mappedCount === 0 || batchLinkMutation.isPending}
                className="text-xs flex items-center gap-1.5 bg-blue-600 hover:bg-blue-500 text-white font-semibold"
              >
                {batchLinkMutation.isPending ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <Sparkles className="w-3.5 h-3.5" />
                )}
                <span>Apply All Mapped ({mappedCount})</span>
              </Button>
            </div>
          </div>

          {/* Interactive Batch Mapping Table */}
          <div className="overflow-x-auto border border-gray-800 rounded-xl">
            <table className="w-full text-left text-xs text-gray-300">
              <thead className="bg-gray-950/80 text-gray-400 uppercase tracking-wider font-semibold border-b border-gray-800">
                <tr>
                  <th className="p-3 w-10 text-center">
                    <input
                      type="checkbox"
                      checked={allSelected}
                      onChange={toggleSelectAll}
                      className="rounded border-gray-700 bg-gray-900 text-blue-600 focus:ring-blue-500 w-4 h-4"
                    />
                  </th>
                  <th className="p-3 min-w-[180px]">Folder Name</th>
                  <th className="p-3 min-w-[120px]">Detected Files</th>
                  <th className="p-3 min-w-[280px]">YouTube Playlist URL (Tab to next)</th>
                  <th className="p-3 w-28 text-center">Rename Disk</th>
                  <th className="p-3 w-32 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800/60 bg-gray-900/40">
                {folders.map((folder: UnmanagedFolder) => {
                  const state = rowStates[folder.folder_name] || {
                    playlist_url: '',
                    rename_folder: globalRename,
                    selected: false,
                  }

                  const hasUrl = Boolean(state.playlist_url?.trim())

                  return (
                    <tr
                      key={folder.folder_name}
                      className={`transition-colors hover:bg-gray-800/40 ${
                        state.selected ? 'bg-blue-950/20' : ''
                      }`}
                    >
                      <td className="p-3 text-center">
                        <input
                          type="checkbox"
                          checked={state.selected}
                          onChange={(e) => updateRow(folder.folder_name, { selected: e.target.checked })}
                          className="rounded border-gray-700 bg-gray-900 text-blue-600 focus:ring-blue-500 w-4 h-4"
                        />
                      </td>

                      <td className="p-3">
                        <div className="flex items-center gap-2">
                          <Folder className="w-4 h-4 text-amber-400 shrink-0" />
                          <span className="font-semibold text-white truncate max-w-[220px]" title={folder.folder_name}>
                            {folder.folder_name}
                          </span>
                        </div>
                      </td>

                      <td className="p-3">
                        <div className="flex items-center gap-1.5 flex-wrap">
                          {folder.video_count > 0 && (
                            <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-blue-950/60 text-blue-300 border border-blue-800/60">
                              {folder.video_count} video{folder.video_count > 1 ? 's' : ''}
                            </span>
                          )}
                          {folder.audio_count > 0 && (
                            <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-purple-950/60 text-purple-300 border border-purple-800/60">
                              {folder.audio_count} audio
                            </span>
                          )}
                          {folder.video_count === 0 && folder.audio_count === 0 && (
                            <span className="text-gray-500 text-[11px]">Empty</span>
                          )}
                        </div>
                      </td>

                      <td className="p-3">
                        <input
                          type="text"
                          value={state.playlist_url}
                          onChange={(e) => updateRow(folder.folder_name, { playlist_url: e.target.value })}
                          placeholder="https://www.youtube.com/playlist?list=..."
                          className="w-full px-3 py-1.5 text-xs bg-gray-950 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500 font-mono"
                        />
                      </td>

                      <td className="p-3 text-center">
                        <input
                          type="checkbox"
                          checked={state.rename_folder}
                          onChange={(e) => updateRow(folder.folder_name, { rename_folder: e.target.checked })}
                          className="rounded border-gray-700 bg-gray-900 text-blue-600 focus:ring-blue-500 w-4 h-4"
                          title="Rename disk folder to match playlist title"
                        />
                      </td>

                      <td className="p-3 text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          <button
                            type="button"
                            onClick={() => handleLinkSingle(folder)}
                            disabled={!hasUrl || batchLinkMutation.isPending}
                            className={`p-1.5 rounded-lg text-xs font-semibold transition-colors flex items-center gap-1 ${
                              hasUrl
                                ? 'bg-blue-600 hover:bg-blue-500 text-white'
                                : 'bg-gray-800 text-gray-500 cursor-not-allowed'
                            }`}
                            title="Link this folder"
                          >
                            <LinkIcon className="w-3.5 h-3.5" />
                            <span className="hidden sm:inline">Link</span>
                          </button>

                          <button
                            type="button"
                            onClick={() => handleExcludeSingle(folder)}
                            disabled={bulkExcludeMutation.isPending}
                            className="p-1.5 rounded-lg text-gray-400 hover:text-gray-200 hover:bg-gray-800 transition-colors"
                            title="Exclude this folder"
                          >
                            <EyeOff className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
