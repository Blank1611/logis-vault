import React from 'react'
import { RefreshCw } from 'lucide-react'

export interface SchedulerBannerProps {
  schedulerStatus?: {
    is_scanning?: boolean
    completed_count?: number
    total_count?: number
    current_playlist?: string | null
  } | null
}

export const SchedulerBanner: React.FC<SchedulerBannerProps> = ({ schedulerStatus }) => {
  if (!schedulerStatus?.is_scanning) return null

  return (
    <div className="mb-6 p-4 bg-blue-50 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-800 rounded-xl flex items-center justify-between shadow-sm animate-pulse">
      <div className="flex items-center gap-3.5">
        <div className="w-9 h-9 rounded-lg bg-blue-600 text-white flex items-center justify-center flex-shrink-0 shadow-sm">
          <RefreshCw className="w-5 h-5 animate-spin" />
        </div>
        <div>
          <h4 className="text-sm font-bold text-blue-950 dark:text-blue-200">
            Daily Metadata Auto-Scan in Progress ({schedulerStatus.completed_count}/{schedulerStatus.total_count})
          </h4>
          <p className="text-xs text-blue-700 dark:text-blue-300 mt-0.5">
            Scanning: <span className="font-semibold">{schedulerStatus.current_playlist || 'Initializing...'}</span> (Manual refresh paused to prevent rate-limits)
          </p>
        </div>
      </div>
      <span className="hidden sm:inline-flex text-xs font-mono font-medium px-2.5 py-1 rounded bg-blue-100 dark:bg-blue-900/60 text-blue-800 dark:text-blue-300">
        Scheduled Auto-Scan
      </span>
    </div>
  )
}
