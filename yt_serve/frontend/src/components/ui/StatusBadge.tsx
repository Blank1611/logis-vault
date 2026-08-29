import React from 'react'

export interface StatusBadgeProps {
  status: string
  label?: string
  className?: string
  pulse?: boolean
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({
  status,
  label,
  className = '',
  pulse,
}) => {
  const normStatus = status.toLowerCase()
  let bgClass = 'bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-300'
  let shouldPulse = pulse ?? false

  switch (normStatus) {
    case 'running':
    case 'downloading':
    case 'extracting':
      bgClass = 'bg-blue-100 dark:bg-blue-900/50 text-blue-800 dark:text-blue-300'
      shouldPulse = pulse !== false
      break
    case 'completed':
    case 'success':
    case 'valid':
    case 'searchable':
      bgClass = 'bg-emerald-100 dark:bg-emerald-900/40 text-emerald-800 dark:text-emerald-300'
      break
    case 'failed':
    case 'error':
    case 'expired':
    case 'likely gone':
      bgClass = 'bg-rose-100 dark:bg-rose-900/40 text-rose-800 dark:text-rose-300'
      break
    case 'cancelled':
    case 'stopped':
      bgClass = 'bg-amber-100 dark:bg-amber-900/40 text-amber-800 dark:text-amber-300'
      break
    case 'pending':
    case 'might return':
    case 'expiring_soon':
      bgClass = 'bg-yellow-100 dark:bg-yellow-900/40 text-yellow-800 dark:text-yellow-300'
      break
    case 'unknown':
    case 'not_installed':
      bgClass = 'bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300'
      break
    default:
      bgClass = 'bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-300'
  }

  return (
    <span
      className={`px-2.5 py-0.5 rounded-full text-xs font-bold uppercase tracking-wider inline-flex items-center gap-1.5 ${bgClass} ${
        shouldPulse ? 'animate-pulse' : ''
      } ${className}`}
    >
      {shouldPulse && <span className="w-1.5 h-1.5 rounded-full bg-current inline-block" />}
      {label || status}
    </span>
  )
}
