import { useState, useEffect, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { playlistsApi, jobsApi, configApi } from './services/api'
import type { Playlist, Job } from './services/types'
import { useWebSocketEvents } from './hooks/useWebSocket'
import { ThemeProvider } from './context/ThemeContext'
import { ToastProvider, ConfirmProvider, useToast } from './context'
import { Header, SchedulerBanner, type TabType } from './components/layout'
import { PlaylistsPage, LogsPage, SettingsPage, type ActivityLog } from './pages'
import { QuickDownloadCard } from './components/adhoc/QuickDownloadCard'
import { 
  ExclusionsModal, LogsModal, InitialSetupModal, InterruptedJobsDialog, ReorganizeModal, DeduplicateModal 
} from './components/modals'

function AppContent() {
  const { toast } = useToast()
  const [activeTab, setActiveTab] = useState<TabType>('playlists')
  const [showSettings, setShowSettings] = useState(false)
  const [settingsTab, setSettingsTab] = useState<'storage' | 'audio' | 'auth' | 'scheduler' | 'git' | 'network'>('storage')
  const [showReorganize, setShowReorganize] = useState(false)
  const [showDeduplicate, setShowDeduplicate] = useState(false)
  const [showInitialSetup, setShowInitialSetup] = useState(false)
  const [editingExclusions, setEditingExclusions] = useState<Playlist | null>(null)
  const [viewingLogs, setViewingLogs] = useState<Job | null>(null)
  const [interruptedJobs, setInterruptedJobs] = useState<any[]>([])
  const [showInterruptedDialog, setShowInterruptedDialog] = useState(false)
  const [interruptedJobsHandled, setInterruptedJobsHandled] = useState(false)
  const [viewMode, setViewMode] = useState<'grid' | 'list'>(() => {
    try {
      const saved = localStorage.getItem('viewMode')
      return (saved as 'grid' | 'list') || 'grid'
    } catch {
      return 'grid'
    }
  })
  const [expandedRows, setExpandedRows] = useState<Set<number>>(new Set())
  const [activityLogs, setActivityLogs] = useState<ActivityLog[]>([])
  const [completedJobIds, setCompletedJobIds] = useState<Set<number>>(new Set())
  const [refreshingPlaylistId, setRefreshingPlaylistId] = useState<number | null>(null)
  const [cancellingJobId, setCancellingJobId] = useState<number | null>(null)
  const [openFolderPlaylistId, setOpenFolderPlaylistId] = useState<number | null>(null)

  const queryClient = useQueryClient()

  // Save viewMode
  useEffect(() => {
    try {
      localStorage.setItem('viewMode', viewMode)
    } catch (e) {
      console.error('Failed to save viewMode in localStorage', e)
    }
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

  const addActivityLog = useCallback((source: string, type: string, message: string, level: 'info' | 'warn' | 'error' | 'success' = 'info') => {
    const timestamp = new Date().toLocaleTimeString()
    setActivityLogs(prev => [
      { id: Math.random().toString(36).substring(2, 9), timestamp, source, type, message, level },
      ...prev.slice(0, 499)
    ])
  }, [])

  // WebSocket event handler
  const handleWebSocketEvent = useCallback((type: string, data: any) => {
    if (type === 'playlist_updated') {
      addActivityLog('WebSocket', 'playlist_updated', `Playlist update signal received (ID: ${data?.playlist_id || 'all'})`, 'info')
      setRefreshingPlaylistId(prev => {
        if (!data?.playlist_id || prev === data.playlist_id) {
          return null
        }
        return prev
      })
      queryClient.invalidateQueries({ queryKey: ['playlists'] })
      queryClient.refetchQueries({ queryKey: ['playlists'] })
    } else if (type === 'connected') {
      addActivityLog('WebSocket', 'connected', 'Connected to real-time events stream', 'success')
    } else if (type === 'job_status') {
      addActivityLog('JobQueue', 'status_change', `Job #${data?.job_id} status changed to ${data?.status}`, 'info')
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
    } else if (type === 'job_progress' && data?.job_id) {
      queryClient.setQueryData<Job[]>(['jobs'], (oldJobs) => {
        if (!oldJobs) return oldJobs
        return oldJobs.map((j) => {
          if (j.id === data.job_id) {
            return {
              ...j,
              current_video_id: data.current_video_id,
              current_video_title: data.current_video_title,
              current_video_bytes_downloaded: data.bytes_downloaded,
              current_video_bytes_total: data.bytes_total,
              current_video_speed: data.speed,
              current_video_eta: data.eta,
              download_completed: data.download_completed ?? j.download_completed,
              download_total: data.download_total ?? j.download_total,
            }
          }
          return j
        })
      })
    }
  }, [queryClient, addActivityLog])

  useWebSocketEvents(handleWebSocketEvent)

  // Fetch initial config
  const { data: config } = useQuery({
    queryKey: ['config'],
    queryFn: async () => {
      const res = await configApi.get()
      return res.data
    },
    staleTime: 0,
    refetchOnMount: true,
  })

  useEffect(() => {
    if (config?.needs_setup) {
      setShowInitialSetup(true)
    }
  }, [config])

  // Check interrupted jobs
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

  // Queries
  const { data: playlists = [], isLoading: playlistsLoading } = useQuery({
    queryKey: ['playlists'],
    queryFn: async () => {
      const res = await playlistsApi.list()
      return res.data
    },
    refetchInterval: 30000,
    staleTime: 0,
    refetchOnMount: true,
    refetchOnWindowFocus: true,
  })

  const { data: jobs = [] } = useQuery({
    queryKey: ['jobs'],
    queryFn: async () => {
      const res = await jobsApi.list()
      return res.data
    },
    refetchInterval: 2000,
  })

  const { data: schedulerStatus } = useQuery({
    queryKey: ['scheduler-status'],
    queryFn: async () => {
      const res = await configApi.getSchedulerStatus()
      return res.data
    },
    refetchInterval: 4000,
  })

  // Watch newly completed jobs
  useEffect(() => {
    if (jobs && jobs.length > 0) {
      const newlyCompleted = jobs.filter(j => 
        (j.status === 'completed' || j.status === 'failed' || j.status === 'cancelled') &&
        !completedJobIds.has(j.id)
      )
      if (newlyCompleted.length > 0) {
        setCompletedJobIds(prev => new Set([...prev, ...newlyCompleted.map(j => j.id)]))
        queryClient.invalidateQueries({ queryKey: ['playlists'] })
        queryClient.refetchQueries({ queryKey: ['playlists'] })
      }
    }
  }, [jobs, completedJobIds, queryClient])

  // Mutations
  const deletePlaylist = useMutation({
    mutationFn: (id: number) => playlistsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['playlists'] })
    },
  })

  const refreshPlaylist = useMutation({
    mutationFn: async (id: number) => {
      setRefreshingPlaylistId(id)
      return playlistsApi.refresh(id)
    },
    onSuccess: (_, id) => {
      // Safety timeout: reset loading spinner after 30s in case WebSocket notification drops
      setTimeout(() => {
        setRefreshingPlaylistId(prev => prev === id ? null : prev)
      }, 30000)
    },
    onError: (err: any) => {
      setRefreshingPlaylistId(null)
      const msg = err.response?.data?.detail || err.message
      toast.error(`Cannot refresh playlist:\n\n${msg}`)
    },
  })

  const startJob = useMutation({
    mutationFn: ({ playlistId, jobType }: { playlistId: number; jobType: 'download' | 'extract' | 'both' }) =>
      jobsApi.create(playlistId, jobType),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
    },
    onError: (err: any) => {
      const msg = err.response?.data?.detail || err.message
      toast.error(`Cannot start job:\n\n${msg}`)
    },
  })

  const cancelJob = useMutation({
    mutationFn: async (id: number) => {
      setCancellingJobId(id)
      return jobsApi.cancel(id)
    },
    onSettled: () => {
      setCancellingJobId(null)
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
    },
  })

  const openFolder = useMutation({
    mutationFn: async (id: number) => {
      setOpenFolderPlaylistId(id)
      return playlistsApi.openFolder(id)
    },
    onSettled: () => {
      setOpenFolderPlaylistId(null)
    },
    onError: (error: any) => {
      const errorDetail = error.response?.data?.detail || error.message
      toast.error(`Error opening folder:\n\n${errorDetail}`)
    },
  })

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

  const runningJobsCount = jobs.filter(j => j.status === 'running' || j.status === 'pending').length

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 transition-colors">
      {showSettings ? (
        <SettingsPage
          initialTab={settingsTab}
          onBack={() => setShowSettings(false)}
          onOpenDeduplicate={() => {
            setShowSettings(false)
            setShowDeduplicate(true)
          }}
        />
      ) : (
        <>
          {/* Header */}
          <Header
            activeTab={activeTab}
            onTabChange={setActiveTab}
            runningJobsCount={runningJobsCount}
            onOpenSettings={() => setShowSettings(true)}
            onOpenSettingsTab={(tab) => {
              setSettingsTab(tab || 'storage')
              setShowSettings(true)
            }}
          />

          {/* Main Container */}
          <main className="w-full max-w-[min(94vw,1920px)] mx-auto px-4 sm:px-6 lg:px-8 py-8">
            <SchedulerBanner schedulerStatus={schedulerStatus} />

            <div className={activeTab === 'playlists' ? 'block' : 'hidden'}>
              <PlaylistsPage
                playlists={playlists}
                jobs={jobs}
                isLoading={playlistsLoading}
                viewMode={viewMode}
                onViewModeChange={setViewMode}
                onOpenReorganize={() => setShowReorganize(true)}
                onOpenDeduplicate={() => setShowDeduplicate(true)}
                expandedRows={expandedRows}
                onToggleRow={toggleRow}
                isScanning={schedulerStatus?.is_scanning}
                currentScanningPlaylist={schedulerStatus?.current_playlist}
                onStartJob={(playlistId, jobType) => startJob.mutate({ playlistId, jobType })}
                onCancelJob={(jobId) => cancelJob.mutate(jobId)}
                onRefresh={(playlistId) => refreshPlaylist.mutate(playlistId)}
                onDelete={(playlistId) => deletePlaylist.mutate(playlistId)}
                onOpenFolder={(playlistId) => openFolder.mutate(playlistId)}
                onEditExclusions={(playlist) => setEditingExclusions(playlist)}
                onViewLogs={(job) => setViewingLogs(job)}
                refreshingPlaylistId={refreshingPlaylistId}
                cancellingJobId={cancellingJobId}
                openFolderPlaylistId={openFolderPlaylistId}
              />
            </div>

            <div className={activeTab === 'quick-download' ? 'block space-y-6' : 'hidden'}>
              <QuickDownloadCard 
                jobs={jobs}
                onJobStarted={() => {
                  // Stay on page and let user see active progress
                }} 
                onViewJobLogs={() => {
                  setActiveTab('logs')
                }}
              />
            </div>

            <div className={activeTab === 'logs' ? 'block' : 'hidden'}>
              <LogsPage
                jobs={jobs}
                playlists={playlists}
                activityLogs={activityLogs}
                onClearActivity={() => setActivityLogs([])}
                onCancelJob={(jobId) => cancelJob.mutate(jobId)}
              />
            </div>
          </main>
        </>
      )}

      {showReorganize && (
        <ReorganizeModal
          isOpen={showReorganize}
          onClose={() => setShowReorganize(false)}
        />
      )}

      {showDeduplicate && (
        <DeduplicateModal
          isOpen={showDeduplicate}
          onClose={() => setShowDeduplicate(false)}
        />
      )}

      {editingExclusions && (
        <ExclusionsModal
          playlist={editingExclusions}
          onClose={() => setEditingExclusions(null)}
        />
      )}

      {viewingLogs && (
        <LogsModal
          job={viewingLogs}
          onClose={() => setViewingLogs(null)}
        />
      )}

      {showInitialSetup && (
        <InitialSetupModal
          onComplete={() => {
            setShowInitialSetup(false)
            queryClient.invalidateQueries({ queryKey: ['config'] })
          }}
          onOpenSettings={(tab) => {
            if (tab) setSettingsTab(tab)
            setShowSettings(true)
          }}
        />
      )}

      {showInterruptedDialog && interruptedJobs.length > 0 && (
        <InterruptedJobsDialog
          jobs={interruptedJobs}
          isLoading={handleInterruptedJobs.isPending}
          onResumeAll={async () => {
            await handleInterruptedJobs.mutateAsync({ action: 'resume_all' })
          }}
          onCancelAll={async () => {
            await handleInterruptedJobs.mutateAsync({ action: 'cancel_all' })
          }}
          onIndividual={async (decisions) => {
            await handleInterruptedJobs.mutateAsync({ action: 'individual', jobDecisions: decisions })
          }}
        />
      )}
    </div>
  )
}

function App() {
  return (
    <ThemeProvider>
      <ToastProvider>
        <ConfirmProvider>
          <AppContent />
        </ConfirmProvider>
      </ToastProvider>
    </ThemeProvider>
  )
}

export default App
