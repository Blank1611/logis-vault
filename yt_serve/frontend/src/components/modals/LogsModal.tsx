import React, { useRef, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { jobsApi } from '../../services/api'
import type { Job } from '../../services/types'
import { Modal } from '../ui/Modal'
import { Button } from '../ui/Button'
import { Loader2, Copy } from 'lucide-react'

import { useToast } from '../../context'

export interface LogsModalProps {
  job: Job
  onClose: () => void
}

export const LogsModal: React.FC<LogsModalProps> = ({ job, onClose }) => {
  const { toast } = useToast()
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
      toast.success('Logs copied to clipboard!')
    }
  }

  return (
    <Modal
      isOpen={true}
      onClose={onClose}
      title="Job Logs"
      subtitle={`Job #${job.id} - ${job.job_type} - ${job.status}`}
      maxWidth="4xl"
      headerActions={
        <Button
          variant="secondary"
          size="sm"
          onClick={copyLogs}
          icon={<Copy className="w-3.5 h-3.5" />}
        >
          Copy Logs
        </Button>
      }
      footer={
        <div className="flex justify-between items-center text-xs text-gray-500 dark:text-gray-400 w-full">
          <span>
            {job.status === 'running' ? '🔄 Auto-refreshing every 2 seconds' : '✓ Job completed'}
          </span>
          <span>
            {logs?.length || 0} log entries
          </span>
        </div>
      }
    >
      <div className="p-4 bg-gray-900 rounded-lg min-h-[300px] max-h-[60vh] overflow-y-auto">
        {isLoading ? (
          <div className="text-center py-8 text-gray-400">
            <Loader2 className="w-8 h-8 animate-spin mx-auto text-blue-500 mb-2" />
            <p className="text-sm">Loading logs...</p>
          </div>
        ) : logs && logs.length > 0 ? (
          <div className="font-mono text-xs text-gray-200 space-y-1">
            {logs.map((log, index) => (
              <div
                key={index}
                className="whitespace-pre-wrap break-words hover:bg-gray-800/60 px-2 py-0.5 rounded transition-colors"
              >
                {log.message}
              </div>
            ))}
            <div ref={logsEndRef} />
          </div>
        ) : (
          <div className="text-center py-12 text-gray-500">
            <p>No logs available yet</p>
          </div>
        )}
      </div>
    </Modal>
  )
}
