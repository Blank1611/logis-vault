import React, { useEffect, useState } from 'react'
import { X, Maximize2, Minimize2 } from 'lucide-react'

export interface ModalProps {
  isOpen?: boolean
  onClose: () => void
  title: React.ReactNode
  subtitle?: React.ReactNode
  children: React.ReactNode
  footer?: React.ReactNode
  headerActions?: React.ReactNode
  maxWidth?: 'sm' | 'md' | 'lg' | 'xl' | '2xl' | '3xl' | '4xl' | '5xl' | 'full'
  resizable?: boolean
}

export const Modal: React.FC<ModalProps> = ({
  isOpen = true,
  onClose,
  title,
  subtitle,
  children,
  footer,
  headerActions,
  maxWidth = '2xl',
  resizable = false,
}) => {
  const [isMaximized, setIsMaximized] = useState(false)

  useEffect(() => {
    if (!isOpen) return

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, onClose])

  if (!isOpen) return null

  const maxWidthClasses = {
    sm: 'max-w-sm',
    md: 'max-w-md',
    lg: 'max-w-lg',
    xl: 'max-w-xl',
    '2xl': 'max-w-2xl',
    '3xl': 'max-w-3xl',
    '4xl': 'max-w-4xl',
    '5xl': 'max-w-5xl',
    full: 'max-w-[96vw]',
  }

  // Dimension classes when maximized vs standard/resizable
  const sizeClasses = isMaximized
    ? 'w-[96vw] h-[92vh] max-w-[96vw] max-h-[92vh]'
    : resizable
    ? `w-[min(90vw,1000px)] sm:resize overflow-hidden min-w-[min(88vw,520px)] min-h-[420px] max-w-[96vw] max-h-[92vh]`
    : `${maxWidthClasses[maxWidth]} w-full max-h-[90vh]`

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-3 sm:p-4 transition-all animate-fadeIn">
      <div 
        className={`bg-white dark:bg-gray-800 rounded-xl shadow-2xl ${sizeClasses} overflow-hidden flex flex-col border border-gray-100 dark:border-gray-700 transition-all duration-150`}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="p-5 sm:p-6 border-b border-gray-200 dark:border-gray-700 flex justify-between items-center flex-shrink-0">
          <div>
            <h2 className="text-xl sm:text-2xl font-bold text-gray-900 dark:text-white flex items-center gap-2">
              {title}
            </h2>
            {subtitle && (
              <p className="text-xs sm:text-sm text-gray-600 dark:text-gray-400 mt-1">
                {subtitle}
              </p>
            )}
          </div>
          <div className="flex items-center gap-1.5 sm:gap-2">
            {headerActions}

            {/* Maximize / Restore Toggle (Desktop) */}
            {resizable && (
              <button
                onClick={() => setIsMaximized(!isMaximized)}
                className="hidden sm:flex p-1.5 text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
                title={isMaximized ? 'Restore window size' : 'Maximize window'}
              >
                {isMaximized ? (
                  <Minimize2 className="w-4 h-4" />
                ) : (
                  <Maximize2 className="w-4 h-4" />
                )}
              </button>
            )}

            <button
              onClick={onClose}
              className="p-1.5 text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
              title="Close modal"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Body */}
        <div className="p-5 sm:p-6 flex-1 overflow-y-auto">
          {children}
        </div>

        {/* Footer */}
        {footer && (
          <div className="p-4 sm:p-6 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/80 flex-shrink-0">
            {footer}
          </div>
        )}
      </div>
    </div>
  )
}

