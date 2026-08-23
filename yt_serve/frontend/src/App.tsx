import React, { useState, useEffect, useRef, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { playlistsApi, jobsApi, configApi, type Config } from './services/api'
import { 
  PlayCircle, Download, Music, Trash2, RefreshCw, Plus, Loader2, Moon, Sun, 
  Settings, FolderOpen, FileText, Edit3, X, FileText as LogIcon, Grid3x3, List, 
  ExternalLink, Search, Terminal, Copy, Check, DownloadCloud, RotateCcw, Activity,
  Info, Zap, Sparkles
} from 'lucide-react'
import type { Playlist, Job } from './services/types'
import { useWebSocketEvents } from './hooks/useWebSocket'
import { InterruptedJobsDialog } from './components/InterruptedJobsDialog'

export interface ActivityLog {
  id: string
  timestamp: string
  source: string
  type: string
  message: string
  level: 'info' | 'warn' | 'error' | 'success'
}

function App() {
  const [activeTab, setActiveTab] = useState<'playlists' | 'logs'>('playlists')
  const [newPlaylistUrl, setNewPlaylistUrl] = useState('')
  // const [selectedPlaylist, setSelectedPlaylist] = useState<number | null>(null)
  const [showSettings, setShowSettings] = useState(false)
  const [showInitialSetup, setShowInitialSetup] = useState(false)
  const [editingExclusions, setEditingExclusions] = useState<Playlist | null>(null)
  const [viewingLogs, setViewingLogs] = useState<Job | null>(null)
  const [interruptedJobs, setInterruptedJobs] = useState<any[]>([])
  const [showInterruptedDialog, setShowInterruptedDialog] = useState(false)
  const [interruptedJobsHandled, setInterruptedJobsHandled] = useState(false)
  const [viewMode, setViewMode] = useState<'grid' | 'list'>(() => {
    const saved = localStorage.getItem('viewMode')
    return (saved as 'grid' | 'list') || 'grid'
  })
  const [expandedRows, setExpandedRows] = useState<Set<number>>(new Set())
  const [darkMode, setDarkMode] = useState(() => {
    const saved = localStorage.getItem('darkMode')
    return saved ? JSON.parse(saved) : false
  })
  const [activityLogs, setActivityLogs] = useState<ActivityLog[]>([])
  const queryClient = useQueryClient()

  const addActivityLog = useCallback((source: string, type: string, message: string, level: 'info' | 'warn' | 'error' | 'success' = 'info') => {
    const timestamp = new Date().toLocaleTimeString()
    setActivityLogs(prev => [
      { id: Math.random().toString(36).substring(2, 9), timestamp, source, type, message, level },
      ...prev.slice(0, 499)
    ])
  }, [])

  // WebSocket event handler for real-time updates
  const handleWebSocketEvent = useCallback((type: string, data: any) => {
    if (type === 'playlist_updated') {
      addActivityLog('WebSocket', 'playlist_updated', `Playlist update signal received (ID: ${data?.playlist_id || 'all'})`, 'info')
      // Force immediate refetch of playlists
      queryClient.invalidateQueries({ queryKey: ['playlists'] })
      queryClient.refetchQueries({ queryKey: ['playlists'] })
    } else if (type === 'connected') {
      addActivityLog('WebSocket', 'connected', 'Connected to real-time events stream', 'success')
    } else if (type === 'job_status') {
      addActivityLog('JobQueue', 'status_change', `Job #${data?.job_id} status changed to ${data?.status}`, 'info')
    }
  }, [queryClient, addActivityLog])

  // Connect to WebSocket for real-time events
  useWebSocketEvents(handleWebSocketEvent)

  // Save view mode to localStorage
  useEffect(() => {
    localStorage.setItem('viewMode', viewMode)
  }, [viewMode])

  const toggleRow = (playlistId: number) => {
    const newExpanded = new Set(expandedRows)
    if (newExpanded.has(playlistId)) {
      newExpanded.delete(playlistId)
    } else {
      newExpanded.add(playlistId)
    }
    setExpandedRows(newExpanded)
  }

  // Check if initial setup is needed
  const { data: config } = useQuery({
    queryKey: ['config'],
    queryFn: async () => {
      const res = await configApi.get()
      return res.data
    },
    staleTime: 0, // Always fetch fresh config
    refetchOnMount: true,
  })

  // Show initial setup modal if needed
  useEffect(() => {
    // Temporarily disabled - user already has config
    if (config?.needs_setup) {
      setShowInitialSetup(true)
    }
  }, [config])

  // Check for interrupted jobs on app initialization
  useEffect(() => {
    const checkInterruptedJobs = async () => {
      if (interruptedJobsHandled) return
      
      try {
        const res = await jobsApi.getInterrupted()
        if (res.data.count > 0) {
          setInterruptedJobs(res.data.jobs)
          setShowInterruptedDialog(true)
        } else {
          setInterruptedJobsHandled(true)
        }
      } catch (error) {
        console.error('Error checking interrupted jobs:', error)
        setInterruptedJobsHandled(true)
      }
    }

    checkInterruptedJobs()
  }, [interruptedJobsHandled])

  // Apply dark mode class to document
  useEffect(() => {
    console.log('Dark mode:', darkMode)
    if (darkMode) {
      document.documentElement.classList.add('dark')
    } else {
      document.documentElement.classList.remove('dark')
    }
    localStorage.setItem('darkMode', JSON.stringify(darkMode))
  }, [darkMode])

  // Fetch playlists (WebSocket provides real-time updates, polling is backup)
  const { data: playlists, isLoading: playlistsLoading } = useQuery({
    queryKey: ['playlists'],
    queryFn: async () => {
      const res = await playlistsApi.list()
      return res.data
    },
    refetchInterval: 30000, // Poll every 30 seconds as backup (WebSocket is primary)
    staleTime: 0, // Always consider data stale to ensure fresh fetches
    refetchOnMount: true,
    refetchOnWindowFocus: true,
  })

  // Fetch jobs
  const { data: jobs } = useQuery({
    queryKey: ['jobs'],
    queryFn: async () => {
      const res = await jobsApi.list()
      return res.data
    },
    refetchInterval: 2000, // Poll every 2 seconds
  })

  // Track completed jobs to refetch playlists only once per completion
  const [completedJobIds, setCompletedJobIds] = useState<Set<number>>(new Set())
  
  useEffect(() => {
    if (jobs) {
      const newlyCompleted = jobs.filter(j => 
        (j.status === 'completed' || j.status === 'failed' || j.status === 'cancelled') &&
        !completedJobIds.has(j.id)
      )
      
      if (newlyCompleted.length > 0) {
        console.log(`[UI] Detected ${newlyCompleted.length} newly completed job(s), refreshing playlists...`)
        
        // Mark these jobs as seen
        setCompletedJobIds(prev => new Set([...prev, ...newlyCompleted.map(j => j.id)]))
        
        // Immediately refetch playlists to get updated stats
        queryClient.invalidateQueries({ queryKey: ['playlists'] })
        queryClient.refetchQueries({ queryKey: ['playlists'] })
      }
    }
  }, [jobs, completedJobIds, queryClient])

  // Add playlist mutation
  const addPlaylist = useMutation({
    mutationFn: (url: string) => playlistsApi.create(url),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['playlists'] })
      setNewPlaylistUrl('')
    },
  })

  // Delete playlist mutation
  const deletePlaylist = useMutation({
    mutationFn: (id: number) => playlistsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['playlists'] })
    },
  })

  // Refresh playlist mutation
  const refreshPlaylist = useMutation({
    mutationFn: (id: number) => playlistsApi.refresh(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['playlists'] })
    },
  })

  // Start job mutation
  const startJob = useMutation({
    mutationFn: ({ playlistId, jobType }: { playlistId: number; jobType: 'download' | 'extract' | 'both' }) =>
      jobsApi.create(playlistId, jobType),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
    },
  })

  // Cancel job mutation
  const cancelJob = useMutation({
    mutationFn: (id: number) => jobsApi.cancel(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
    },
  })

  // Handle interrupted jobs mutations
  const handleInterruptedJobs = useMutation({
    mutationFn: ({
      action,
      jobDecisions,
    }: {
      action: 'resume_all' | 'cancel_all' | 'individual'
      jobDecisions?: Record<string, 'resume' | 'cancel'>
    }) => jobsApi.handleInterrupted(action, jobDecisions),
    onSuccess: () => {
      setShowInterruptedDialog(false)
      setInterruptedJobsHandled(true)
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
      queryClient.invalidateQueries({ queryKey: ['playlists'] })
    },
  })

  // Open folder mutation (simple backend approach)
  const openFolder = useMutation({
    mutationFn: (id: number) => playlistsApi.openFolder(id),
    onError: (error: any) => {
      const errorDetail = error.response?.data?.detail || error.message
      alert(`Error opening folder:\n\n${errorDetail}`)
    },
    onSuccess: (data) => {
      console.log(`Folder opened: ${data.data.path}`)
    },
  })

  const getPlaylistJobs = (playlistId: number): Job[] => {
    return jobs?.filter(j => j.playlist_id === playlistId) || []
  }

  const getRunningJob = (playlistId: number): Job | undefined => {
    return getPlaylistJobs(playlistId).find(j => j.status === 'running' || j.status === 'pending')
  }

  const runningJobsCount = jobs?.filter(j => j.status === 'running' || j.status === 'pending').length || 0

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 transition-colors">
      {/* Header */}
      <header className="bg-white dark:bg-gray-800 shadow">
        <div className="max-w-7xl mx-auto px-4 py-6 flex justify-between items-center flex-wrap gap-4">
          <div className="flex items-center gap-6 flex-wrap">
            <h1 className="text-3xl font-bold text-gray-900 dark:text-white">Playlist Manager</h1>

            {/* Top Navigation Tabs */}
            <div className="flex items-center gap-1 bg-gray-200 dark:bg-gray-700/70 p-1 rounded-xl">
              <button
                onClick={() => setActiveTab('playlists')}
                className={`px-4 py-1.5 rounded-lg text-sm font-semibold transition-all flex items-center gap-2 ${
                  activeTab === 'playlists'
                    ? 'bg-white dark:bg-gray-800 text-blue-600 dark:text-blue-400 shadow-sm'
                    : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'
                }`}
              >
                <PlayCircle className="w-4 h-4" />
                Playlists
              </button>
              <button
                onClick={() => setActiveTab('logs')}
                className={`px-4 py-1.5 rounded-lg text-sm font-semibold transition-all flex items-center gap-2 ${
                  activeTab === 'logs'
                    ? 'bg-white dark:bg-gray-800 text-blue-600 dark:text-blue-400 shadow-sm'
                    : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'
                }`}
              >
                <FileText className="w-4 h-4" />
                Job Logs
                {runningJobsCount > 0 && (
                  <span className="px-1.5 py-0.2 rounded-full text-xs font-bold bg-blue-600 text-white animate-pulse">
                    {runningJobsCount}
                  </span>
                )}
              </button>
            </div>
          </div>
          
          <div className="flex gap-2">
            {/* View Mode Toggle (Only show on playlists tab) */}
            {activeTab === 'playlists' && (
              <div className="flex gap-1 p-1 rounded-lg bg-gray-200 dark:bg-gray-700">
                <button
                  onClick={() => setViewMode('grid')}
                  className={`p-2 rounded transition-colors ${
                    viewMode === 'grid'
                      ? 'bg-white dark:bg-gray-600 text-blue-600 dark:text-blue-400'
                      : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
                  }`}
                  title="Grid View"
                >
                  <Grid3x3 className="w-5 h-5" />
                </button>
                <button
                  onClick={() => setViewMode('list')}
                  className={`p-2 rounded transition-colors ${
                    viewMode === 'list'
                      ? 'bg-white dark:bg-gray-600 text-blue-600 dark:text-blue-400'
                      : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
                  }`}
                  title="List View"
                >
                  <List className="w-5 h-5" />
                </button>
              </div>
            )}
            
            {/* Settings Button */}
            <button
              onClick={() => setShowSettings(true)}
              className="p-2 rounded-lg bg-gray-200 dark:bg-gray-700 hover:bg-gray-300 dark:hover:bg-gray-600 transition-colors"
              title="Settings"
            >
              <Settings className="w-5 h-5 text-gray-700 dark:text-gray-300" />
            </button>
            
            {/* Dark Mode Toggle */}
            <button
              onClick={() => setDarkMode(!darkMode)}
              className="p-2 rounded-lg bg-gray-200 dark:bg-gray-700 hover:bg-gray-300 dark:hover:bg-gray-600 transition-colors"
              title={darkMode ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
            >
              {darkMode ? (
                <Sun className="w-5 h-5 text-yellow-400" />
              ) : (
                <Moon className="w-5 h-5 text-gray-700 dark:text-gray-300" />
              )}
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-8">
        {activeTab === 'playlists' ? (
          <>
            {/* Add Playlist */}
            <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6 mb-8">
              <h2 className="text-xl font-semibold mb-4 text-gray-900 dark:text-white">Add Playlist</h2>
          <div className="flex gap-2">
            <input
              type="text"
              value={newPlaylistUrl}
              onChange={(e) => setNewPlaylistUrl(e.target.value)}
              placeholder="https://www.youtube.com/playlist?list=... (YouTube supported)"
              className="flex-1 px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-500 dark:placeholder-gray-400"
            />
            <button
              onClick={() => addPlaylist.mutate(newPlaylistUrl)}
              disabled={!newPlaylistUrl || addPlaylist.isPending}
              className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed flex items-center gap-2"
            >
              {addPlaylist.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
              Add
            </button>
          </div>
        </div>

        {/* Playlists View */}
        {playlistsLoading ? (
          <div className="text-center py-12">
            <Loader2 className="w-8 h-8 animate-spin mx-auto text-blue-600" />
            <p className="mt-2 text-gray-600 dark:text-gray-400">Loading playlists...</p>
          </div>
        ) : viewMode === 'grid' ? (
          /* Grid View */
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {playlists
              ?.slice()
              .sort((a, b) => {
                // Calculate pending downloads
                const aPending = Math.max(0, a.playlist_count - a.local_count)
                const bPending = Math.max(0, b.playlist_count - b.local_count)
                // Sort by pending (descending) - playlists with more pending come first
                return bPending - aPending
              })
              .map((playlist) => {
              const runningJob = getRunningJob(playlist.id)
              const isCaughtUp = playlist.local_count >= playlist.playlist_count && playlist.playlist_count > 0
              const hasPendingDownloads = playlist.local_count < playlist.playlist_count && playlist.playlist_count > 0
              
              return (
                <div key={playlist.id} className={`rounded-lg shadow hover:shadow-lg transition-shadow playlist-card-light-hover playlist-card-dark-hover ${
                  isCaughtUp 
                    ? 'bg-green-50 dark:bg-green-900/20 border-2 border-green-200 dark:border-green-800 playlist-complete-glow' 
                    : hasPendingDownloads
                    ? 'bg-white dark:bg-gray-800 playlist-pending-glow'
                    : 'bg-white dark:bg-gray-800'
                }`}>
                  <div className="p-6">
                    <div className="flex items-center justify-between mb-2">
                      <h3 
                        className="text-lg font-semibold truncate text-gray-900 dark:text-white cursor-pointer hover:text-blue-600 dark:hover:text-blue-400 transition-all flex-1 mr-2 group"
                        onClick={() => openFolder.mutate(playlist.id)}
                        title="Open in explorer"
                      >
                        <span className="playlist-title-glow">
                          {playlist.title}
                        </span>
                        {isCaughtUp && <span className="ml-2 text-xs text-green-600 dark:text-green-400">✓ Caught up</span>}
                      </h3>
                      <button
                        onClick={() => window.open(playlist.url, '_blank')}
                        className="p-1 text-gray-400 hover:text-blue-600 dark:hover:text-blue-400 transition-colors"
                        title="Open playlist in browser"
                      >
                        <ExternalLink className="w-4 h-4" />
                      </button>
                    </div>
                    
                    {/* Stats */}
                    <div className="grid grid-cols-3 gap-2 mb-4 text-sm">
                      <div className="text-center p-2 bg-green-50 dark:bg-green-900/30 rounded">
                        <div className="font-semibold text-green-700 dark:text-green-400">{playlist.local_count}</div>
                        <div className="text-gray-600 dark:text-gray-400">Local</div>
                      </div>
                      <div className="text-center p-2 bg-blue-50 dark:bg-blue-900/30 rounded">
                        <div className="font-semibold text-blue-700 dark:text-blue-400">{playlist.playlist_count}</div>
                        <div className="text-gray-600 dark:text-gray-400">Available</div>
                      </div>
                      <div className="text-center p-2 bg-red-50 dark:bg-red-900/30 rounded">
                        <div className="font-semibold text-red-700 dark:text-red-400">{playlist.unavailable_count}</div>
                        <div className="text-gray-600 dark:text-gray-400">Unavailable</div>
                      </div>
                    </div>

                    {/* Progress Bars */}
                    {runningJob && (
                      <div className="mb-4 space-y-3">
                        {/* Download Progress */}
                        {(runningJob.download_status === 'pending' || runningJob.download_status === 'running') && (
                          <div>
                            <div className="flex justify-between text-sm mb-1">
                              <span className="text-gray-600 dark:text-gray-400">
                                📥 {runningJob.download_status === 'pending' ? 'Preparing download...' : 'Downloading'}
                              </span>
                              <span className="font-semibold text-gray-900 dark:text-white">
                                {runningJob.download_completed} / {runningJob.download_total}
                              </span>
                            </div>
                            <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                              <div
                                className="bg-blue-600 dark:bg-blue-500 h-2 rounded-full transition-all"
                                style={{ 
                                  width: `${runningJob.download_total > 0 ? (runningJob.download_completed / runningJob.download_total * 100) : 0}%` 
                                }}
                              />
                            </div>
                            {runningJob.download_batch_info && (
                              <div className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                                {runningJob.download_batch_info}
                              </div>
                            )}
                          </div>
                        )}
                        
                        {/* Extraction Progress */}
                        {(runningJob.extract_status === 'pending' || runningJob.extract_status === 'running') && (
                          <div>
                            <div className="flex justify-between text-sm mb-1">
                              <span className="text-gray-600 dark:text-gray-400">
                                🎵 {runningJob.extract_status === 'pending' ? 'Preparing extraction...' : 'Extracting Audio'}
                              </span>
                              <span className="font-semibold text-gray-900 dark:text-white">
                                {runningJob.extract_completed} / {runningJob.extract_total}
                              </span>
                            </div>
                            <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                              <div
                                className="bg-purple-600 dark:bg-purple-500 h-2 rounded-full transition-all"
                                style={{ 
                                  width: `${runningJob.extract_total > 0 ? (runningJob.extract_completed / runningJob.extract_total * 100) : 0}%` 
                                }}
                              />
                            </div>
                          </div>
                        )}
                        
                        {/* Show completion message if both are done */}
                        {runningJob.download_status === 'completed' && runningJob.extract_status === 'completed' && (
                          <div className="text-sm text-green-600 dark:text-green-400">
                            ✓ Download and extraction completed
                          </div>
                        )}
                        
                        {/* View Logs Button */}
                        <div className="mt-2">
                          <button
                            onClick={() => setViewingLogs(runningJob)}
                            className="text-xs text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300 flex items-center gap-1"
                          >
                            <LogIcon className="w-3 h-3" />
                            View Logs
                          </button>
                        </div>
                      </div>
                    )}

                    {/* Actions */}
                    <div className="flex gap-2">
                      {runningJob ? (
                        // Only show cancel button when job is running
                        <button
                          onClick={() => {
                            if (confirm('Cancel this job? The current video download will complete first.')) {
                              cancelJob.mutate(runningJob.id)
                            }
                          }}
                          disabled={cancelJob.isPending}
                          className="flex-1 px-3 py-2 bg-red-600 text-white rounded hover:bg-red-700 disabled:bg-red-400 text-sm flex items-center justify-center gap-1"
                        >
                          {cancelJob.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Cancel'}
                        </button>
                      ) : (
                        // Show all buttons when no job is running
                        <>
                          {/* Check if all videos are downloaded */}
                          {(() => {
                            const allDownloaded = playlist.local_count >= playlist.playlist_count && playlist.playlist_count > 0
                            
                            return (
                              <>
                                <button
                                  onClick={() => startJob.mutate({ playlistId: playlist.id, jobType: 'both' })}
                                  disabled={allDownloaded}
                                  className={`flex-1 px-3 py-2 ${allDownloaded ? 'bg-gray-400 cursor-not-allowed' : 'bg-blue-600 hover:bg-blue-700'} text-white rounded text-sm flex items-center justify-center gap-1`}
                                  title={allDownloaded ? 'All videos downloaded' : 'Download & Extract'}
                                >
                                  <PlayCircle className="w-4 h-4" />
                                  Download & Extract
                                </button>
                                <button
                                  onClick={() => startJob.mutate({ playlistId: playlist.id, jobType: 'download' })}
                                  disabled={allDownloaded}
                                  className={`px-3 py-2 ${allDownloaded ? 'bg-gray-400 cursor-not-allowed' : 'bg-green-600 hover:bg-green-700'} text-white rounded text-sm`}
                                  title={allDownloaded ? 'All videos downloaded' : 'Download Only'}
                                >
                                  <Download className="w-4 h-4" />
                                </button>
                              </>
                            )
                          })()}
                          <button
                            onClick={() => startJob.mutate({ playlistId: playlist.id, jobType: 'extract' })}
                            className="px-3 py-2 bg-purple-600 text-white rounded hover:bg-purple-700 text-sm"
                            title="Extract Audio Only"
                          >
                            <Music className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => refreshPlaylist.mutate(playlist.id)}
                            disabled={refreshPlaylist.isPending}
                            className="px-3 py-2 bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded hover:bg-gray-300 dark:hover:bg-gray-600 text-sm"
                            title="Refresh Stats"
                          >
                            <RefreshCw className={`w-4 h-4 ${refreshPlaylist.isPending ? 'animate-spin' : ''}`} />
                          </button>
                          <button
                            onClick={() => {
                              if (confirm(
                                `Remove "${playlist.title}" from manager?\n\n` +
                                'This will only remove the playlist entry from the database.\n' +
                                'Downloaded files and folders will remain intact.\n' +
                                'You can manually delete them if needed.'
                              )) {
                                deletePlaylist.mutate(playlist.id)
                              }
                            }}
                            className="px-3 py-2 bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400 rounded hover:bg-red-200 dark:hover:bg-red-900/50 text-sm"
                            title="Remove playlist entry (files stay intact)"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </>
                      )}
                    </div>

                    {/* Last Download/Extract Times & Excluded Count */}
                    <div className="mt-3 text-xs text-gray-500 dark:text-gray-400 space-y-1">
                      {playlist.last_download && (
                        <div>Last download: {new Date(playlist.last_download).toLocaleString()}</div>
                      )}
                      {playlist.last_extract && (
                        <div>Last extract: {new Date(playlist.last_extract).toLocaleString()}</div>
                      )}
                      {playlist.excluded_ids.length > 0 && (
                        <div className="flex items-center justify-between">
                          <span>{playlist.excluded_ids.length} videos excluded</span>
                          <button
                            onClick={() => setEditingExclusions(playlist)}
                            className="text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300 flex items-center gap-1"
                            title="Edit exclusions"
                          >
                            <Edit3 className="w-3 h-3" />
                            Edit
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        ) : (
          /* List View - Tile-based Rows */
          <div className="space-y-3">
            {playlists
              ?.slice()
              .sort((a, b) => {
                const aPending = Math.max(0, a.playlist_count - a.local_count)
                const bPending = Math.max(0, b.playlist_count - b.local_count)
                return bPending - aPending
              })
              .map((playlist) => {
                const runningJob = getRunningJob(playlist.id)
                const isCaughtUp = playlist.local_count >= playlist.playlist_count && playlist.playlist_count > 0
                const hasPendingDownloads = playlist.local_count < playlist.playlist_count && playlist.playlist_count > 0
                const isExpanded = expandedRows.has(playlist.id)
                
                return (
                  <div
                    key={playlist.id}
                    className={`rounded-lg shadow-md hover:shadow-lg transition-all playlist-card-light-hover playlist-card-dark-hover ${
                      isCaughtUp 
                        ? 'bg-gradient-to-r from-green-50 to-green-100 dark:from-green-900/20 dark:to-green-800/20 border-2 border-green-200 dark:border-green-800 playlist-complete-glow' 
                        : hasPendingDownloads
                        ? 'bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 playlist-pending-glow'
                        : 'bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700'
                    }`}
                  >
                    {/* Main Row - Clickable */}
                    <div
                      onClick={() => toggleRow(playlist.id)}
                      className="px-6 py-4 cursor-pointer hover:bg-gray-50/50 dark:hover:bg-gray-700/50 transition-colors rounded-t-lg"
                    >
                      <div className="flex items-center justify-between gap-4">
                        {/* Title and Status */}
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-1">
                            <h3 
                              className="text-lg font-semibold text-gray-900 dark:text-white truncate cursor-pointer hover:text-blue-600 dark:hover:text-blue-400 transition-all group"
                              onClick={(e) => {
                                e.stopPropagation()
                                openFolder.mutate(playlist.id)
                              }}
                              title="Open in explorer"
                            >
                              <span className="playlist-title-glow">
                                {playlist.title}
                              </span>
                            </h3>
                            <button
                              onClick={(e) => {
                                e.stopPropagation()
                                window.open(playlist.url, '_blank')
                              }}
                              className="p-1 text-gray-400 hover:text-blue-600 dark:hover:text-blue-400 transition-colors"
                              title="Open playlist in browser"
                            >
                              <ExternalLink className="w-4 h-4" />
                            </button>
                            {isCaughtUp && (
                              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">
                                ✓ Complete
                              </span>
                            )}
                            {runningJob && (
                              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200 animate-pulse">
                                ● Running
                              </span>
                            )}
                          </div>
                          
                          {/* Progress Info */}
                          {runningJob && (
                            <div className="text-xs text-gray-600 dark:text-gray-400 space-x-3">
                              {runningJob.download_status === 'running' && (
                                <span>📥 Downloading {runningJob.download_completed}/{runningJob.download_total}</span>
                              )}
                              {runningJob.extract_status === 'running' && (
                                <span>🎵 Extracting {runningJob.extract_completed}/{runningJob.extract_total}</span>
                              )}
                            </div>
                          )}
                        </div>
                        
                        {/* Stats with colored backgrounds */}
                        <div className="flex items-center gap-3">
                          <div className="text-center p-3 bg-green-50 dark:bg-green-900/30 rounded-lg min-w-[80px]">
                            <div className="text-2xl font-bold text-green-700 dark:text-green-400">{playlist.local_count}</div>
                            <div className="text-xs text-gray-600 dark:text-gray-400">Local</div>
                          </div>
                          <div className="text-center p-3 bg-blue-50 dark:bg-blue-900/30 rounded-lg min-w-[80px]">
                            <div className="text-2xl font-bold text-blue-700 dark:text-blue-400">{playlist.playlist_count}</div>
                            <div className="text-xs text-gray-600 dark:text-gray-400">Available</div>
                          </div>
                          <div className="text-center p-3 bg-red-50 dark:bg-red-900/30 rounded-lg min-w-[80px]">
                            <div className="text-2xl font-bold text-red-700 dark:text-red-400">{playlist.unavailable_count}</div>
                            <div className="text-xs text-gray-600 dark:text-gray-400">Unavailable</div>
                          </div>
                          
                          {/* Last Activity - side by side */}
                          {playlist.last_download && (
                            <div className="text-center p-3 bg-gray-50 dark:bg-gray-700/30 rounded-lg min-w-[140px]">
                              <div className="text-sm font-semibold text-gray-700 dark:text-gray-300">
                                {new Date(playlist.last_download).toLocaleDateString()}
                              </div>
                              <div className="text-xs text-gray-500 dark:text-gray-400">Last Download</div>
                            </div>
                          )}
                          {playlist.last_extract && (
                            <div className="text-center p-3 bg-gray-50 dark:bg-gray-700/30 rounded-lg min-w-[140px]">
                              <div className="text-sm font-semibold text-gray-700 dark:text-gray-300">
                                {new Date(playlist.last_extract).toLocaleDateString()}
                              </div>
                              <div className="text-xs text-gray-500 dark:text-gray-400">Last Extract</div>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                    
                    {/* Expanded Section with Actions */}
                    {isExpanded && (
                      <div className="px-6 py-4 bg-gray-50 dark:bg-gray-900/50 border-t border-gray-200 dark:border-gray-700 rounded-b-lg">
                              <div className="space-y-4">
                                {/* Progress Bars */}
                                {runningJob && (
                                  <div className="space-y-3">
                                    {runningJob.download_status && runningJob.download_status !== 'completed' && (
                                      <div>
                                        <div className="flex justify-between text-sm mb-1">
                                          <span className="text-gray-600 dark:text-gray-400">📥 Downloading</span>
                                          <span className="font-semibold text-gray-900 dark:text-white">
                                            {runningJob.download_completed} / {runningJob.download_total}
                                          </span>
                                        </div>
                                        <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                                          <div
                                            className="bg-blue-600 dark:bg-blue-500 h-2 rounded-full transition-all"
                                            style={{ 
                                              width: `${runningJob.download_total > 0 ? (runningJob.download_completed / runningJob.download_total * 100) : 0}%` 
                                            }}
                                          />
                                        </div>
                                        {runningJob.download_batch_info && (
                                          <div className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                                            {runningJob.download_batch_info}
                                          </div>
                                        )}
                                      </div>
                                    )}
                                    
                                    {runningJob.extract_status && runningJob.extract_status !== 'completed' && (
                                      <div>
                                        <div className="flex justify-between text-sm mb-1">
                                          <span className="text-gray-600 dark:text-gray-400">🎵 Extracting Audio</span>
                                          <span className="font-semibold text-gray-900 dark:text-white">
                                            {runningJob.extract_completed} / {runningJob.extract_total}
                                          </span>
                                        </div>
                                        <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                                          <div
                                            className="bg-purple-600 dark:bg-purple-500 h-2 rounded-full transition-all"
                                            style={{ 
                                              width: `${runningJob.extract_total > 0 ? (runningJob.extract_completed / runningJob.extract_total * 100) : 0}%` 
                                            }}
                                          />
                                        </div>
                                      </div>
                                    )}
                                    
                                    <button
                                      onClick={() => setViewingLogs(runningJob)}
                                      className="text-xs text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300 flex items-center gap-1"
                                    >
                                      <LogIcon className="w-3 h-3" />
                                      View Logs
                                    </button>
                                  </div>
                                )}
                                
                                {/* Action Buttons */}
                                <div className="flex gap-2 flex-wrap">
                                  {runningJob ? (
                                    <button
                                      onClick={() => {
                                        if (confirm('Cancel this job? The current video download will complete first.')) {
                                          cancelJob.mutate(runningJob.id)
                                        }
                                      }}
                                      disabled={cancelJob.isPending}
                                      className="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700 disabled:bg-red-400 text-sm flex items-center gap-1"
                                    >
                                      {cancelJob.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Cancel Job'}
                                    </button>
                                  ) : (
                                    <>
                                      {(() => {
                                        const allDownloaded = playlist.local_count >= playlist.playlist_count && playlist.playlist_count > 0
                                        return (
                                          <>
                                            <button
                                              onClick={() => startJob.mutate({ playlistId: playlist.id, jobType: 'both' })}
                                              disabled={allDownloaded}
                                              className={`px-4 py-2 ${allDownloaded ? 'bg-gray-400 cursor-not-allowed' : 'bg-blue-600 hover:bg-blue-700'} text-white rounded text-sm flex items-center gap-1`}
                                            >
                                              <PlayCircle className="w-4 h-4" />
                                              Download & Extract
                                            </button>
                                            <button
                                              onClick={() => startJob.mutate({ playlistId: playlist.id, jobType: 'download' })}
                                              disabled={allDownloaded}
                                              className={`px-4 py-2 ${allDownloaded ? 'bg-gray-400 cursor-not-allowed' : 'bg-green-600 hover:bg-green-700'} text-white rounded text-sm flex items-center gap-1`}
                                            >
                                              <Download className="w-4 h-4" />
                                              Download
                                            </button>
                                          </>
                                        )
                                      })()}
                                      <button
                                        onClick={() => startJob.mutate({ playlistId: playlist.id, jobType: 'extract' })}
                                        className="px-4 py-2 bg-purple-600 text-white rounded hover:bg-purple-700 text-sm flex items-center gap-1"
                                      >
                                        <Music className="w-4 h-4" />
                                        Extract
                                      </button>
                                      <button
                                        onClick={() => refreshPlaylist.mutate(playlist.id)}
                                        disabled={refreshPlaylist.isPending}
                                        className="px-4 py-2 bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded hover:bg-gray-300 dark:hover:bg-gray-600 text-sm flex items-center gap-1"
                                      >
                                        <RefreshCw className={`w-4 h-4 ${refreshPlaylist.isPending ? 'animate-spin' : ''}`} />
                                        Refresh
                                      </button>
                                      {playlist.excluded_ids.length > 0 && (
                                        <button
                                          onClick={() => setEditingExclusions(playlist)}
                                          className="px-4 py-2 bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded hover:bg-gray-300 dark:hover:bg-gray-600 text-sm flex items-center gap-1"
                                        >
                                          <Edit3 className="w-4 h-4" />
                                          Edit Exclusions ({playlist.excluded_ids.length})
                                        </button>
                                      )}
                                      <button
                                        onClick={() => {
                                          if (confirm(`Remove "${playlist.title}" from manager?\n\nDownloaded files will remain intact.`)) {
                                            deletePlaylist.mutate(playlist.id)
                                          }
                                        }}
                                        className="px-4 py-2 bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400 rounded hover:bg-red-200 dark:hover:bg-red-900/50 text-sm flex items-center gap-1"
                                      >
                                        <Trash2 className="w-4 h-4" />
                                        Remove
                                      </button>
                                    </>
                                  )}
                                </div>
                              </div>
                            </div>
                          )}
                        </div>
                      )
              })}
          </div>
        )}

        {playlists?.length === 0 && !playlistsLoading && (
          <div className="text-center py-12 text-gray-500 dark:text-gray-400">
            <p>No playlists yet. Add one above to get started!</p>
          </div>
        )}
          </>
        ) : (
          <JobLogsView
            jobs={jobs || []}
            playlists={playlists || []}
            activityLogs={activityLogs}
            onClearActivity={() => setActivityLogs([])}
          />
        )}
      </main>

      {/* Initial Setup Modal */}
      {showInitialSetup && (
        <InitialSetupModal 
          onComplete={() => {
            setShowInitialSetup(false)
            queryClient.invalidateQueries({ queryKey: ['config'] })
          }}
        />
      )}

      {/* Interrupted Jobs Dialog */}
      {showInterruptedDialog && interruptedJobs.length > 0 && (
        <InterruptedJobsDialog
          jobs={interruptedJobs}
          onResumeAll={async () => {
            await handleInterruptedJobs.mutateAsync({
              action: 'resume_all',
            })
          }}
          onCancelAll={async () => {
            await handleInterruptedJobs.mutateAsync({
              action: 'cancel_all',
            })
          }}
          onIndividual={async (decisions) => {
            await handleInterruptedJobs.mutateAsync({
              action: 'individual',
              jobDecisions: decisions,
            })
          }}
          isLoading={handleInterruptedJobs.isPending}
        />
      )}

      {/* Settings Modal */}
      {showSettings && <SettingsModal onClose={() => setShowSettings(false)} />}
      
      {/* Exclusions Modal */}
      {editingExclusions && (
        <ExclusionsModal 
          playlist={editingExclusions} 
          onClose={() => setEditingExclusions(null)} 
        />
      )}
      
      {/* Logs Modal */}
      {viewingLogs && (
        <LogsModal 
          job={viewingLogs} 
          onClose={() => setViewingLogs(null)} 
        />
      )}
    </div>
  )
}

// Helper Component for interactive field headers with recommendations and toggleable info
function FieldHeader({
  label,
  required = false,
  recommended,
  infoText,
  id
}: {
  label: string
  required?: boolean
  recommended?: string
  infoText?: string
  id?: string
}) {
  const [open, setOpen] = useState(false)
  return (
    <div className="mb-1.5">
      <div className="flex items-center justify-between gap-2">
        <label htmlFor={id} className="text-sm font-semibold text-gray-900 dark:text-white flex items-center gap-1.5 flex-wrap">
          <span>{label}</span>
          {required && <span className="text-rose-500 font-bold">*</span>}
          {recommended && (
            <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300">
              {recommended}
            </span>
          )}
        </label>
        {infoText && (
          <button
            type="button"
            onClick={() => setOpen(!open)}
            className={`px-2 py-0.5 rounded text-xs transition-colors flex items-center gap-1 shrink-0 ${
              open 
                ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/60 dark:text-blue-200' 
                : 'text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700'
            }`}
            title="Click to toggle explanation"
          >
            <Info className="w-3.5 h-3.5" />
            <span className="text-[11px] font-medium">{open ? 'Hide info' : 'Info'}</span>
          </button>
        )}
      </div>
      {open && infoText && (
        <div className="mt-1.5 p-2.5 bg-blue-50 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-800/80 rounded-lg text-xs text-blue-950 dark:text-blue-200 leading-relaxed shadow-sm">
          {infoText}
        </div>
      )}
    </div>
  )
}

// Helper Component for dynamic Audio Extraction Mode preview card
function AudioModeCard({ mode }: { mode: string }) {
  if (mode === 'copy') {
    return (
      <div className="mt-2 p-3 bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-800/60 rounded-lg text-xs space-y-1">
        <div className="font-semibold text-emerald-800 dark:text-emerald-300 flex items-center gap-1.5">
          <Zap className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
          Direct Stream Copy (Lossless & Instantaneous)
        </div>
        <p className="text-emerald-700 dark:text-emerald-300/90 leading-relaxed">
          Extracts YouTube's original native audio track (<code className="font-mono bg-emerald-100 dark:bg-emerald-900/60 px-1 py-0.5 rounded">.m4a</code> for AAC, <code className="font-mono bg-emerald-100 dark:bg-emerald-900/60 px-1 py-0.5 rounded">.opus</code> for Opus) without transcoding. Takes ~0.2s per song with zero CPU load and zero acoustic compression loss.
        </p>
      </div>
    )
  }
  if (mode === 'mp3_best') {
    return (
      <div className="mt-2 p-3 bg-indigo-50 dark:bg-indigo-950/30 border border-indigo-200 dark:border-indigo-800/60 rounded-lg text-xs space-y-1">
        <div className="font-semibold text-indigo-800 dark:text-indigo-300 flex items-center gap-1.5">
          <Music className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
          MP3 Best Quality (VBR ~250–320 kbps)
        </div>
        <p className="text-indigo-700 dark:text-indigo-300/90 leading-relaxed">
          Re-encodes audio to universal MP3 at maximum variable bitrate (<code className="font-mono bg-indigo-100 dark:bg-indigo-900/60 px-1 py-0.5 rounded">libmp3lame -q:a 0</code>). 100% compatible with older car stereos and legacy MP3 players.
        </p>
      </div>
    )
  }
  if (mode === 'mp3_high') {
    return (
      <div className="mt-2 p-3 bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800/60 rounded-lg text-xs space-y-1">
        <div className="font-semibold text-blue-800 dark:text-blue-300 flex items-center gap-1.5">
          <Music className="w-4 h-4 text-blue-600 dark:text-blue-400" />
          MP3 High Quality (VBR ~190–250 kbps)
        </div>
        <p className="text-blue-700 dark:text-blue-300/90 leading-relaxed">
          Standard high-quality MP3 encoding (<code className="font-mono bg-blue-100 dark:bg-blue-900/60 px-1 py-0.5 rounded">libmp3lame -q:a 2</code>). Great balance of smaller file sizes and high audio fidelity.
        </p>
      </div>
    )
  }
  if (mode === 'opus') {
    return (
      <div className="mt-2 p-3 bg-purple-50 dark:bg-purple-950/30 border border-purple-200 dark:border-purple-800/60 rounded-lg text-xs space-y-1">
        <div className="font-semibold text-purple-800 dark:text-purple-300 flex items-center gap-1.5">
          <Sparkles className="w-4 h-4 text-purple-600 dark:text-purple-400" />
          Opus Codec (128 kbps)
        </div>
        <p className="text-purple-700 dark:text-purple-300/90 leading-relaxed">
          Uses the next-generation open Opus audio codec. Delivers crystal-clear acoustic transparency at half the file size of traditional MP3s.
        </p>
      </div>
    )
  }
  return null
}

// Initial Setup Modal Component
function InitialSetupModal({ onComplete }: { onComplete: () => void }) {
  const [formData, setFormData] = useState<Partial<Config>>({
    base_download_path: '',
    temp_download_path: '',
    audio_extract_mode: 'copy',
    max_extraction_workers: 4,
    batch_size: 200,
    use_browser_cookies: false,
    browser_name: 'chrome',
    cookies_file: null,
  })

  const updateConfig = useMutation({
    mutationFn: (data: Partial<Config>) => configApi.update(data),
    onSuccess: () => {
      alert('Setup complete! You can now start using the app.')
      onComplete()
    },
    onError: (error) => {
      alert(`Setup failed: ${error}`)
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    
    // Validate required fields
    if (!formData.base_download_path?.trim()) {
      alert('Please enter a download directory path')
      return
    }
    
    updateConfig.mutate(formData)
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center z-50 p-4">
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto border border-gray-200 dark:border-gray-700">
        <div className="p-6">
          <div className="mb-6 pb-4 border-b border-gray-200 dark:border-gray-700">
            <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-1 flex items-center gap-2">
              <Sparkles className="w-6 h-6 text-blue-600 dark:text-blue-400" />
              Initial Setup
            </h2>
            <p className="text-sm text-gray-600 dark:text-gray-400">
              Configure your storage and download preferences to get started. You can change these anytime in Settings.
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5">
            {/* Required: Download Path */}
            <div className="border-2 border-blue-500/80 dark:border-blue-400/80 rounded-xl p-4 bg-blue-50/50 dark:bg-blue-900/10">
              <FieldHeader
                label="Main Download Directory"
                required={true}
                infoText="The permanent storage destination for your music and playlists (e.g. your 2TB external HDD mounted at /downloads or E:\Music\Playlists)."
              />
              <input
                type="text"
                value={formData.base_download_path || ''}
                onChange={(e) => setFormData({ ...formData, base_download_path: e.target.value })}
                className="w-full px-3.5 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500"
                placeholder="/downloads or E:\Music\Playlists"
                required
              />
              <p className="text-xs text-gray-600 dark:text-gray-400 mt-1.5">
                Target location where completed playlists and audio albums are saved.
              </p>
            </div>

            {/* Optional: Temp Download Buffer */}
            <div className="border border-gray-300 dark:border-gray-600 rounded-xl p-4 bg-gray-50/40 dark:bg-gray-800/40">
              <FieldHeader
                label="Temporary Processing Directory"
                recommended="Optional: Fast SSD Buffer"
                infoText="Uses a fast internal SSD directory (e.g. /downloads-temp) to buffer active multi-fragment chunk downloads and FFmpeg audio extractions. Once verified non-empty, files are moved atomically in a single fast sequential write to your main HDD."
              />
              <input
                type="text"
                value={formData.temp_download_path || ''}
                onChange={(e) => setFormData({ ...formData, temp_download_path: e.target.value })}
                className="w-full px-3.5 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                placeholder="/downloads-temp (leave empty to download directly to main storage)"
              />
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1.5">
                Leave blank if you prefer downloading directly to your main storage drive.
              </p>
            </div>

            {/* Audio Extract Mode */}
            <div className="border border-gray-300 dark:border-gray-600 rounded-xl p-4 bg-gray-50/40 dark:bg-gray-800/40">
              <FieldHeader
                label="Audio Extraction Mode"
                recommended="Recommended: copy"
                infoText="Specifies whether to stream copy native YouTube audio (lossless, instant) or transcode to MP3/Opus."
              />
              <select
                value={formData.audio_extract_mode || 'copy'}
                onChange={(e) => setFormData({ ...formData, audio_extract_mode: e.target.value })}
                className="w-full px-3.5 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
              >
                <option value="copy">Copy (Direct Stream Copy - Fastest & Lossless)</option>
                <option value="mp3_best">MP3 Best Quality (VBR ~250–320 kbps)</option>
                <option value="mp3_high">MP3 High Quality (VBR ~190–250 kbps)</option>
                <option value="opus">Opus (128 kbps)</option>
              </select>
              <AudioModeCard mode={formData.audio_extract_mode || 'copy'} />
            </div>

            {/* Advanced Settings (Collapsed) */}
            <details className="border border-gray-300 dark:border-gray-600 rounded-xl p-4 bg-gray-50/20 dark:bg-gray-800/20">
              <summary className="cursor-pointer text-sm font-semibold text-gray-800 dark:text-gray-200">
                Advanced Performance & Authentication Settings
              </summary>
              
              <div className="space-y-4 mt-4 pt-3 border-t border-gray-200 dark:border-gray-700">
                <div>
                  <FieldHeader
                    label="Max Concurrent Extractions"
                    recommended="Recommended: 4"
                    infoText="Number of parallel CPU worker threads used to extract and verify audio tracks simultaneously (1–16 workers)."
                  />
                  <input
                    type="number"
                    min="1"
                    max="16"
                    value={formData.max_extraction_workers || 4}
                    onChange={(e) => setFormData({ ...formData, max_extraction_workers: parseInt(e.target.value) })}
                    className="w-full px-3.5 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                  />
                </div>

                <div>
                  <FieldHeader
                    label="Batch Size (Videos per run)"
                    recommended="Recommended: 200"
                    infoText="Maximum number of videos to download in a single batch. Prevents YouTube anti-bot rate-limiting on large playlists."
                  />
                  <input
                    type="number"
                    min="1"
                    max="1000"
                    value={formData.batch_size || 200}
                    onChange={(e) => setFormData({ ...formData, batch_size: parseInt(e.target.value) })}
                    className="w-full px-3.5 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                  />
                </div>

                <div>
                  <FieldHeader
                    label="Browser Profile Extraction (Advanced / Headless)"
                    infoText="Reads login cookies directly from a mounted browser profile directory (Chrome, Firefox, Edge, Safari). Useful for headless browser setups. You can also upload a cookies.txt file at any time from Settings."
                  />
                  <label className="flex items-center space-x-2 mt-1">
                    <input
                      type="checkbox"
                      checked={formData.use_browser_cookies || false}
                      onChange={(e) => setFormData({ ...formData, use_browser_cookies: e.target.checked })}
                      className="rounded text-blue-600 focus:ring-blue-500"
                    />
                    <span className="text-sm text-gray-700 dark:text-gray-300">Enable Browser Profile Extraction</span>
                  </label>

                  {formData.use_browser_cookies && (
                    <div className="mt-2">
                      <select
                        value={formData.browser_name || 'chrome'}
                        onChange={(e) => setFormData({ ...formData, browser_name: e.target.value })}
                        className="w-full px-3.5 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                      >
                        <option value="chrome">Chrome</option>
                        <option value="firefox">Firefox</option>
                        <option value="edge">Edge</option>
                        <option value="safari">Safari</option>
                      </select>
                    </div>
                  )}
                </div>
              </div>
            </details>

            <div className="flex gap-2 pt-2">
              <button
                type="submit"
                disabled={updateConfig.isPending || !formData.base_download_path?.trim()}
                className="flex-1 px-5 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-400 flex items-center justify-center gap-2 font-semibold shadow-sm transition-colors"
              >
                {updateConfig.isPending && <Loader2 className="w-4 h-4 animate-spin" />}
                Complete Setup & Start
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  )
}

// Settings Modal Component
function SettingsModal({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient()
  
  const { data: config, isLoading } = useQuery({
    queryKey: ['config'],
    queryFn: async () => {
      const res = await configApi.get()
      return res.data
    },
  })

  const { data: ytdlpVersionData, refetch: refetchYtdlp } = useQuery({
    queryKey: ['ytdlpVersion'],
    queryFn: async () => {
      const res = await configApi.getYtdlpVersion()
      return res.data
    },
  })

  const updateYtdlpMutation = useMutation({
    mutationFn: () => configApi.updateYtdlp(),
    onSuccess: (res) => {
      if (res.data.success) {
        alert(`yt-dlp updated successfully to version ${res.data.new_version}`)
        refetchYtdlp()
      } else {
        alert(`Failed to update yt-dlp: ${res.data.message}`)
      }
    },
    onError: (err: any) => {
      alert(`Error updating yt-dlp: ${err.message}`)
    },
  })

  const testFlareSolverrMutation = useMutation({
    mutationFn: (url?: string) => configApi.testFlareSolverr(url),
    onSuccess: (res) => {
      if (res.data.success) {
        alert(`✓ ${res.data.message} (${res.data.response_time_ms}ms)`)
      } else {
        alert(`✗ ${res.data.message}`)
      }
    },
    onError: (err: any) => {
      alert(`Error testing FlareSolverr: ${err.message}`)
    },
  })

  const { data: cookieStatus, refetch: refetchCookieStatus } = useQuery({
    queryKey: ['cookies-status'],
    queryFn: async () => {
      const res = await configApi.getCookiesStatus()
      return res.data
    },
  })

  const uploadCookiesMutation = useMutation({
    mutationFn: (file: File) => configApi.uploadCookies(file),
    onSuccess: (res) => {
      refetchCookieStatus()
      queryClient.invalidateQueries({ queryKey: ['config'] })
      alert(`✓ ${res.data.status_message}`)
    },
    onError: (err: any) => {
      alert(`Failed to upload cookies: ${err.message}`)
    },
  })

  const deleteCookiesMutation = useMutation({
    mutationFn: () => configApi.deleteCookies(),
    onSuccess: () => {
      refetchCookieStatus()
      queryClient.invalidateQueries({ queryKey: ['config'] })
      alert('✓ Cookies removed. Downloads will use mobile client emulation.')
    },
    onError: (err: any) => {
      alert(`Failed to remove cookies: ${err.message}`)
    },
  })

  const [formData, setFormData] = useState<Partial<Config>>({})

  useEffect(() => {
    if (config) {
      setFormData(config)
    }
  }, [config])

  const updateConfig = useMutation({
    mutationFn: (data: Partial<Config>) => configApi.update(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['config'] })
      alert('Settings saved! Restart the backend for changes to take effect.')
      onClose()
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    
    // Validate inputs
    const validated: Partial<Config> = {}
    
    if (formData.base_download_path) {
      validated.base_download_path = formData.base_download_path.trim()
    }

    if (formData.temp_download_path !== undefined) {
      validated.temp_download_path = formData.temp_download_path?.trim() || null
    }
    
    if (formData.audio_extract_mode) {
      const validModes = ['copy', 'mp3_best', 'mp3_high', 'opus']
      if (validModes.includes(formData.audio_extract_mode)) {
        validated.audio_extract_mode = formData.audio_extract_mode
      }
    }
    
    if (formData.max_extraction_workers !== undefined) {
      const workers = Number(formData.max_extraction_workers)
      if (workers >= 1 && workers <= 16) {
        validated.max_extraction_workers = workers
      }
    }
    
    if (formData.batch_size !== undefined) {
      const size = Number(formData.batch_size)
      if (size >= 1 && size <= 1000) {
        validated.batch_size = size
      }
    }
    
    if (formData.cookies_file !== undefined) {
      validated.cookies_file = formData.cookies_file?.trim() || null
    }
    
    if (formData.use_browser_cookies !== undefined) {
      validated.use_browser_cookies = formData.use_browser_cookies
    }
    
    if (formData.browser_name) {
      const validBrowsers = ['chrome', 'firefox', 'edge', 'safari']
      if (validBrowsers.includes(formData.browser_name.toLowerCase())) {
        validated.browser_name = formData.browser_name.toLowerCase()
      }
    }

    if (formData.enable_stream_integrity_check !== undefined) {
      validated.enable_stream_integrity_check = formData.enable_stream_integrity_check
    }

    if (formData.flaresolverr_url !== undefined) {
      validated.flaresolverr_url = formData.flaresolverr_url?.trim() || null
    }

    
    updateConfig.mutate(validated)
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        <div className="p-6">
          <div className="flex justify-between items-center mb-6">
            <h2 className="text-2xl font-bold text-gray-900 dark:text-white">Settings</h2>
            <button
              onClick={onClose}
              className="text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
            >
              ✕
            </button>
          </div>

          {isLoading ? (
            <div className="text-center py-8">
              <Loader2 className="w-8 h-8 animate-spin mx-auto text-blue-600" />
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <FieldHeader
                  label="Base Download Path"
                  required={true}
                  infoText="Root destination directory on your main storage drive (e.g. 2TB external HDD or /downloads) where all completed playlists and audio albums are stored."
                />
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={formData.base_download_path || ''}
                    onChange={(e) => setFormData({ ...formData, base_download_path: e.target.value })}
                    className="flex-1 px-3.5 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                    placeholder="E:\\Music\\Playlists or /downloads"
                  />
                  <button
                    type="button"
                    onClick={() => {
                      const input = document.createElement('input')
                      input.type = 'file'
                      input.webkitdirectory = true
                      input.onchange = (e: any) => {
                        const files = e.target.files
                        if (files && files.length > 0) {
                          const path = files[0].webkitRelativePath.split('/')[0]
                          setFormData({ ...formData, base_download_path: path })
                        }
                      }
                      input.click()
                    }}
                    className="px-4 py-2 bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-300 dark:hover:bg-gray-600 whitespace-nowrap flex items-center gap-2"
                  >
                    <FolderOpen className="w-4 h-4" />
                    Browse
                  </button>
                </div>
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                  Note: Browser security limits full path picking. You may type or paste the exact absolute path manually.
                </p>
              </div>

              <div>
                <FieldHeader
                  label="Temp Processing Directory"
                  recommended="Optional: Fast SSD Buffer"
                  infoText="Active multi-fragment chunk downloads and FFmpeg audio extraction occur on this fast SSD directory before being moved in a single sequential write to your main storage."
                />
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={formData.temp_download_path || ''}
                    onChange={(e) => setFormData({ ...formData, temp_download_path: e.target.value })}
                    className="flex-1 px-3.5 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                    placeholder="/downloads-temp (leave empty to download directly to main storage)"
                  />
                  <button
                    type="button"
                    onClick={() => {
                      const input = document.createElement('input')
                      input.type = 'file'
                      input.webkitdirectory = true
                      input.onchange = (e: any) => {
                        const files = e.target.files
                        if (files && files.length > 0) {
                          const path = files[0].webkitRelativePath.split('/')[0]
                          setFormData({ ...formData, temp_download_path: path })
                        }
                      }
                      input.click()
                    }}
                    className="px-4 py-2 bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-300 dark:hover:bg-gray-600 whitespace-nowrap flex items-center gap-2"
                  >
                    <FolderOpen className="w-4 h-4" />
                    Browse
                  </button>
                </div>
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                  Leave empty if you do not have a separate SSD temp drive.
                </p>
              </div>

              <div>
                <FieldHeader
                  label="Audio Extract Mode"
                  recommended="Recommended: copy"
                  infoText="Selects whether to directly extract native streams without re-encoding (instant, lossless) or transcode to MP3/Opus."
                />
                <select
                  value={formData.audio_extract_mode || 'copy'}
                  onChange={(e) => setFormData({ ...formData, audio_extract_mode: e.target.value })}
                  className="w-full px-3.5 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                >
                  <option value="copy">Copy (Direct Stream Copy - Fastest & Lossless)</option>
                  <option value="mp3_best">MP3 Best Quality (VBR ~250–320 kbps)</option>
                  <option value="mp3_high">MP3 High Quality (VBR ~190–250 kbps)</option>
                  <option value="opus">Opus (128 kbps)</option>
                </select>
                <AudioModeCard mode={formData.audio_extract_mode || 'copy'} />
              </div>

              {/* Primary Authentication: Upload cookies.txt & live status */}
              <div className="bg-gray-50 dark:bg-gray-700/50 rounded-xl p-4 border border-gray-200 dark:border-gray-600 space-y-3">
                <div className="flex justify-between items-start">
                  <div>
                    <h4 className="text-sm font-semibold text-gray-900 dark:text-white flex items-center gap-1.5">
                      <span>YouTube Authentication & Session Cookies</span>
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300">
                        Recommended
                      </span>
                    </h4>
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                      Required for age-restricted or private playlists. Public tracks use mobile client emulation.
                    </p>
                  </div>
                  {/* Status Badge */}
                  <div>
                    {cookieStatus?.status === 'valid' && (
                      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                        Active (Expires in {cookieStatus.days_remaining}d)
                      </span>
                    )}
                    {cookieStatus?.status === 'expiring_soon' && (
                      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300">
                        <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse"></span>
                        Expiring Soon ({cookieStatus.days_remaining}d left)
                      </span>
                    )}
                    {cookieStatus?.status === 'expired' && (
                      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-rose-100 text-rose-800 dark:bg-rose-900/40 dark:text-rose-300">
                        <span className="w-1.5 h-1.5 rounded-full bg-rose-500"></span>
                        Expired ({cookieStatus.earliest_expiration})
                      </span>
                    )}
                    {cookieStatus?.status === 'not_installed' && (
                      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-gray-200 text-gray-700 dark:bg-gray-600 dark:text-gray-300">
                        Mobile Emulation Active
                      </span>
                    )}
                    {cookieStatus?.status === 'invalid' && (
                      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-orange-100 text-orange-800 dark:bg-orange-900/40 dark:text-orange-300">
                        Invalid / Anonymous
                      </span>
                    )}
                  </div>
                </div>

                {/* Status Message / Expiry info */}
                {cookieStatus?.status_message && (
                  <p className="text-xs font-mono text-gray-600 dark:text-gray-300 bg-white dark:bg-gray-800 p-2 rounded border border-gray-200 dark:border-gray-700">
                    {cookieStatus.status_message}
                  </p>
                )}

                {formData.use_browser_cookies && (
                  <div className="p-2.5 bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 rounded-lg text-xs text-amber-800 dark:text-amber-200">
                    ⚠️ <strong>Notice:</strong> Browser Profile Extraction is currently enabled in Advanced Settings and will override this uploaded cookies file.
                  </div>
                )}

                {/* Upload and Delete Action Buttons */}
                <div className="flex gap-2 items-center pt-1">
                  <button
                    type="button"
                    onClick={() => {
                      const input = document.createElement('input')
                      input.type = 'file'
                      input.accept = '.txt'
                      input.onchange = (e: any) => {
                        const file = e.target.files?.[0]
                        if (file) {
                          uploadCookiesMutation.mutate(file)
                        }
                      }
                      input.click()
                    }}
                    disabled={uploadCookiesMutation.isPending}
                    className="px-3.5 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-xs font-medium rounded-lg flex items-center gap-1.5 disabled:bg-gray-400"
                  >
                    {uploadCookiesMutation.isPending ? (
                      <>
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        Uploading...
                      </>
                    ) : (
                      <>
                        <FileText className="w-3.5 h-3.5" />
                        Upload cookies.txt
                      </>
                    )}
                  </button>

                  {cookieStatus?.is_installed && (
                    <button
                      type="button"
                      onClick={() => {
                        if (confirm('Are you sure you want to remove the installed cookies?')) {
                          deleteCookiesMutation.mutate()
                        }
                      }}
                      disabled={deleteCookiesMutation.isPending}
                      className="px-3 py-1.5 bg-rose-100 hover:bg-rose-200 text-rose-700 dark:bg-rose-900/30 dark:hover:bg-rose-900/50 dark:text-rose-300 text-xs font-medium rounded-lg flex items-center gap-1.5"
                    >
                      {deleteCookiesMutation.isPending ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      ) : (
                        'Remove Cookies'
                      )}
                    </button>
                  )}
                </div>

                <p className="text-[11px] text-gray-500 dark:text-gray-400">
                  💡 <strong>Tip:</strong> Export cookies with a 1-click browser extension (e.g. <em>Get cookies.txt LOCALLY</em>) using a secondary account.
                </p>
              </div>

              {/* Collapsed Advanced & Experimental Settings */}
              <details className="border border-gray-300 dark:border-gray-600 rounded-xl p-4 bg-gray-50/20 dark:bg-gray-800/20">
                <summary className="cursor-pointer text-sm font-semibold text-gray-800 dark:text-gray-200">
                  Advanced & Experimental Settings (Workers, Batching, Headless Browser, Proxy)
                </summary>
                
                <div className="space-y-4 mt-4 pt-3 border-t border-gray-200 dark:border-gray-700">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                      <FieldHeader
                        label="Max Concurrent Extractions"
                        recommended="Recommended: 4"
                        infoText="Number of parallel CPU worker threads used to extract and encode audio tracks simultaneously (1–16 workers)."
                      />
                      <input
                        type="number"
                        min="1"
                        max="16"
                        value={formData.max_extraction_workers || 4}
                        onChange={(e) => setFormData({ ...formData, max_extraction_workers: parseInt(e.target.value) })}
                        className="w-full px-3.5 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                      />
                    </div>

                    <div>
                      <FieldHeader
                        label="Batch Size (Videos / run)"
                        recommended="Recommended: 200"
                        infoText="Maximum number of videos to download in a single batch to avoid platform rate-limiting and temporary IP blocks."
                      />
                      <input
                        type="number"
                        min="1"
                        max="1000"
                        value={formData.batch_size || 200}
                        onChange={(e) => setFormData({ ...formData, batch_size: parseInt(e.target.value) })}
                        className="w-full px-3.5 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                      <FieldHeader
                        label="Anti-Rate-Limit Delay (Min/Max s)"
                        recommended="Recommended: 1s – 5s"
                        infoText="Random delay pause (jitter) introduced between consecutive video downloads. Mimics human behavior to avoid temporary HTTP 429 bans on large playlists."
                      />
                      <div className="flex items-center gap-2">
                        <input
                          type="number"
                          min="0"
                          max="30"
                          value={formData.sleep_interval_min ?? 1}
                          onChange={(e) => setFormData({ ...formData, sleep_interval_min: parseInt(e.target.value) || 0 })}
                          className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm"
                          placeholder="Min (1s)"
                        />
                        <span className="text-gray-400 dark:text-gray-500 font-medium">–</span>
                        <input
                          type="number"
                          min="0"
                          max="60"
                          value={formData.sleep_interval_max ?? 5}
                          onChange={(e) => setFormData({ ...formData, sleep_interval_max: parseInt(e.target.value) || 0 })}
                          className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm"
                          placeholder="Max (5s)"
                        />
                      </div>
                    </div>

                    <div>
                      <FieldHeader
                        label="Concurrent DASH Fragments"
                        recommended="Recommended: 2"
                        infoText="Number of multi-threaded DASH video stream chunks downloaded concurrently per video. Higher values increase speed but can trigger IP blocks if set above 4."
                      />
                      <input
                        type="number"
                        min="1"
                        max="16"
                        value={formData.concurrent_fragments ?? 2}
                        onChange={(e) => setFormData({ ...formData, concurrent_fragments: parseInt(e.target.value) || 1 })}
                        className="w-full px-3.5 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                      />
                    </div>
                  </div>

                  {/* Browser Profile Extraction */}
                  <div className="p-3 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 space-y-2">
                    <FieldHeader
                      label="Browser Profile Extraction (Headless / Mounted Directory)"
                      infoText="Extracts cookies directly from a browser database directory (Chrome, Firefox, Edge, Safari). Useful for headless browser setups with mounted profile folders. If active, this is prioritized over cookies.txt."
                    />
                    <label className="flex items-center space-x-2 mt-1">
                      <input
                        type="checkbox"
                        checked={formData.use_browser_cookies || false}
                        onChange={(e) => setFormData({ ...formData, use_browser_cookies: e.target.checked })}
                        className="rounded text-blue-600 focus:ring-blue-500"
                      />
                      <span className="text-sm text-gray-700 dark:text-gray-300">Enable Browser Profile Extraction</span>
                    </label>

                    {formData.use_browser_cookies && (
                      <div className="mt-2 space-y-2">
                        <label className="block text-xs font-medium text-gray-700 dark:text-gray-300">
                          Browser Engine Profile
                        </label>
                        <select
                          value={formData.browser_name || 'chrome'}
                          onChange={(e) => setFormData({ ...formData, browser_name: e.target.value })}
                          className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm"
                        >
                          <option value="chrome">Chrome</option>
                          <option value="firefox">Firefox</option>
                          <option value="edge">Edge</option>
                          <option value="safari">Safari</option>
                        </select>
                        <p className="text-[11px] text-amber-600 dark:text-amber-400">
                          ⚠️ Note: In Docker, ensure your browser profile volume is mounted into the container.
                        </p>
                      </div>
                    )}
                  </div>

                  {/* Experimental Stream Integrity Safeguard */}
                  <div className="p-3 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 space-y-1">
                    <div className="flex items-start gap-3">
                      <input
                        type="checkbox"
                        id="enable_stream_integrity_check"
                        checked={formData.enable_stream_integrity_check || false}
                        onChange={(e) => setFormData({ ...formData, enable_stream_integrity_check: e.target.checked })}
                        className="mt-1 w-4 h-4 text-blue-600 rounded border-gray-300 dark:border-gray-600"
                      />
                      <div>
                        <label htmlFor="enable_stream_integrity_check" className="text-sm font-semibold text-gray-900 dark:text-white cursor-pointer">
                          Experimental Stream Integrity Verification (ffprobe)
                        </label>
                        <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                          Inspects downloaded video containers for valid audio & video streams. Falls back gracefully if inspection fails.
                        </p>
                      </div>
                    </div>
                  </div>

                  {/* FlareSolverr Homelab Proxy */}
                  <div className="p-3 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 space-y-2">
                    <FieldHeader
                      label="FlareSolverr Proxy URL"
                      recommended="Optional Homelab Proxy"
                      infoText="Connects to a local FlareSolverr Docker container (e.g. http://localhost:8191/v1) to bypass Cloudflare protection if downloading from external websites."
                    />
                    <div className="flex gap-2">
                      <input
                        type="text"
                        value={formData.flaresolverr_url || ''}
                        onChange={(e) => setFormData({ ...formData, flaresolverr_url: e.target.value })}
                        className="flex-1 px-3.5 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm"
                        placeholder="http://localhost:8191/v1"
                      />
                      <button
                        type="button"
                        onClick={() => testFlareSolverrMutation.mutate(formData.flaresolverr_url || undefined)}
                        disabled={testFlareSolverrMutation.isPending}
                        className="px-3 py-2 bg-purple-600 text-white text-xs font-medium rounded-lg hover:bg-purple-700 disabled:bg-gray-400 flex items-center gap-1.5 whitespace-nowrap"
                      >
                        {testFlareSolverrMutation.isPending ? (
                          <>
                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                            Testing...
                          </>
                        ) : (
                          'Test Connection'
                        )}
                      </button>
                    </div>
                    <p className="text-xs text-gray-500 dark:text-gray-400">
                      Connect your homelab FlareSolverr container to bypass anti-bot challenges and solve session cookies.
                    </p>
                  </div>
                </div>
              </details>

              {/* yt-dlp updater box */}
              <div className="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-4 border border-gray-200 dark:border-gray-600 space-y-2">
                <div className="flex justify-between items-center">
                  <div>
                    <h4 className="text-sm font-semibold text-gray-900 dark:text-white">yt-dlp Engine</h4>
                    <p className="text-xs text-gray-500 dark:text-gray-400">
                      Installed Version: <span className="font-mono font-medium text-blue-600 dark:text-blue-400">{ytdlpVersionData?.version || 'Loading...'}</span>
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => updateYtdlpMutation.mutate()}
                    disabled={updateYtdlpMutation.isPending}
                    className="px-3 py-1.5 bg-emerald-600 text-white text-xs font-medium rounded-md hover:bg-emerald-700 disabled:bg-gray-400 flex items-center gap-1.5"
                  >
                    {updateYtdlpMutation.isPending ? (
                      <>
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        Updating...
                      </>
                    ) : (
                      'Update yt-dlp'
                    )}
                  </button>
                </div>
              </div>

              <div className="flex gap-2 pt-4">
                <button
                  type="submit"
                  disabled={updateConfig.isPending}
                  className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-400 flex items-center justify-center gap-2"
                >
                  {updateConfig.isPending && <Loader2 className="w-4 h-4 animate-spin" />}
                  Save Settings
                </button>
                <button
                  type="button"
                  onClick={onClose}
                  className="px-4 py-2 bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-300 dark:hover:bg-gray-600"
                >
                  Cancel
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  )
}

// Exclusions Modal Component
function ExclusionsModal({ playlist, onClose }: { playlist: Playlist; onClose: () => void }) {
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
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-hidden flex flex-col">
        <div className="p-6 border-b border-gray-200 dark:border-gray-700">
          <div className="flex justify-between items-center">
            <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
              Edit Exclusions: {playlist.title}
            </h2>
            <button
              onClick={onClose}
              className="text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
            >
              ✕
            </button>
          </div>
          <p className="text-sm text-gray-600 dark:text-gray-400 mt-2">
            Excluded videos will be skipped during downloads
          </p>
        </div>

        <div className="p-6 flex-1 overflow-y-auto">
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
                onKeyPress={(e) => e.key === 'Enter' && handleAdd()}
                placeholder="Enter video ID (e.g., dQw4w9WgXcQ)"
                className="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
              />
              <button
                onClick={handleAdd}
                disabled={!newId.trim()}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed"
              >
                Add
              </button>
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
                    // Search for all excluded video titles on YouTube
                    // Open all tabs immediately to preserve user gesture context
                    excludedIds.forEach((id) => {
                      const info = videoInfo?.[id]
                      const title = info?.title || id
                      const searchQuery = encodeURIComponent(title)
                      window.open(`https://www.youtube.com/results?search_query=${searchQuery}`, '_blank')
                    })
                  }}
                  className="text-xs px-3 py-1 bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-400 hover:bg-yellow-200 dark:hover:bg-yellow-900/50 rounded-full transition-colors"
                  title={`Search for all ${excludedIds.length} excluded video titles on YouTube`}
                >
                  🔍 Search All ({excludedIds.length})
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
                  .slice() // Create a copy to avoid mutating original array
                  .sort((a, b) => {
                    const infoA = videoInfo?.[a]
                    const infoB = videoInfo?.[b]
                    const titleA = infoA?.title || a
                    const titleB = infoB?.title || b
                    
                    // Define priority levels (lower number = higher priority)
                    const getPriority = (title: string, id: string) => {
                      if (title === id) return 4 // No title info (just video ID)
                      if (title.includes('[Deleted video]')) return 3 // Deleted videos
                      if (title.includes('[Private video]')) return 2 // Private videos
                      return 1 // Videos with actual titles
                    }
                    
                    const priorityA = getPriority(titleA, a)
                    const priorityB = getPriority(titleB, b)
                    
                    // Sort by priority first
                    if (priorityA !== priorityB) {
                      return priorityA - priorityB
                    }
                    
                    // Within same priority, sort alphabetically by title
                    return titleA.localeCompare(titleB)
                  })
                  .map((id, index) => {
                  const info = videoInfo?.[id]
                  const title = info?.title || id
                  
                  return (
                    <li
                      key={id}
                      className="flex items-start gap-3 p-3 bg-gray-50 dark:bg-gray-700 rounded-lg"
                    >
                      <span className="text-sm font-semibold text-gray-600 dark:text-gray-400 min-w-[2rem] mt-0.5">
                        {index + 1}.
                      </span>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <a
                            href={`https://www.youtube.com/watch?v=${id}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-sm text-blue-600 dark:text-blue-400 hover:underline truncate"
                            title={`${title}\n\nClick to view in browser`}
                          >
                            {title}
                          </a>
                          {(() => {
                            // Determine status badge based on title
                            if (title === id) {
                              return (
                                <span className="text-xs px-2 py-0.5 bg-gray-200 dark:bg-gray-600 text-gray-700 dark:text-gray-300 rounded-full">
                                  Unknown
                                </span>
                              )
                            } else if (title.includes('[Deleted video]')) {
                              return (
                                <span className="text-xs px-2 py-0.5 bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400 rounded-full">
                                  Likely Gone
                                </span>
                              )
                            } else if (title.includes('[Private video]')) {
                              return (
                                <span className="text-xs px-2 py-0.5 bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-400 rounded-full">
                                  Might Return
                                </span>
                              )
                            } else {
                              return (
                                <span className="text-xs px-2 py-0.5 bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 rounded-full">
                                  Searchable
                                </span>
                              )
                            }
                          })()}
                        </div>
                        <code className="text-xs text-gray-500 dark:text-gray-400 font-mono">
                          {id}
                        </code>
                      </div>
                      <div className="flex gap-1 flex-shrink-0">
                        <button
                          onClick={() => {
                            const searchQuery = encodeURIComponent(title)
                            window.open(`https://www.youtube.com/results?search_query=${searchQuery}`, '_blank')
                          }}
                          className="p-1 text-yellow-600 dark:text-yellow-400 hover:bg-yellow-100 dark:hover:bg-yellow-900/30 rounded text-xs px-2 py-1"
                          title={`Search "${title}" on YouTube\n\nUseful if video was removed and re-uploaded`}
                        >
                          🔍 Search
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
        </div>

        <div className="p-6 border-t border-gray-200 dark:border-gray-700">
          <div className="flex gap-2">
            <button
              onClick={handleSave}
              disabled={updatePlaylist.isPending}
              className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-400 flex items-center justify-center gap-2"
            >
              {updatePlaylist.isPending && <Loader2 className="w-4 h-4 animate-spin" />}
              Save Changes
            </button>
            <button
              onClick={onClose}
              className="px-4 py-2 bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-300 dark:hover:bg-gray-600"
            >
              Cancel
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

// Job Logs View Component
function JobLogsView({
  jobs,
  playlists,
  activityLogs,
  onClearActivity
}: {
  jobs: Job[]
  playlists: Playlist[]
  activityLogs: ActivityLog[]
  onClearActivity: () => void
}) {
  const [selectedSource, setSelectedSource] = useState<string>(() => {
    const running = jobs.find(j => j.status === 'running' || j.status === 'pending')
    if (running) return `job_${running.id}`
    if (jobs.length > 0) return `job_${jobs[0].id}`
    return 'system'
  })
  
  const [selectedLevel, setSelectedLevel] = useState<'ALL' | 'ERROR' | 'WARN' | 'SUCCESS' | 'INFO'>('ALL')
  const [searchQuery, setSearchQuery] = useState('')
  const [autoScroll, setAutoScroll] = useState(true)
  const [copied, setCopied] = useState(false)
  const logsEndRef = useRef<HTMLDivElement>(null)

  // Auto-switch to newly running job if currently on finished job
  useEffect(() => {
    const running = jobs.find(j => j.status === 'running')
    if (running && (!selectedSource.startsWith('job_') || jobs.find(j => `job_${j.id}` === selectedSource)?.status !== 'running')) {
      setSelectedSource(`job_${running.id}`)
    }
  }, [jobs])

  const isJobSource = selectedSource.startsWith('job_')
  const selectedJobId = isJobSource ? parseInt(selectedSource.replace('job_', ''), 10) : null
  const selectedJob = jobs.find(j => j.id === selectedJobId)
  const selectedPlaylist = selectedJob ? playlists.find(p => p.id === selectedJob.playlist_id) : null

  // Fetch job logs if job source is selected
  const { data: jobLogs, isLoading: jobLogsLoading } = useQuery({
    queryKey: ['job-logs', selectedJobId],
    queryFn: async () => {
      if (!selectedJobId) return []
      const res = await jobsApi.logs(selectedJobId, 1000)
      return res.data
    },
    enabled: !!selectedJobId,
    refetchInterval: selectedJob?.status === 'running' ? 1500 : false,
  })

  // Auto scroll to bottom
  useEffect(() => {
    if (autoScroll) {
      logsEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [jobLogs, activityLogs, autoScroll])

  // Parse lines
  const parsedJobLogs = (jobLogs || []).map(entry => {
    const text = entry.message
    let level: 'INFO' | 'WARN' | 'ERROR' | 'SUCCESS' = 'INFO'
    let timestamp = ''
    let body = text

    // Parse [YYYY-MM-DD HH:MM:SS] [LEVEL] msg
    const match = text.match(/^\[(.*?)\]\s*(?:\[(.*?)\])?\s*(.*)$/)
    if (match) {
      timestamp = match[1]
      const rawLevel = match[2]?.toUpperCase()
      if (rawLevel && ['INFO', 'WARN', 'ERROR', 'SUCCESS'].includes(rawLevel)) {
        level = rawLevel as any
      } else {
        if (text.includes('⚠️') || text.toLowerCase().includes('warn')) level = 'WARN'
        else if (text.includes('✗') || text.toLowerCase().includes('error') || text.toLowerCase().includes('failed')) level = 'ERROR'
        else if (text.includes('✓') || text.toLowerCase().includes('completed') || text.toLowerCase().includes('success') || text.toLowerCase().includes('verified')) level = 'SUCCESS'
      }
      body = match[3] || text
    }
    return { timestamp, level, body, raw: text }
  })

  const filteredJobLogs = parsedJobLogs.filter(log => {
    if (selectedLevel !== 'ALL' && log.level !== selectedLevel) return false
    if (searchQuery.trim()) {
      return log.raw.toLowerCase().includes(searchQuery.toLowerCase())
    }
    return true
  })

  const filteredActivityLogs = activityLogs.filter(log => {
    if (selectedLevel !== 'ALL') {
      if (selectedLevel === 'ERROR' && log.level !== 'error') return false
      if (selectedLevel === 'WARN' && log.level !== 'warn') return false
      if (selectedLevel === 'SUCCESS' && log.level !== 'success') return false
      if (selectedLevel === 'INFO' && log.level !== 'info') return false
    }
    if (searchQuery.trim()) {
      return log.message.toLowerCase().includes(searchQuery.toLowerCase()) || log.source.toLowerCase().includes(searchQuery.toLowerCase())
    }
    return true
  })

  const copyToClipboard = () => {
    let content = ''
    if (isJobSource) {
      content = filteredJobLogs.map(l => l.raw).join('\n')
    } else {
      content = filteredActivityLogs.map(l => `[${l.timestamp}] [${l.level.toUpperCase()}] [${l.source}] ${l.message}`).join('\n')
    }
    navigator.clipboard.writeText(content)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const runningJobs = jobs.filter(j => j.status === 'running' || j.status === 'pending')
  const completedJobs = jobs.filter(j => j.status !== 'running' && j.status !== 'pending')

  return (
    <div className="space-y-6">
      {/* Top Controls Bar */}
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-md p-5 border border-gray-200 dark:border-gray-700 space-y-4">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          
          {/* Log Source Selector Dropdown */}
          <div className="flex-1 max-w-xl">
            <label className="block text-xs font-bold uppercase tracking-wider text-gray-500 dark:text-gray-400 mb-1.5 flex items-center gap-1.5">
              <Terminal className="w-3.5 h-3.5 text-blue-500" />
              Log Source
            </label>
            <select
              value={selectedSource}
              onChange={(e) => setSelectedSource(e.target.value)}
              className="w-full px-3.5 py-2.5 bg-gray-50 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg text-sm font-semibold text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:outline-none"
            >
              {runningJobs.length > 0 && (
                <optgroup label="🟢 Active Running Jobs">
                  {runningJobs.map(j => {
                    const pl = playlists.find(p => p.id === j.playlist_id)
                    const title = pl ? pl.title : `Playlist #${j.playlist_id}`
                    return (
                      <option key={j.id} value={`job_${j.id}`}>
                        ⚡ Job #{j.id} — {title} ({j.job_type}) [{j.status.toUpperCase()}]
                      </option>
                    )
                  })}
                </optgroup>
              )}
              
              <optgroup label="⚪ Recent Jobs History">
                {completedJobs.slice(0, 20).map(j => {
                  const pl = playlists.find(p => p.id === j.playlist_id)
                  const title = pl ? pl.title : `Playlist #${j.playlist_id}`
                  return (
                    <option key={j.id} value={`job_${j.id}`}>
                      Job #{j.id} — {title} ({j.job_type}) [{j.status}]
                    </option>
                  )
                })}
              </optgroup>

              <optgroup label="🌐 Live System & Events">
                <option value="system">
                  🌐 System & WebSocket Live Activity ({activityLogs.length} events)
                </option>
              </optgroup>
            </select>
          </div>

          {/* Quick Actions */}
          <div className="flex items-center gap-2 flex-wrap">
            <button
              onClick={() => setAutoScroll(!autoScroll)}
              className={`px-3 py-2 rounded-lg text-xs font-semibold flex items-center gap-1.5 border transition-all ${
                autoScroll
                  ? 'bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-900/30 dark:text-blue-300 dark:border-blue-700'
                  : 'bg-gray-100 text-gray-600 border-gray-200 dark:bg-gray-700 dark:text-gray-400 dark:border-gray-600'
              }`}
              title="Auto-scroll to bottom on new logs"
            >
              <RotateCcw className={`w-3.5 h-3.5 ${autoScroll ? 'animate-spin' : ''}`} />
              Auto-Scroll: {autoScroll ? 'ON' : 'OFF'}
            </button>

            <button
              onClick={copyToClipboard}
              className="px-3 py-2 bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-200 border border-gray-200 dark:border-gray-600 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-colors"
            >
              {copied ? <Check className="w-3.5 h-3.5 text-emerald-500" /> : <Copy className="w-3.5 h-3.5" />}
              {copied ? 'Copied!' : 'Copy Logs'}
            </button>

            {isJobSource && selectedJobId && (
              <a
                href={jobsApi.getDownloadLogUrl(selectedJobId)}
                download={`job_${selectedJobId}.log`}
                target="_blank"
                rel="noreferrer"
                className="px-3 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-semibold flex items-center gap-1.5 shadow-sm transition-colors"
              >
                <DownloadCloud className="w-3.5 h-3.5" />
                Download .log
              </a>
            )}

            {!isJobSource && (
              <button
                onClick={onClearActivity}
                className="px-3 py-2 bg-rose-50 hover:bg-rose-100 text-rose-700 dark:bg-rose-900/30 dark:hover:bg-rose-900/50 dark:text-rose-300 border border-rose-200 dark:border-rose-800 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-colors"
              >
                <Trash2 className="w-3.5 h-3.5" />
                Clear Activity
              </button>
            )}
          </div>
        </div>

        {/* Filters and Search Bar */}
        <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-2 border-t border-gray-100 dark:border-gray-700">
          {/* Level Filter Buttons */}
          <div className="flex items-center gap-1.5 flex-wrap w-full sm:w-auto">
            {(['ALL', 'ERROR', 'WARN', 'SUCCESS', 'INFO'] as const).map(lvl => (
              <button
                key={lvl}
                onClick={() => setSelectedLevel(lvl)}
                className={`px-2.5 py-1 rounded-md text-xs font-semibold transition-all ${
                  selectedLevel === lvl
                    ? lvl === 'ERROR'
                      ? 'bg-rose-600 text-white'
                      : lvl === 'WARN'
                      ? 'bg-amber-500 text-white'
                      : lvl === 'SUCCESS'
                      ? 'bg-emerald-600 text-white'
                      : 'bg-blue-600 text-white'
                    : 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
                }`}
              >
                {lvl}
              </button>
            ))}
          </div>

          {/* Search Box */}
          <div className="relative w-full sm:w-72">
            <Search className="w-3.5 h-3.5 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search in log lines..."
              className="w-full pl-9 pr-3 py-1.5 bg-gray-50 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg text-xs text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>
      </div>

      {/* Selected Job Header / Progress Banner (if job selected) */}
      {isJobSource && selectedJob && (
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-md p-4 border border-gray-200 dark:border-gray-700">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-base font-bold text-gray-900 dark:text-white">
                  {selectedPlaylist ? selectedPlaylist.title : `Playlist #${selectedJob.playlist_id}`}
                </h3>
                <span className={`px-2 py-0.5 rounded-full text-xs font-bold uppercase tracking-wider ${
                  selectedJob.status === 'running'
                    ? 'bg-blue-100 text-blue-800 dark:bg-blue-900/50 dark:text-blue-300 animate-pulse'
                    : selectedJob.status === 'completed'
                    ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/50 dark:text-emerald-300'
                    : selectedJob.status === 'failed'
                    ? 'bg-rose-100 text-rose-800 dark:bg-rose-900/50 dark:text-rose-300'
                    : 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300'
                }`}>
                  {selectedJob.status}
                </span>
                <span className="text-xs text-gray-500 dark:text-gray-400 font-mono">
                  (Job #{selectedJob.id} • {selectedJob.job_type})
                </span>
              </div>
              {selectedJob.error && (
                <p className="text-xs text-rose-600 dark:text-rose-400 mt-1">
                  Error: {selectedJob.error}
                </p>
              )}
            </div>

            {/* Progress Bars */}
            <div className="flex items-center gap-6 text-xs font-medium">
              {selectedJob.job_type !== 'extract' && (
                <div>
                  <div className="flex justify-between gap-2 text-gray-600 dark:text-gray-400 mb-1">
                    <span>Download Progress</span>
                    <span>{selectedJob.download_completed} / {selectedJob.download_total}</span>
                  </div>
                  <div className="w-36 h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                    <div 
                      className="h-full bg-blue-600 transition-all duration-300"
                      style={{
                        width: `${selectedJob.download_total > 0 ? (selectedJob.download_completed / selectedJob.download_total) * 100 : 0}%`
                      }}
                    />
                  </div>
                </div>
              )}

              {selectedJob.job_type !== 'download' && (
                <div>
                  <div className="flex justify-between gap-2 text-gray-600 dark:text-gray-400 mb-1">
                    <span>Audio Extraction</span>
                    <span>{selectedJob.extract_completed} / {selectedJob.extract_total}</span>
                  </div>
                  <div className="w-36 h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                    <div 
                      className="h-full bg-purple-600 transition-all duration-300"
                      style={{
                        width: `${selectedJob.extract_total > 0 ? (selectedJob.extract_completed / selectedJob.extract_total) * 100 : 0}%`
                      }}
                    />
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Terminal Display Console */}
      <div className="bg-gray-950 rounded-xl shadow-2xl border border-gray-800 p-4 font-mono text-xs text-gray-200 min-h-[500px] max-h-[70vh] overflow-y-auto">
        {isJobSource ? (
          jobLogsLoading ? (
            <div className="text-center py-16 text-gray-500">
              <Loader2 className="w-8 h-8 animate-spin mx-auto text-blue-500 mb-2" />
              Loading job output logs...
            </div>
          ) : filteredJobLogs.length > 0 ? (
            <div className="space-y-1">
              {filteredJobLogs.map((log, idx) => (
                <div key={idx} className="flex items-start gap-2.5 hover:bg-gray-900/60 px-2 py-0.5 rounded transition-colors break-all">
                  {log.timestamp && (
                    <span className="text-gray-500 select-none whitespace-nowrap text-[11px]">
                      {log.timestamp}
                    </span>
                  )}
                  {log.level && (
                    <span className={`px-1.5 py-0.2 rounded text-[10px] font-bold select-none whitespace-nowrap ${
                      log.level === 'ERROR'
                        ? 'bg-rose-950 text-rose-300 border border-rose-800'
                        : log.level === 'WARN'
                        ? 'bg-amber-950 text-amber-300 border border-amber-800'
                        : log.level === 'SUCCESS'
                        ? 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                        : 'bg-blue-950 text-blue-300 border border-blue-800'
                    }`}>
                      {log.level}
                    </span>
                  )}
                  <span className={`flex-1 whitespace-pre-wrap ${
                    log.level === 'ERROR'
                      ? 'text-rose-300 font-semibold'
                      : log.level === 'WARN'
                      ? 'text-amber-200'
                      : log.level === 'SUCCESS'
                      ? 'text-emerald-200'
                      : 'text-gray-300'
                  }`}>
                    {log.body}
                  </span>
                </div>
              ))}
              <div ref={logsEndRef} />
            </div>
          ) : (
            <div className="text-center py-20 text-gray-500">
              <Terminal className="w-8 h-8 mx-auto mb-2 opacity-50" />
              No logs matched your current filters.
            </div>
          )
        ) : (
          filteredActivityLogs.length > 0 ? (
            <div className="space-y-1">
              {filteredActivityLogs.map(log => (
                <div key={log.id} className="flex items-start gap-2.5 hover:bg-gray-900/60 px-2 py-0.5 rounded transition-colors break-all">
                  <span className="text-gray-500 select-none whitespace-nowrap text-[11px]">
                    {log.timestamp}
                  </span>
                  <span className={`px-1.5 py-0.2 rounded text-[10px] font-bold select-none whitespace-nowrap ${
                    log.level === 'error'
                      ? 'bg-rose-950 text-rose-300 border border-rose-800'
                      : log.level === 'warn'
                      ? 'bg-amber-950 text-amber-300 border border-amber-800'
                      : log.level === 'success'
                      ? 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                      : 'bg-cyan-950 text-cyan-300 border border-cyan-800'
                  }`}>
                    {log.source.toUpperCase()}
                  </span>
                  <span className={`flex-1 whitespace-pre-wrap ${
                    log.level === 'error'
                      ? 'text-rose-300 font-semibold'
                      : log.level === 'warn'
                      ? 'text-amber-200'
                      : log.level === 'success'
                      ? 'text-emerald-200'
                      : 'text-gray-300'
                  }`}>
                    {log.message}
                  </span>
                </div>
              ))}
              <div ref={logsEndRef} />
            </div>
          ) : (
            <div className="text-center py-20 text-gray-500">
              <Activity className="w-8 h-8 mx-auto mb-2 opacity-50" />
              No system activity events recorded yet.
            </div>
          )
        )}
      </div>
    </div>
  )
}

// Logs Modal Component
function LogsModal({ job, onClose }: { job: Job; onClose: () => void }) {
  const logsEndRef = useRef<HTMLDivElement>(null)
  
  // Fetch logs with auto-refresh
  const { data: logs, isLoading } = useQuery({
    queryKey: ['logs', job.id],
    queryFn: async () => {
      const res = await jobsApi.logs(job.id, 100) // Get last 100 lines
      return res.data
    },
    refetchInterval: job.status === 'running' ? 2000 : false, // Refresh every 2s if running
  })

  // Auto-scroll to bottom when logs update
  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs])

  const copyLogs = () => {
    if (logs) {
      const logText = logs.map(l => l.message).join('\n')
      navigator.clipboard.writeText(logText)
      alert('Logs copied to clipboard!')
    }
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] flex flex-col">
        <div className="p-6 border-b border-gray-200 dark:border-gray-700">
          <div className="flex justify-between items-center">
            <div>
              <h2 className="text-2xl font-bold text-gray-900 dark:text-white">Job Logs</h2>
              <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                Job #{job.id} - {job.job_type} - {job.status}
              </p>
            </div>
            <div className="flex gap-2">
              <button
                onClick={copyLogs}
                className="px-3 py-1 text-sm bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded hover:bg-gray-300 dark:hover:bg-gray-600"
              >
                Copy Logs
              </button>
              <button
                onClick={onClose}
                className="text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
              >
                <X className="w-6 h-6" />
              </button>
            </div>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-6 bg-gray-50 dark:bg-gray-900">
          {isLoading ? (
            <div className="text-center py-8">
              <Loader2 className="w-8 h-8 animate-spin mx-auto text-blue-600" />
              <p className="mt-2 text-gray-600 dark:text-gray-400">Loading logs...</p>
            </div>
          ) : logs && logs.length > 0 ? (
            <div className="font-mono text-sm space-y-1">
              {logs.map((log, index) => (
                <div
                  key={index}
                  className="text-gray-800 dark:text-gray-200 whitespace-pre-wrap break-words"
                >
                  {log.message}
                </div>
              ))}
              <div ref={logsEndRef} />
            </div>
          ) : (
            <div className="text-center py-8 text-gray-500 dark:text-gray-400">
              <p>No logs available yet</p>
            </div>
          )}
        </div>

        <div className="p-4 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800">
          <div className="flex justify-between items-center text-xs text-gray-500 dark:text-gray-400">
            <span>
              {job.status === 'running' ? '🔄 Auto-refreshing every 2 seconds' : '✓ Job completed'}
            </span>
            <span>
              {logs?.length || 0} log entries
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}

export default App
