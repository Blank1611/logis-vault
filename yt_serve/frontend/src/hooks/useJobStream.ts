import { useEffect, useRef, useState } from 'react'
import type { Job, LogEntry } from '../services/types'

export interface JobStreamData {
  job: Partial<Job> | null
  logs: LogEntry[]
  isConnected: boolean
  error: string | null
}

export function useJobStream(jobId: number | null): JobStreamData {
  const [job, setJob] = useState<Partial<Job> | null>(null)
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [isConnected, setIsConnected] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const eventSourceRef = useRef<EventSource | null>(null)

  useEffect(() => {
    if (!jobId) {
      setJob(null)
      setLogs([])
      setIsConnected(false)
      return
    }

    const sseUrl = `/api/downloads/jobs/${jobId}/stream`
    const es = new EventSource(sseUrl)
    eventSourceRef.current = es

    es.onopen = () => {
      setIsConnected(true)
      setError(null)
    }

    es.addEventListener('progress', (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data)
        setJob((prev) => ({
          ...prev,
          ...data,
          current_video_bytes_downloaded: data.bytes_downloaded,
          current_video_bytes_total: data.bytes_total,
        }))
      } catch (err) {
        console.error('[SSE] Failed to parse progress event:', err)
      }
    })

    es.addEventListener('log', (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data)
        setLogs((prev) => [...prev, { message: data.message }])
      } catch (err) {
        console.error('[SSE] Failed to parse log event:', err)
      }
    })

    es.addEventListener('completed', (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data)
        setJob((prev) => ({ ...prev, status: data.status, error: data.error }))
      } catch (err) {
        console.error('[SSE] Failed to parse completed event:', err)
      }
      es.close()
      setIsConnected(false)
    })

    es.onerror = () => {
      setError('SSE stream disconnected. Retrying...')
      setIsConnected(false)
    }

    return () => {
      es.close()
      eventSourceRef.current = null
    }
  }, [jobId])

  return { job, logs, isConnected, error }
}
