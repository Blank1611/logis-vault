import React, { useState, useEffect, useRef } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { jobsApi, logsApi, type ServerLogEntry } from '../services/api'
import type { Playlist, Job } from '../services/types'
import { Button } from '../components/ui/Button'
import { StatusBadge } from '../components/ui/StatusBadge'
import { ProgressBar, DualTierProgressBar } from '../components/ui/ProgressBar'
import { 
  Terminal, RotateCcw, Copy, Check, DownloadCloud, Trash2, Search, Loader2, Activity, Server, PlayCircle
} from 'lucide-react'
import { useToast } from '../context'
import { copyToClipboard } from '../utils/clipboard'

export interface ActivityLog {
  id: string
  timestamp: string
  source: string
  type: string
  message: string
  level: 'info' | 'warn' | 'error' | 'success'
}

export interface LogsPageProps {
  jobs: Job[]
  playlists: Playlist[]
  activityLogs: ActivityLog[]
  onClearActivity: () => void
}

export const LogsPage: React.FC<LogsPageProps> = ({
  jobs,
  playlists,
  activityLogs,
  onClearActivity,
}) => {
  const queryClient = useQueryClient()
  const { toast } = useToast()

  // Top-level tab: 'system' (Live System & Observability) vs 'jobs' (Job History & Execution)
  const [activeTab, setActiveTab] = useState<'system' | 'jobs'>(() => {
    const running = jobs.find(j => j.status === 'running' || j.status === 'pending')
    return running ? 'jobs' : 'system'
  })

  // Sub-source for system tab: 'server' (Central Server Logs via SSE/Ring Buffer) vs 'browser' (Client session events)
  const [systemLogType, setSystemLogType] = useState<'server' | 'browser'>('server')

  // Selected job for jobs tab
  const [selectedJobId, setSelectedJobId] = useState<number | null>(() => {
    const running = jobs.find(j => j.status === 'running' || j.status === 'pending')
    if (running) return running.id
    if (jobs.length > 0) return jobs[0].id
    return null
  })

  const [selectedLevel, setSelectedLevel] = useState<'ALL' | 'ERROR' | 'WARN' | 'SUCCESS' | 'INFO'>('ALL')
  const [searchQuery, setSearchQuery] = useState('')
  const [autoScroll, setAutoScroll] = useState(true)
  const [copied, setCopied] = useState(false)
  const logsEndRef = useRef<HTMLDivElement>(null)

  // Auto-switch to newly running job if one starts
  useEffect(() => {
    const running = jobs.find(j => j.status === 'running')
    if (running) {
      if (selectedJobId !== running.id) {
        setSelectedJobId(running.id)
      }
    }
  }, [jobs, selectedJobId])

  const runningJobs = jobs.filter(j => j.status === 'running' || j.status === 'pending')
  const completedJobs = jobs.filter(j => j.status !== 'running' && j.status !== 'pending')

  const selectedJob = jobs.find(j => j.id === selectedJobId)
  const selectedPlaylist = selectedJob ? playlists.find(p => p.id === selectedJob.playlist_id) : null

  // Fetch job logs if on jobs tab and job is selected
  const { data: jobLogs, isLoading: jobLogsLoading } = useQuery({
    queryKey: ['job-logs', selectedJobId],
    queryFn: async () => {
      if (!selectedJobId) return []
      const res = await jobsApi.logs(selectedJobId, 1000)
      return res.data
    },
    enabled: activeTab === 'jobs' && !!selectedJobId,
    refetchInterval: selectedJob?.status === 'running' ? 1500 : false,
  })

  // Fetch central ring buffer server logs if on system tab and server logs selected
  const { data: serverLogs = [] } = useQuery({
    queryKey: ['server-logs'],
    queryFn: async () => {
      const res = await logsApi.getRecent({ limit: 500 })
      // Display oldest to newest so newest entries scroll in at bottom like standard console
      return (res.data || []).slice().reverse()
    },
    enabled: activeTab === 'system' && systemLogType === 'server',
    staleTime: 5000,
  })

  // Live SSE stream for server logs
  useEffect(() => {
    if (activeTab !== 'system' || systemLogType !== 'server') return

    const es = new EventSource('/api/logs/stream')
    es.addEventListener('log', (event: MessageEvent) => {
      try {
        const item: ServerLogEntry = JSON.parse(event.data)
        queryClient.setQueryData<ServerLogEntry[]>(['server-logs'], (prev = []) => {
          if (prev.some(p => p.id === item.id)) return prev
          return [...prev, item].slice(-500)
        })
      } catch (err) {
        console.error('[SSE Logs] Error parsing record:', err)
      }
    })

    return () => {
      es.close()
    }
  }, [activeTab, systemLogType, queryClient])

  // Auto scroll to bottom
  useEffect(() => {
    if (autoScroll) {
      logsEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [jobLogs, serverLogs, activityLogs, autoScroll, activeTab, systemLogType])

  // Parse lines for jobs
  const parsedJobLogs = (jobLogs || []).map(entry => {
    const text = entry.message
    let level: 'INFO' | 'WARN' | 'ERROR' | 'SUCCESS' = 'INFO'
    let timestamp = ''
    let body = text

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

  const filteredServerLogs = serverLogs.filter(log => {
    if (selectedLevel !== 'ALL') {
      const lvl = log.level.toUpperCase()
      if (selectedLevel === 'ERROR' && lvl !== 'ERROR' && lvl !== 'CRITICAL') return false
      if (selectedLevel === 'WARN' && lvl !== 'WARN' && lvl !== 'WARNING') return false
      if (selectedLevel === 'INFO' && lvl !== 'INFO') return false
      if (selectedLevel === 'SUCCESS' && lvl !== 'SUCCESS') return false
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase()
      return log.message.toLowerCase().includes(q) || (log.source && log.source.toLowerCase().includes(q))
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
      const q = searchQuery.toLowerCase()
      return log.message.toLowerCase().includes(q) || log.source.toLowerCase().includes(q)
    }
    return true
  })

  const handleCopyLogs = async () => {
    let content = ''
    if (activeTab === 'jobs') {
      content = filteredJobLogs.map(l => l.raw).join('\n')
    } else if (systemLogType === 'server') {
      content = filteredServerLogs.map(l => `[${l.timestamp}] [${l.level}] [${l.source || l.logger}] ${l.message}`).join('\n')
    } else {
      content = filteredActivityLogs.map(l => `[${l.timestamp}] [${l.level.toUpperCase()}] [${l.source}] ${l.message}`).join('\n')
    }
    const success = await copyToClipboard(content)
    if (success) {
      setCopied(true)
      toast.success('Logs copied to clipboard!')
      setTimeout(() => setCopied(false), 2000)
    } else {
      toast.error('Failed to copy logs to clipboard')
    }
  }

  return (
    <div className="space-y-5">
      {/* Primary Navigation Tabs */}
      <div className="flex border-b border-gray-200 dark:border-gray-700 gap-3">
        <button
          onClick={() => setActiveTab('system')}
          className={`pb-3 px-3 font-semibold text-sm flex items-center gap-2 border-b-2 transition-all ${
            activeTab === 'system'
              ? 'border-blue-600 text-blue-600 dark:text-blue-400 dark:border-blue-400'
              : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200'
          }`}
        >
          <Server className="w-4 h-4" />
          Live System & Observability
          <span className="text-xs px-2 py-0.5 rounded-full bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300 font-normal">
            Server & App
          </span>
        </button>

        <button
          onClick={() => setActiveTab('jobs')}
          className={`pb-3 px-3 font-semibold text-sm flex items-center gap-2 border-b-2 transition-all ${
            activeTab === 'jobs'
              ? 'border-blue-600 text-blue-600 dark:text-blue-400 dark:border-blue-400'
              : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200'
          }`}
        >
          <PlayCircle className="w-4 h-4" />
          Job History & Execution
          {runningJobs.length > 0 && (
            <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-300 font-bold animate-pulse">
              {runningJobs.length} Running
            </span>
          )}
        </button>
      </div>

      {/* Controls and Selectors Bar */}
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-md p-5 border border-gray-200 dark:border-gray-700 space-y-4">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          
          {/* Sub-selector depending on active tab */}
          {activeTab === 'system' ? (
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-xs font-bold uppercase tracking-wider text-gray-500 dark:text-gray-400 mr-2">
                Observability Feed:
              </span>
              <button
                onClick={() => setSystemLogType('server')}
                className={`px-3.5 py-2 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all ${
                  systemLogType === 'server'
                    ? 'bg-blue-600 text-white shadow-sm'
                    : 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
                }`}
              >
                <Server className="w-3.5 h-3.5" />
                Central Server Logs (Ring Buffer & SSE)
              </button>

              <button
                onClick={() => setSystemLogType('browser')}
                className={`px-3.5 py-2 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all ${
                  systemLogType === 'browser'
                    ? 'bg-blue-600 text-white shadow-sm'
                    : 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
                }`}
                title="Ephemeral client-side UI and WebSocket notifications recorded during the current browser tab session"
              >
                <Activity className="w-3.5 h-3.5" />
                Browser Session Events ({activityLogs.length})
              </button>
            </div>
          ) : (
            <div className="flex-1 max-w-xl">
              <label className="block text-xs font-bold uppercase tracking-wider text-gray-500 dark:text-gray-400 mb-1.5 flex items-center gap-1.5">
                <Terminal className="w-3.5 h-3.5 text-blue-500" />
                Select Job Execution Log:
              </label>
              <select
                value={selectedJobId || ''}
                onChange={(e) => setSelectedJobId(e.target.value ? parseInt(e.target.value, 10) : null)}
                className="w-full px-3.5 py-2.5 bg-gray-50 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg text-sm font-semibold text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:outline-none"
              >
                {runningJobs.length > 0 && (
                  <optgroup label="🟢 Active Running Jobs">
                    {runningJobs.map(j => {
                      const pl = playlists.find(p => p.id === j.playlist_id)
                      const title = pl ? pl.title : `Playlist #${j.playlist_id}`
                      return (
                        <option key={j.id} value={j.id}>
                          ⚡ Job #{j.id} — {title} ({j.job_type}) [{j.status.toUpperCase()}]
                        </option>
                      )
                    })}
                  </optgroup>
                )}
                
                <optgroup label="⚪ Recent Completed Jobs">
                  {completedJobs.slice(0, 30).map(j => {
                    const pl = playlists.find(p => p.id === j.playlist_id)
                    const title = pl ? pl.title : `Playlist #${j.playlist_id}`
                    return (
                      <option key={j.id} value={j.id}>
                        Job #{j.id} — {title} ({j.job_type}) [{j.status}]
                      </option>
                    )
                  })}
                </optgroup>
              </select>
            </div>
          )}

          {/* Quick Actions Bar */}
          <div className="flex items-center gap-2 flex-wrap">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setAutoScroll(!autoScroll)}
              icon={<RotateCcw className={`w-3.5 h-3.5 ${autoScroll ? 'animate-spin' : ''}`} />}
              className={autoScroll ? 'bg-blue-50 text-blue-700 border border-blue-200 dark:bg-blue-900/30 dark:text-blue-300' : ''}
              title="Auto-scroll to bottom on new logs"
            >
              Auto-Scroll: {autoScroll ? 'ON' : 'OFF'}
            </Button>

            <Button
              variant="secondary"
              size="sm"
              onClick={handleCopyLogs}
              icon={copied ? <Check className="w-3.5 h-3.5 text-emerald-500" /> : <Copy className="w-3.5 h-3.5" />}
            >
              {copied ? 'Copied!' : 'Copy Logs'}
            </Button>

            {activeTab === 'jobs' && selectedJobId && (
              <a
                href={jobsApi.getDownloadLogUrl(selectedJobId)}
                download={`job_${selectedJobId}.log`}
                target="_blank"
                rel="noreferrer"
                className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-semibold flex items-center gap-1.5 shadow-sm transition-colors"
              >
                <DownloadCloud className="w-3.5 h-3.5" />
                Download .log
              </a>
            )}

            {activeTab === 'system' && systemLogType === 'server' && (
              <>
                <a
                  href={logsApi.getLogFileUrl()}
                  download="yt_manager.log"
                  target="_blank"
                  rel="noreferrer"
                  className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-semibold flex items-center gap-1.5 shadow-sm transition-colors"
                >
                  <DownloadCloud className="w-3.5 h-3.5" />
                  Download Server Log
                </a>

                <Button
                  variant="danger"
                  size="sm"
                  onClick={async () => {
                    await logsApi.clear()
                    queryClient.invalidateQueries({ queryKey: ['server-logs'] })
                  }}
                  icon={<Trash2 className="w-3.5 h-3.5" />}
                >
                  Clear Buffer
                </Button>
              </>
            )}

            {activeTab === 'system' && systemLogType === 'browser' && (
              <Button
                variant="danger"
                size="sm"
                onClick={onClearActivity}
                icon={<Trash2 className="w-3.5 h-3.5" />}
              >
                Clear Events
              </Button>
            )}
          </div>
        </div>

        {/* Filters and Search Bar */}
        <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-2 border-t border-gray-100 dark:border-gray-700">
          {/* Level Filter Buttons */}
          <div className="flex items-center gap-1.5 overflow-x-auto w-full sm:w-auto pb-1 sm:pb-0">
            {(['ALL', 'ERROR', 'WARN', 'SUCCESS', 'INFO'] as const).map(lvl => (
              <button
                key={lvl}
                onClick={() => setSelectedLevel(lvl)}
                className={`px-2.5 py-1 rounded-md text-xs font-bold transition-all ${
                  selectedLevel === lvl
                    ? lvl === 'ERROR'
                      ? 'bg-rose-600 text-white shadow-sm'
                      : lvl === 'WARN'
                      ? 'bg-amber-500 text-white shadow-sm'
                      : lvl === 'SUCCESS'
                      ? 'bg-emerald-600 text-white shadow-sm'
                      : lvl === 'INFO'
                      ? 'bg-blue-600 text-white shadow-sm'
                      : 'bg-gray-800 text-white dark:bg-gray-200 dark:text-gray-900 shadow-sm'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200 dark:bg-gray-700 dark:text-gray-300 dark:hover:bg-gray-600'
                }`}
              >
                {lvl}
              </button>
            ))}
          </div>

          {/* Search Box */}
          <div className="relative w-full sm:w-72">
            <Search className="w-3.5 h-3.5 absolute left-3 top-2.5 text-gray-400" />
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

      {/* Selected Job Header / Progress Banner (for Job Execution Tab) */}
      {activeTab === 'jobs' && selectedJob && (
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-md p-4 border border-gray-200 dark:border-gray-700">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-2 flex-wrap">
                <h3 className="text-base font-bold text-gray-900 dark:text-white">
                  {selectedPlaylist ? selectedPlaylist.title : `Playlist #${selectedJob.playlist_id}`}
                </h3>
                <StatusBadge status={selectedJob.status} />
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
            <div className="flex items-center gap-6 text-xs font-medium flex-wrap">
              {selectedJob.job_type !== 'extract' && (
                <div className="min-w-[240px]">
                  <DualTierProgressBar
                    itemCompleted={selectedJob.download_completed}
                    itemTotal={selectedJob.download_total}
                    itemLabel="Download Progress"
                    batchInfo={selectedJob.download_batch_info}
                    currentTitle={selectedJob.current_video_title}
                    bytesDownloaded={selectedJob.current_video_bytes_downloaded}
                    bytesTotal={selectedJob.current_video_bytes_total}
                    speed={selectedJob.current_video_speed}
                    eta={selectedJob.current_video_eta}
                    variant="blue"
                  />
                </div>
              )}

              {selectedJob.job_type !== 'download' && (
                <div className="min-w-[180px]">
                  <ProgressBar
                    completed={selectedJob.extract_completed}
                    total={selectedJob.extract_total}
                    variant="purple"
                    height="sm"
                    showLabel={true}
                    label="Audio Extraction"
                  />
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Terminal Display Console */}
      <div className="bg-gray-950 rounded-xl shadow-2xl border border-gray-800 p-4 font-mono text-xs text-gray-200 min-h-[500px] max-h-[70vh] overflow-y-auto">
        {activeTab === 'jobs' ? (
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
                    <span className="text-gray-500 whitespace-nowrap text-[11px]">
                      {log.timestamp}
                    </span>
                  )}
                  {log.level && (
                    <span className={`px-1.5 py-0.2 rounded text-[10px] font-bold whitespace-nowrap ${
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
              {selectedJobId ? 'No log lines found for this job.' : 'Select a job to view its execution logs.'}
            </div>
          )
        ) : systemLogType === 'server' ? (
          filteredServerLogs.length > 0 ? (
            <div className="space-y-1">
              {filteredServerLogs.map(log => {
                const lvl = log.level.toUpperCase()
                return (
                  <div key={log.id} className="flex items-start gap-2.5 hover:bg-gray-900/60 px-2 py-0.5 rounded transition-colors break-all">
                    <span className="text-gray-500 whitespace-nowrap text-[11px]">
                      {log.timestamp.replace('T', ' ').replace('Z', '')}
                    </span>
                    <span className={`px-1.5 py-0.2 rounded text-[10px] font-bold whitespace-nowrap ${
                      lvl === 'ERROR' || lvl === 'CRITICAL'
                        ? 'bg-rose-950 text-rose-300 border border-rose-800'
                        : lvl === 'WARN' || lvl === 'WARNING'
                        ? 'bg-amber-950 text-amber-300 border border-amber-800'
                        : lvl === 'SUCCESS'
                        ? 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                        : 'bg-cyan-950 text-cyan-300 border border-cyan-800'
                    }`}>
                      {lvl}
                    </span>
                    <span className="px-1.5 py-0.2 rounded text-[10px] text-gray-400 bg-gray-900 border border-gray-800 font-mono">
                      {log.source || log.logger}
                    </span>
                    <span className={`flex-1 whitespace-pre-wrap ${
                      lvl === 'ERROR' || lvl === 'CRITICAL'
                        ? 'text-rose-300 font-semibold'
                        : lvl === 'WARN' || lvl === 'WARNING'
                        ? 'text-amber-200'
                        : 'text-gray-300'
                    }`}>
                      {log.message}
                    </span>
                  </div>
                )
              })}
              <div ref={logsEndRef} />
            </div>
          ) : (
            <div className="text-center py-20 text-gray-500">
              <Server className="w-8 h-8 mx-auto mb-2 opacity-50" />
              No server logs in ring buffer yet.
            </div>
          )
        ) : (
          filteredActivityLogs.length > 0 ? (
            <div className="space-y-1">
              {filteredActivityLogs.map(log => (
                <div key={log.id} className="flex items-start gap-2.5 hover:bg-gray-900/60 px-2 py-0.5 rounded transition-colors break-all">
                  <span className="text-gray-500 whitespace-nowrap text-[11px]">
                    {log.timestamp}
                  </span>
                  <span className={`px-1.5 py-0.2 rounded text-[10px] font-bold whitespace-nowrap ${
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
              No client-side browser session events recorded yet.
            </div>
          )
        )}
      </div>
    </div>
  )
}
