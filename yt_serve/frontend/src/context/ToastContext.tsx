import React, { createContext, useContext, useState, useCallback } from 'react'
import { CheckCircle2, AlertCircle, Info, AlertTriangle, X } from 'lucide-react'

export type ToastType = 'success' | 'error' | 'info' | 'warning'

export interface ToastItem {
  id: string
  type: ToastType
  message: string
  duration?: number
}

interface ToastContextType {
  toast: {
    success: (message: string, duration?: number) => void
    error: (message: string, duration?: number) => void
    info: (message: string, duration?: number) => void
    warning: (message: string, duration?: number) => void
  }
  showToast: (type: ToastType, message: string, duration?: number) => void
  removeToast: (id: string) => void
}

const ToastContext = createContext<ToastContextType | undefined>(undefined)

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([])

  const removeToast = useCallback((id: string) => {
    setToasts(prev => prev.filter(t => t.id !== id))
  }, [])

  const showToast = useCallback((type: ToastType, message: string, duration = 4000) => {
    const id = `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
    setToasts(prev => [...prev, { id, type, message, duration }])

    if (duration > 0) {
      setTimeout(() => {
        removeToast(id)
      }, duration)
    }
  }, [removeToast])

  const toast = {
    success: (msg: string, dur?: number) => showToast('success', msg, dur),
    error: (msg: string, dur?: number) => showToast('error', msg, dur ?? 6000),
    info: (msg: string, dur?: number) => showToast('info', msg, dur),
    warning: (msg: string, dur?: number) => showToast('warning', msg, dur ?? 5000),
  }

  return (
    <ToastContext.Provider value={{ toast, showToast, removeToast }}>
      {children}
      {/* Toast Render Stack */}
      <div 
        aria-live="assertive"
        className="fixed top-4 right-4 z-[9999] flex flex-col gap-2.5 max-w-sm w-full pointer-events-none px-4 sm:px-0"
      >
        {toasts.map(t => {
          let bgClass = 'bg-gray-900/95 border-gray-700 text-gray-100'
          let Icon = Info
          let iconColor = 'text-blue-400'

          if (t.type === 'success') {
            bgClass = 'bg-emerald-950/90 border-emerald-700/80 text-emerald-100 shadow-emerald-950/50'
            Icon = CheckCircle2
            iconColor = 'text-emerald-400'
          } else if (t.type === 'error') {
            bgClass = 'bg-rose-950/90 border-rose-700/80 text-rose-100 shadow-rose-950/50'
            Icon = AlertCircle
            iconColor = 'text-rose-400'
          } else if (t.type === 'warning') {
            bgClass = 'bg-amber-950/90 border-amber-700/80 text-amber-100 shadow-amber-950/50'
            Icon = AlertTriangle
            iconColor = 'text-amber-400'
          } else if (t.type === 'info') {
            bgClass = 'bg-blue-950/90 border-blue-700/80 text-blue-100 shadow-blue-950/50'
            Icon = Info
            iconColor = 'text-blue-400'
          }

          return (
            <div
              key={t.id}
              className={`pointer-events-auto flex items-start gap-3 p-3.5 rounded-xl border backdrop-blur-md shadow-xl transition-all duration-300 animate-in fade-in slide-in-from-top-2 ${bgClass}`}
              role="alert"
            >
              <Icon className={`w-5 h-5 shrink-0 mt-0.5 ${iconColor}`} />
              <div className="flex-1 text-sm font-medium leading-snug break-words">
                {t.message}
              </div>
              <button
                type="button"
                onClick={() => removeToast(t.id)}
                className="text-gray-400 hover:text-white p-0.5 rounded transition-colors shrink-0"
                aria-label="Dismiss"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          )
        })}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast() {
  const context = useContext(ToastContext)
  if (!context) {
    throw new Error('useToast must be used within a ToastProvider')
  }
  return context
}
