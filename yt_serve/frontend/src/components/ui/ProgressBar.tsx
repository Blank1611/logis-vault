import React from 'react'
import { Activity, Clock, Zap } from 'lucide-react'

export function formatBytes(bytes?: number | null): string {
  if (!bytes || bytes <= 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`
}

export function formatSpeed(bytesPerSec?: number | null): string {
  if (!bytesPerSec || bytesPerSec <= 0) return '0 KB/s'
  if (bytesPerSec >= 1024 * 1024) {
    return `${(bytesPerSec / (1024 * 1024)).toFixed(1)} MB/s`
  }
  return `${(bytesPerSec / 1024).toFixed(0)} KB/s`
}

export function formatEta(seconds?: number | null): string {
  if (!seconds || seconds <= 0) return ''
  if (seconds < 60) return `${seconds}s`
  const mins = Math.floor(seconds / 60)
  const secs = seconds % 60
  return `${mins}m ${secs}s`
}

export interface ProgressBarProps {
  completed: number
  total: number
  variant?: 'blue' | 'purple' | 'emerald' | 'amber' | 'rose' | 'cyan'
  height?: 'xs' | 'sm' | 'md' | 'lg'
  showLabel?: boolean
  label?: string
  className?: string
  subLabel?: string
}

export const ProgressBar: React.FC<ProgressBarProps> = ({
  completed,
  total,
  variant = 'blue',
  height = 'md',
  showLabel = false,
  label,
  className = '',
  subLabel,
}) => {
  const percentage = total > 0 ? Math.min(100, Math.max(0, (completed / total) * 100)) : 0

  const variantClasses = {
    blue: 'bg-blue-600 dark:bg-blue-500',
    purple: 'bg-purple-600 dark:bg-purple-500',
    emerald: 'bg-emerald-600 dark:bg-emerald-500',
    amber: 'bg-amber-500 dark:bg-amber-400',
    rose: 'bg-rose-600 dark:bg-rose-500',
    cyan: 'bg-cyan-500 dark:bg-cyan-400',
  }

  const heightClasses = {
    xs: 'h-1',
    sm: 'h-1.5',
    md: 'h-2',
    lg: 'h-3',
  }

  return (
    <div className={`w-full ${className}`}>
      {showLabel && (
        <div className="flex justify-between items-center text-xs text-gray-600 dark:text-gray-400 mb-1">
          <span className="font-medium truncate mr-2">{label || 'Progress'}</span>
          <span className="font-mono whitespace-nowrap">
            {subLabel ? subLabel : `${completed} / ${total} (${Math.round(percentage)}%)`}
          </span>
        </div>
      )}
      <div className={`w-full ${heightClasses[height]} bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden`}>
        <div
          className={`h-full ${variantClasses[variant]} transition-all duration-200 rounded-full`}
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  )
}

export interface DualTierProgressBarProps {
  // Tier 1: Playlist Items
  itemCompleted: number
  itemTotal: number
  itemLabel?: string
  batchInfo?: string | null
  
  // Tier 2: In-Flight Active Track Stream
  currentTitle?: string | null
  bytesDownloaded?: number | null
  bytesTotal?: number | null
  speed?: number | null
  eta?: number | null
  
  variant?: 'blue' | 'purple'
  className?: string
}

export const DualTierProgressBar: React.FC<DualTierProgressBarProps> = ({
  itemCompleted,
  itemTotal,
  itemLabel = 'Downloading Playlist',
  batchInfo,
  currentTitle,
  bytesDownloaded = 0,
  bytesTotal = 0,
  speed = 0,
  eta = 0,
  variant = 'blue',
  className = '',
}) => {
  const hasInFlightData = (bytesTotal && bytesTotal > 0) || (currentTitle && currentTitle.trim().length > 0)
  const etaText = formatEta(eta)

  return (
    <div className={`space-y-2 ${className}`}>
      {/* Tier 1: Overall Playlist Progress */}
      <div>
        <ProgressBar
          completed={itemCompleted}
          total={itemTotal}
          variant={variant}
          height="md"
          showLabel={true}
          label={itemLabel}
        />
        {batchInfo && (
          <div className="text-[11px] text-gray-500 dark:text-gray-400 mt-0.5 font-medium">
            {batchInfo}
          </div>
        )}
      </div>

      {/* Tier 2: In-Flight Active Track Byte Stream Telemetry */}
      {hasInFlightData && (
        <div className="p-2.5 bg-blue-50/80 dark:bg-blue-950/40 border border-blue-200/80 dark:border-blue-800/60 rounded-lg space-y-1.5 animate-fadeIn">
          {/* Active Track Title */}
          {currentTitle && (
            <div className="flex items-center gap-1.5 text-xs text-blue-950 dark:text-blue-200 font-semibold truncate">
              <Activity className="w-3.5 h-3.5 text-blue-600 dark:text-blue-400 shrink-0 animate-pulse" />
              <span className="truncate" title={currentTitle}>
                {currentTitle}
              </span>
            </div>
          )}

          {/* In-Flight Byte Progress Bar */}
          {bytesTotal && bytesTotal > 0 ? (
            <ProgressBar
              completed={bytesDownloaded || 0}
              total={bytesTotal}
              variant="cyan"
              height="xs"
              showLabel={false}
            />
          ) : null}

          {/* Real-time Telemetry Metrics (Bytes, Speed MB/s, ETA) */}
          <div className="flex items-center justify-between text-[11px] text-gray-600 dark:text-gray-400 font-mono pt-0.5">
            <div>
              {bytesTotal && bytesTotal > 0 ? (
                <span>
                  {formatBytes(bytesDownloaded)} / {formatBytes(bytesTotal)}
                </span>
              ) : (
                <span>Streaming in progress...</span>
              )}
            </div>

            <div className="flex items-center gap-3">
              {speed && speed > 0 ? (
                <span className="flex items-center gap-1 text-emerald-600 dark:text-emerald-400 font-semibold">
                  <Zap className="w-3 h-3" />
                  {formatSpeed(speed)}
                </span>
              ) : null}

              {etaText ? (
                <span className="flex items-center gap-1 text-gray-500 dark:text-gray-400">
                  <Clock className="w-3 h-3" />
                  ETA: {etaText}
                </span>
              ) : null}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
