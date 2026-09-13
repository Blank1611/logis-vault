import React, { createContext, useContext, useState, useCallback, useRef } from 'react'
import { ConfirmModal } from '../components/ui/ConfirmModal'

export interface ConfirmOptions {
  title: string
  message: string | React.ReactNode
  confirmText?: string
  cancelText?: string
  isDestructive?: boolean
}

type ConfirmFunction = (options: ConfirmOptions) => Promise<boolean>

const ConfirmContext = createContext<ConfirmFunction | undefined>(undefined)

export function ConfirmProvider({ children }: { children: React.ReactNode }) {
  const [modalState, setModalState] = useState<{
    isOpen: boolean
    options: ConfirmOptions
  }>({
    isOpen: false,
    options: {
      title: '',
      message: '',
    },
  })

  const resolveRef = useRef<((value: boolean) => void) | null>(null)

  const confirm = useCallback<ConfirmFunction>((options) => {
    return new Promise<boolean>((resolve) => {
      resolveRef.current = resolve
      setModalState({
        isOpen: true,
        options,
      })
    })
  }, [])

  const handleConfirm = useCallback(() => {
    if (resolveRef.current) {
      resolveRef.current(true)
      resolveRef.current = null
    }
    setModalState(prev => ({ ...prev, isOpen: false }))
  }, [])

  const handleCancel = useCallback(() => {
    if (resolveRef.current) {
      resolveRef.current(false)
      resolveRef.current = null
    }
    setModalState(prev => ({ ...prev, isOpen: false }))
  }, [])

  return (
    <ConfirmContext.Provider value={confirm}>
      {children}
      <ConfirmModal
        isOpen={modalState.isOpen}
        title={modalState.options.title}
        message={modalState.options.message}
        confirmText={modalState.options.confirmText}
        cancelText={modalState.options.cancelText}
        isDestructive={modalState.options.isDestructive}
        onConfirm={handleConfirm}
        onCancel={handleCancel}
      />
    </ConfirmContext.Provider>
  )
}

export function useConfirm(): ConfirmFunction {
  const context = useContext(ConfirmContext)
  if (!context) {
    throw new Error('useConfirm must be used within a ConfirmProvider')
  }
  return context
}
