import { useState, useEffect, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { configApi, type UnmanagedFolder, type ExcludedFolderItem } from '../../services/api'
import { useToast } from '../../context/ToastContext'
import { useConfirm } from '../../context/ConfirmContext'
import { Button } from '../ui/Button'
import { 
  Folder, Link as LinkIcon, EyeOff, RefreshCw, CheckCircle2, 
  Loader2, Sparkles, Undo2, Lock,
  ArrowUpDown, ArrowUp, ArrowDown
} from 'lucide-react'

interface RowState {
  playlist_url: string
  rename_folder: boolean
  selected: boolean
}

export type UnmanagedSortField = 'folder_name' | 'files' | 'playlist_url'
export type ExcludedSortField = 'folder_name' | 'reason' | 'created_at'

export function UnmanagedFoldersManager() {
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const confirm = useConfirm()

  const [activeTab, setActiveTab] = useState<'unmanaged' | 'excluded'>('unmanaged')
  const [rowStates, setRowStates] = useState<Record<string, RowState>>({})
  const [globalRename, setGlobalRename] = useState<boolean>(false)
  const [renameInitialized, setRenameInitialized] = useState<boolean>(false)
  const [rowErrors, setRowErrors] = useState<Record<string, string>>({})

  // Sorting state for Unmanaged tab
  const [unmanagedSortField, setUnmanagedSortField] = useState<UnmanagedSortField>('folder_name')
  const [unmanagedSortDirection, setUnmanagedSortDirection] = useState<'asc' | 'desc'>('asc')

  // Sorting state for Excluded tab
  const [excludedSortField, setExcludedSortField] = useState<ExcludedSortField>('folder_name')
  const [excludedSortDirection, setExcludedSortDirection] = useState<'asc' | 'desc'>('asc')

  // Fetch app config to read global rename_folder_on_link default
  const { data: appConfig } = useQuery({
    queryKey: ['config'],
    queryFn: async () => {
      const res = await configApi.get()
      return res.data
    },
  })

  useEffect(() => {
    if (appConfig && !renameInitialized) {
      setGlobalRename(Boolean(appConfig.rename_folder_on_link))
      setRenameInitialized(true)
    }
  }, [appConfig, renameInitialized])

  // Fetch unmanaged & excluded folders
  const { data, isLoading, isFetching, refetch } = useQuery({
    queryKey: ['unmanagedFolders'],
    queryFn: async () => {
      const res = await configApi.getUnmanagedFolders()
      return res.data
    },
  })

  const folders: UnmanagedFolder[] = data?.unmanaged_folders || []
  const excludedFolders: ExcludedFolderItem[] = data?.excluded_folders || []

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
      if (res.results && Array.isArray(res.results)) {
        const newErrors: Record<string, string> = {}
        for (const r of res.results) {
          const key = r.folder_name || (r.folder_path ? r.folder_path.split(/[/\\]/).pop() || '' : '')
          if (r.success === false && key) {
            newErrors[key] = r.error || 'Invalid or inaccessible playlist URL'
          }
        }
        setRowErrors(prev => ({ ...prev, ...newErrors }))
      }
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

  // Restore Excluded Folder Mutation
  const restoreMutation = useMutation({
    mutationFn: async (folderName: string) => {
      const res = await configApi.restoreExcludedFolder(folderName)
      return res.data
    },
    onSuccess: (_, folderName) => {
      toast.success(`Restored "${folderName}" to unmanaged folders.`)
      queryClient.invalidateQueries({ queryKey: ['config'] })
      queryClient.invalidateQueries({ queryKey: ['unmanagedFolders'] })
      refetch()
    },
    onError: (err: any) => {
      toast.error(`Failed to restore folder: ${err.response?.data?.detail || err.message}`)
    }
  })

  const updateRow = (folderName: string, updates: Partial<RowState>) => {
    setRowStates(prev => ({
      ...prev,
      [folderName]: {
        ...(prev[folderName] || { playlist_url: '', rename_folder: globalRename, selected: false }),
        ...updates,
      }
    }))
    if (updates.playlist_url !== undefined) {
      setRowErrors(prev => {
        if (!prev[folderName]) return prev
        const next = { ...prev }
        delete next[folderName]
        return next
      })
    }
  }

  const candidateFolders = folders.filter((f: UnmanagedFolder) => !f.is_adhoc)
  const allSelected = candidateFolders.length > 0 && candidateFolders.every((f: UnmanagedFolder) => rowStates[f.folder_name]?.selected)
  const toggleSelectAll = () => {
    const nextState = !allSelected
    setRowStates(prev => {
      const next: Record<string, RowState> = { ...prev }
      candidateFolders.forEach((f: UnmanagedFolder) => {
        next[f.folder_name] = {
          ...(next[f.folder_name] || { playlist_url: '', rename_folder: globalRename, selected: false }),
          selected: nextState,
        }
      })
      return next
    })
  }

  const isValidPlaylistUrl = (url: string) => {
    const trimmed = url.trim()
    return trimmed.startsWith('http://') || trimmed.startsWith('https://')
  }

  // Count how many have valid URLs entered
  const mappedCount = candidateFolders.filter((f: UnmanagedFolder) => isValidPlaylistUrl(rowStates[f.folder_name]?.playlist_url || '')).length
  const selectedCount = candidateFolders.filter((f: UnmanagedFolder) => rowStates[f.folder_name]?.selected).length

  // Handle Apply All Mapped
  const handleApplyMapped = async () => {
    const entered = folders.filter((f: UnmanagedFolder) => (rowStates[f.folder_name]?.playlist_url || '').trim())
    if (entered.length === 0) {
      toast.info('Please enter at least one YouTube Playlist URL before linking.')
      return
    }

    const invalidItems = entered.filter((f: UnmanagedFolder) => !isValidPlaylistUrl(rowStates[f.folder_name].playlist_url))
    if (invalidItems.length > 0) {
      toast.error(`Invalid URL for "${invalidItems[0].folder_name}". URLs must start with http:// or https://`)
      return
    }

    const itemsToLink = entered.map((f: UnmanagedFolder) => ({
      folder_name: f.folder_name,
      folder_path: f.folder_path,
      playlist_url: rowStates[f.folder_name].playlist_url.trim(),
      rename_folder: rowStates[f.folder_name].rename_folder ?? globalRename,
    }))

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
    if (!isValidPlaylistUrl(url)) {
      toast.error(`Invalid URL for "${folder.folder_name}". URLs must start with http:// or https://`)
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

  // Sorting handlers
  const handleUnmanagedSort = (field: UnmanagedSortField) => {
    if (unmanagedSortField === field) {
      setUnmanagedSortDirection((prev: 'asc' | 'desc') => (prev === 'asc' ? 'desc' : 'asc'))
    } else {
      setUnmanagedSortField(field)
      setUnmanagedSortDirection('asc')
    }
  }

  const handleExcludedSort = (field: ExcludedSortField) => {
    if (excludedSortField === field) {
      setExcludedSortDirection((prev: 'asc' | 'desc') => (prev === 'asc' ? 'desc' : 'asc'))
    } else {
      setExcludedSortField(field)
      setExcludedSortDirection('asc')
    }
  }

  const renderUnmanagedSortIcon = (field: UnmanagedSortField) => {
    if (unmanagedSortField !== field) {
      return <ArrowUpDown className="w-3.5 h-3.5 text-gray-500 opacity-60" />
    }
    return unmanagedSortDirection === 'asc' ? (
      <ArrowUp className="w-3.5 h-3.5 text-blue-400" />
    ) : (
      <ArrowDown className="w-3.5 h-3.5 text-blue-400" />
    )
  }

  const renderExcludedSortIcon = (field: ExcludedSortField) => {
    if (excludedSortField !== field) {
      return <ArrowUpDown className="w-3.5 h-3.5 text-gray-500 opacity-60" />
    }
    return excludedSortDirection === 'asc' ? (
      <ArrowUp className="w-3.5 h-3.5 text-blue-400" />
    ) : (
      <ArrowDown className="w-3.5 h-3.5 text-blue-400" />
    )
  }

  const sortedFolders = useMemo(() => {
    return [...folders].sort((a: UnmanagedFolder, b: UnmanagedFolder) => {
      let comparison = 0
      switch (unmanagedSortField) {
        case 'folder_name':
          comparison = (a.folder_name || '').localeCompare(b.folder_name || '')
          break
        case 'files': {
          const aCount = (a.video_count || 0) + (a.audio_count || 0)
          const bCount = (b.video_count || 0) + (b.audio_count || 0)
          comparison = aCount - bCount
          break
        }
        case 'playlist_url': {
          const aUrl = rowStates[a.folder_name]?.playlist_url || ''
          const bUrl = rowStates[b.folder_name]?.playlist_url || ''
          comparison = aUrl.localeCompare(bUrl)
          break
        }
        default:
          comparison = 0
      }
      return unmanagedSortDirection === 'asc' ? comparison : -comparison
    })
  }, [folders, unmanagedSortField, unmanagedSortDirection, rowStates])

  const sortedExcludedFolders = useMemo(() => {
    return [...excludedFolders].sort((a: ExcludedFolderItem, b: ExcludedFolderItem) => {
      let comparison = 0
      switch (excludedSortField) {
        case 'folder_name':
          comparison = (a.folder_name || '').localeCompare(b.folder_name || '')
          break
        case 'reason': {
          const aReason = a.reason === 'config_env' ? 'Config (.env)' : a.reason || 'user_excluded'
          const bReason = b.reason === 'config_env' ? 'Config (.env)' : b.reason || 'user_excluded'
          comparison = aReason.localeCompare(bReason)
          break
        }
        case 'created_at': {
          const aTime = a.created_at ? new Date(a.created_at).getTime() : 0
          const bTime = b.created_at ? new Date(b.created_at).getTime() : 0
          comparison = aTime - bTime
          break
        }
        default:
          comparison = 0
      }
      return excludedSortDirection === 'asc' ? comparison : -comparison
    })
  }, [excludedFolders, excludedSortField, excludedSortDirection])

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6 shadow-xl space-y-6">
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <Folder className="w-5 h-5 text-amber-400" />
            <h3 className="text-lg font-bold text-white">
              Folder & Auto-Discovery Management
            </h3>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-950/60 text-amber-300 border border-amber-800/80">
              {folders.length} Unmanaged · {excludedFolders.length} Excluded
            </span>
          </div>
          <p className="text-xs text-gray-400 mt-1">
            Subdirectories inside your downloads folder. Link unmanaged directories to YouTube playlists or restore excluded ones.
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

      {/* Tabs */}
      <div className="flex border-b border-gray-800 gap-6">
        <button
          type="button"
          onClick={() => setActiveTab('unmanaged')}
          className={`pb-3 text-sm font-semibold flex items-center gap-2 border-b-2 transition-colors ${
            activeTab === 'unmanaged'
              ? 'border-blue-500 text-blue-400'
              : 'border-transparent text-gray-400 hover:text-gray-300'
          }`}
        >
          <Folder className="w-4 h-4" />
          <span>Unmanaged Folders</span>
          <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-gray-800 text-gray-300">
            {folders.length}
          </span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('excluded')}
          className={`pb-3 text-sm font-semibold flex items-center gap-2 border-b-2 transition-colors ${
            activeTab === 'excluded'
              ? 'border-blue-500 text-blue-400'
              : 'border-transparent text-gray-400 hover:text-gray-300'
          }`}
        >
          <EyeOff className="w-4 h-4" />
          <span>Excluded Folders</span>
          <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-gray-800 text-gray-300">
            {excludedFolders.length}
          </span>
        </button>
      </div>

      {isLoading ? (
        <div className="py-12 text-center text-gray-400 flex flex-col items-center justify-center gap-3">
          <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
          <span className="text-sm">Scanning directory for folders...</span>
        </div>
      ) : activeTab === 'excluded' ? (
        <div>
          {excludedFolders.length === 0 ? (
            <div className="py-10 text-center bg-gray-950/40 border border-gray-800/60 rounded-xl">
              <CheckCircle2 className="w-10 h-10 text-emerald-400 mx-auto mb-2 opacity-80" />
              <p className="text-sm font-medium text-gray-200">No excluded folders</p>
              <p className="text-xs text-gray-400 mt-1">
                Any folders you exclude from auto-discovery will be listed here with 1-click restore.
              </p>
            </div>
          ) : (
            <div className="border border-gray-800 rounded-xl overflow-hidden shadow-inner bg-gray-950/40">
              <table className="w-full text-left text-xs text-gray-300">
                <thead className="bg-gray-950/90 text-gray-400 font-semibold border-b border-gray-800 uppercase tracking-wider">
                  <tr>
                    <th
                      className="p-3 cursor-pointer hover:text-gray-200 transition-colors select-none"
                      onClick={() => handleExcludedSort('folder_name')}
                    >
                      <div className="flex items-center gap-1.5">
                        <span>Folder Name</span>
                        {renderExcludedSortIcon('folder_name')}
                      </div>
                    </th>
                    <th
                      className="p-3 cursor-pointer hover:text-gray-200 transition-colors select-none"
                      onClick={() => handleExcludedSort('reason')}
                    >
                      <div className="flex items-center gap-1.5">
                        <span>Exclusion Reason</span>
                        {renderExcludedSortIcon('reason')}
                      </div>
                    </th>
                    <th
                      className="p-3 cursor-pointer hover:text-gray-200 transition-colors select-none"
                      onClick={() => handleExcludedSort('created_at')}
                    >
                      <div className="flex items-center gap-1.5">
                        <span>Date Excluded</span>
                        {renderExcludedSortIcon('created_at')}
                      </div>
                    </th>
                    <th className="p-3 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-800/70">
                  {sortedExcludedFolders.map((item: ExcludedFolderItem) => (
                    <tr key={item.folder_name} className="hover:bg-gray-800/30 transition-colors">
                      <td className="p-3 font-medium text-gray-100 flex items-center gap-2">
                        <Folder className="w-4 h-4 text-gray-500 shrink-0" />
                        <span className="font-mono text-xs truncate max-w-xs">{item.folder_name}</span>
                      </td>
                      <td className="p-3 text-gray-400">
                        <span className={`px-2 py-0.5 rounded text-[11px] font-medium border ${
                          item.is_system
                            ? 'bg-purple-950/40 text-purple-300 border-purple-800/80'
                            : 'bg-gray-800 text-gray-300 border-gray-700'
                        }`}>
                          {item.reason === 'config_env' ? 'Config (.env)' : item.reason || 'user_excluded'}
                        </span>
                      </td>
                      <td className="p-3 text-gray-400">
                        {item.created_at ? new Date(item.created_at).toLocaleDateString() : '—'}
                      </td>
                      <td className="p-3 text-right">
                        {item.is_system ? (
                          <span className="text-[11px] text-gray-500 italic pr-2" title="Configured via environment EXCLUDED_DIRS">
                            Non-actionable (System)
                          </span>
                        ) : (
                          <Button
                            type="button"
                            variant="secondary"
                            size="sm"
                            disabled={restoreMutation.isPending}
                            onClick={() => restoreMutation.mutate(item.folder_name)}
                            className="text-xs bg-gray-800 hover:bg-gray-700 text-gray-200 border border-gray-700 inline-flex items-center gap-1.5"
                            title="Restore this folder to Unmanaged so it can be linked"
                          >
                            <Undo2 className="w-3.5 h-3.5" />
                            <span>Restore</span>
                          </Button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
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
                <span>Rename Disk Folder on Link</span>
              </label>

              <span className="text-xs text-gray-500">
                {mappedCount} of {folders.length} mapped
              </span>
            </div>

            <div className="flex items-center gap-2">
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={handleBulkExclude}
                disabled={selectedCount === 0 || bulkExcludeMutation.isPending}
                className="flex items-center gap-1.5 text-xs bg-gray-800 hover:bg-gray-700 text-gray-300 border border-gray-700 disabled:opacity-50"
              >
                <EyeOff className="w-3.5 h-3.5" />
                <span>Exclude Selected ({selectedCount})</span>
              </Button>

              <Button
                type="button"
                variant="primary"
                size="sm"
                onClick={handleApplyMapped}
                disabled={mappedCount === 0 || batchLinkMutation.isPending}
                className="flex items-center gap-1.5 text-xs bg-blue-600 hover:bg-blue-500 text-white shadow-lg shadow-blue-500/20 disabled:opacity-50"
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

          {/* Table */}
          <div className="border border-gray-800 rounded-xl overflow-hidden shadow-inner bg-gray-950/40">
            <table className="w-full text-left text-xs text-gray-300">
              <thead className="bg-gray-950/90 text-gray-400 font-semibold border-b border-gray-800 uppercase tracking-wider">
                <tr>
                  <th className="p-3 w-10 text-center">
                    <input
                      type="checkbox"
                      checked={allSelected}
                      onChange={toggleSelectAll}
                      className="rounded border-gray-700 bg-gray-900 text-blue-600 focus:ring-blue-500 w-4 h-4"
                      title="Select all folders"
                    />
                  </th>
                  <th
                    className="p-3 cursor-pointer hover:text-gray-200 transition-colors select-none"
                    onClick={() => handleUnmanagedSort('folder_name')}
                  >
                    <div className="flex items-center gap-1.5">
                      <span>Folder Name</span>
                      {renderUnmanagedSortIcon('folder_name')}
                    </div>
                  </th>
                  <th
                    className="p-3 cursor-pointer hover:text-gray-200 transition-colors select-none"
                    onClick={() => handleUnmanagedSort('files')}
                  >
                    <div className="flex items-center gap-1.5">
                      <span>Files</span>
                      {renderUnmanagedSortIcon('files')}
                    </div>
                  </th>
                  <th
                    className="p-3 w-2/5 cursor-pointer hover:text-gray-200 transition-colors select-none"
                    onClick={() => handleUnmanagedSort('playlist_url')}
                  >
                    <div className="flex items-center gap-1.5">
                      <span>YouTube Playlist URL</span>
                      {renderUnmanagedSortIcon('playlist_url')}
                    </div>
                  </th>
                  <th className="p-3 text-center w-28">Rename Folder</th>
                  <th className="p-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800/70">
                {sortedFolders.map((folder: UnmanagedFolder) => {
                  const state = rowStates[folder.folder_name] || {
                    playlist_url: '',
                    rename_folder: globalRename,
                    selected: false,
                  }
                  const hasUrl = Boolean(state.playlist_url.trim())
                  const isUrlValid = isValidPlaylistUrl(state.playlist_url)
                  const rowError = rowErrors[folder.folder_name]

                  return (
                    <tr
                      key={folder.folder_name}
                      className={`hover:bg-gray-800/40 transition-colors ${
                        state.selected ? 'bg-blue-950/20' : ''
                      }`}
                    >
                      <td className="p-3 text-center">
                        <input
                          type="checkbox"
                          disabled={folder.is_adhoc}
                          checked={state.selected}
                          onChange={(e) => updateRow(folder.folder_name, { selected: e.target.checked })}
                          className="rounded border-gray-700 bg-gray-900 text-blue-600 focus:ring-blue-500 w-4 h-4 disabled:opacity-30 disabled:cursor-not-allowed"
                          title={folder.is_adhoc ? "Ad-hoc download directory cannot be linked as a playlist" : undefined}
                        />
                      </td>

                      <td className="p-3 font-medium text-gray-100 flex items-center gap-2">
                        <Folder className={`w-4 h-4 shrink-0 ${folder.is_adhoc ? 'text-cyan-400' : 'text-amber-500'}`} />
                        <span className="font-mono text-xs truncate max-w-xs" title={folder.folder_name}>
                          {folder.folder_name}
                        </span>
                        {folder.is_adhoc && (
                          <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-cyan-950/60 text-cyan-300 border border-cyan-800/80">
                            {folder.adhoc_type === 'system_default' ? 'Ad-hoc (Default)' : 'Ad-hoc (Config)'}
                          </span>
                        )}
                      </td>

                      <td className="p-3 text-gray-400">
                        {folder.video_count > 0 && <span>{folder.video_count} vids </span>}
                        {folder.audio_count > 0 && <span>{folder.audio_count} aud </span>}
                        {folder.video_count === 0 && folder.audio_count === 0 && (
                          <span className="text-gray-600">empty</span>
                        )}
                      </td>

                      <td className="p-3">
                        {folder.is_adhoc ? (
                          <span className="text-[11px] text-gray-400 italic">
                            Dedicated Ad-hoc & Quick Downloads directory (managed separately)
                          </span>
                        ) : (
                          <div className="space-y-1">
                            <input
                              type="text"
                              placeholder="https://www.youtube.com/playlist?list=..."
                              value={state.playlist_url}
                              onChange={(e) => updateRow(folder.folder_name, { playlist_url: e.target.value })}
                              className={`w-full bg-gray-900 border rounded-lg px-2.5 py-1.5 text-xs text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-1 transition-colors ${
                                rowError
                                  ? 'border-rose-500 focus:ring-rose-500 bg-rose-950/20'
                                  : hasUrl
                                  ? isUrlValid
                                    ? 'border-emerald-700 focus:ring-emerald-500'
                                    : 'border-rose-600 focus:ring-rose-500'
                                  : 'border-gray-700 focus:ring-blue-500'
                              }`}
                            />
                            {rowError ? (
                              <p className="text-[10px] text-rose-400 font-medium flex items-center gap-1">
                                <span>⚠️</span>
                                <span>{rowError}</span>
                              </p>
                            ) : hasUrl && !isUrlValid ? (
                              <p className="text-[10px] text-rose-400 font-medium">
                                Must start with http:// or https://
                              </p>
                            ) : null}
                          </div>
                        )}
                      </td>

                      <td className="p-3 text-center">
                        {folder.is_adhoc ? (
                          <span className="text-gray-600">—</span>
                        ) : (
                          <input
                            type="checkbox"
                            checked={state.rename_folder}
                            onChange={(e) => updateRow(folder.folder_name, { rename_folder: e.target.checked })}
                            className="rounded border-gray-700 bg-gray-900 text-blue-600 focus:ring-blue-500 w-4 h-4"
                            title="Rename disk folder to match playlist title"
                          />
                        )}
                      </td>

                      <td className="p-3 text-right">
                        {folder.is_adhoc ? (
                          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-medium bg-gray-800/70 text-gray-400 border border-gray-700/60">
                            <Lock className="w-3 h-3 text-gray-500" />
                            <span>Ad-hoc Storage</span>
                          </span>
                        ) : (
                          <div className="flex items-center justify-end gap-1.5">
                            <button
                              type="button"
                              onClick={() => handleLinkSingle(folder)}
                              disabled={!hasUrl || !isUrlValid || batchLinkMutation.isPending}
                              className={`px-2.5 py-1.5 rounded-lg text-xs font-semibold transition-colors flex items-center gap-1.5 ${
                                hasUrl && isUrlValid
                                  ? 'bg-blue-600 hover:bg-blue-500 text-white shadow-2xs'
                                  : 'bg-gray-800 text-gray-500 cursor-not-allowed'
                              }`}
                              title={hasUrl && isUrlValid ? 'Link this folder' : 'Enter a valid URL (http:// or https://) to link'}
                            >
                              <LinkIcon className="w-3.5 h-3.5" />
                              <span>Link</span>
                            </button>

                            <button
                              type="button"
                              onClick={() => handleExcludeSingle(folder)}
                              disabled={bulkExcludeMutation.isPending}
                              className="px-2.5 py-1.5 rounded-lg text-xs font-semibold transition-colors flex items-center gap-1.5 bg-amber-950/40 text-amber-300 border border-amber-800/80 hover:bg-amber-900/60 hover:text-amber-200 shadow-2xs"
                              title="Exclude this folder from future scans"
                            >
                              <EyeOff className="w-3.5 h-3.5 text-amber-400" />
                              <span>Exclude</span>
                            </button>
                          </div>
                        )}
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
