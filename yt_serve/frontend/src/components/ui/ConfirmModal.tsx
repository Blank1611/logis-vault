import React from 'react'
import { AlertTriangle, HelpCircle, X } from 'lucide-react'
import { Button } from './Button'

export interface ConfirmModalProps {
  isOpen: boolean
  title: string
  message: string | React.ReactNode
  confirmText?: string
  cancelText?: string
  isDestructive?: boolean
  onConfirm: () => void
  onCancel: () => void
}

export function ConfirmModal({
  isOpen,
  title,
  message,
  confirmText = 'Confirm',
  cancelText = 'Cancel',
  isDestructive = false,
  onConfirm,
  onCancel,
}: ConfirmModalProps) {
  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-[9998] flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-in fade-in duration-200">
      <div 
        className="w-full max-w-md bg-gray-900 border border-gray-800 rounded-2xl shadow-2xl overflow-hidden animate-in zoom-in-95 duration-200"
        role="dialog"
        aria-modal="true"
      >
        <div className="p-6">
          <div className="flex items-start gap-4">
            <div className={`p-3 rounded-xl shrink-0 ${
              isDestructive 
                ? 'bg-rose-950/60 text-rose-400 border border-rose-800/40' 
                : 'bg-blue-950/60 text-blue-400 border border-blue-800/40'
            }`}>
              {isDestructive ? (
                <AlertTriangle className="w-6 h-6" />
              ) : (
                <HelpCircle className="w-6 h-6" />
              )}
            </div>
            <div className="flex-1 min-w-0">
              <h3 className="text-lg font-bold text-white mb-2 leading-tight">
                {title}
              </h3>
              <div className="text-sm text-gray-300 leading-relaxed whitespace-pre-line">
                {message}
              </div>
            </div>
            <button
              type="button"
              onClick={onCancel}
              className="text-gray-500 hover:text-gray-300 p-1 rounded-lg transition-colors -mr-1 -mt-1"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        <div className="px-6 py-4 bg-gray-950/60 border-t border-gray-800/80 flex justify-end gap-3">
          <Button
            type="button"
            variant="secondary"
            onClick={onCancel}
            className="bg-gray-800 hover:bg-gray-700 text-gray-200 border border-gray-700"
          >
            {cancelText}
          </Button>
          <Button
            type="button"
            variant={isDestructive ? 'danger' : 'primary'}
            onClick={onConfirm}
            className={isDestructive ? 'bg-rose-600 hover:bg-rose-500 text-white' : 'bg-blue-600 hover:bg-blue-500 text-white'}
          >
            {confirmText}
          </Button>
        </div>
      </div>
    </div>
  )
}
