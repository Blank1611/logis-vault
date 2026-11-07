import React, { useState, useEffect } from 'react'
import { Modal } from '../ui/Modal'
import { Button } from '../ui/Button'
import { filesystemApi, type DirectoryItem } from '../../services/api'
import {
  Folder,
  FolderPlus,
  ArrowUp,
  RefreshCw,
  Check,
  ChevronRight,
  HardDrive,
  Loader2,
  AlertCircle
} from 'lucide-react'
import { useToast } from '../../context'

export interface DirectoryPickerModalProps {
  isOpen: boolean
  onClose: () => void
  initialPath?: string
  excludeManaged?: boolean
  onSelect: (selectedPath: string) => void
}

export const DirectoryPickerModal: React.FC<DirectoryPickerModalProps> = ({
  isOpen,
  onClose,
  initialPath,
  excludeManaged = false,
  onSelect,
}) => {
  const { toast } = useToast()
  const [currentPath, setCurrentPath] = useState<string>(initialPath || '')
  const [parentPath, setParentPath] = useState<string | null>(null)
  const [rootPath, setRootPath] = useState<string>('')
  const [subdirectories, setSubdirectories] = useState<DirectoryItem[]>([])
  const [isLoading, setIsLoading] = useState<boolean>(true)
  const [error, setError] = useState<string | null>(null)

  // New folder inline creation
  const [showNewFolderInput, setShowNewFolderInput] = useState<boolean>(false)
  const [newFolderName, setNewFolderName] = useState<string>('')
  const [isCreatingFolder, setIsCreatingFolder] = useState<boolean>(false)

  const fetchDirectory = async (targetPath?: string) => {
    setIsLoading(true)
    setError(null)
    try {
      const res = await filesystemApi.browse(targetPath, excludeManaged)
      setCurrentPath(res.data.current_path)
      setParentPath(res.data.parent_path)
      setRootPath(res.data.root_path)
      setSubdirectories(res.data.subdirectories)
    } catch (err: any) {
      const msg = err.response?.data?.detail || err.message || 'Failed to read directory'
      setError(msg)
      toast.error(msg)
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    if (isOpen) {
      fetchDirectory(initialPath)
      setShowNewFolderInput(false)
      setNewFolderName('')
    }
  }, [isOpen, initialPath, excludeManaged])

  const handleNavigate = (path: string) => {
    setShowNewFolderInput(false)
    setNewFolderName('')
    fetchDirectory(path)
  }

  const handleCreateFolder = async () => {
    const trimmed = newFolderName.trim()
    if (!trimmed) return

    setIsCreatingFolder(true)
    try {
      const res = await filesystemApi.createDirectory({
        parent_path: currentPath,
        directory_name: trimmed,
      })
      toast.success(res.data.message || 'Folder created')
      setShowNewFolderInput(false)
      setNewFolderName('')
      // Refresh current directory
      await fetchDirectory(currentPath)
    } catch (err: any) {
      const msg = err.response?.data?.detail || err.message || 'Failed to create folder'
      toast.error(msg)
    } finally {
      setIsCreatingFolder(false)
    }
  }

  const handleConfirmSelect = () => {
    onSelect(currentPath)
    onClose()
  }

  // Generate clickable breadcrumbs relative to root
  const renderBreadcrumbs = () => {
    if (!currentPath) return null
    const parts = currentPath.split('/').filter(Boolean)

    return (
      <div className="flex items-center flex-wrap gap-1 text-xs text-gray-400 font-mono bg-gray-950/60 p-2 rounded border border-gray-800">
        <button
          type="button"
          onClick={() => handleNavigate(rootPath)}
          className="flex items-center gap-1 text-blue-400 hover:text-blue-300 transition-colors font-medium"
          title={`Root Mount: ${rootPath}`}
        >
          <HardDrive className="w-3.5 h-3.5" />
          <span>root</span>
        </button>

        {parts.map((part, idx) => {
          const pathToPart = '/' + parts.slice(0, idx + 1).join('/')
          const isLast = idx === parts.length - 1
          return (
            <React.Fragment key={pathToPart}>
              <ChevronRight className="w-3.5 h-3.5 text-gray-600 flex-shrink-0" />
              {isLast ? (
                <span className="text-gray-200 font-semibold">{part}</span>
              ) : (
                <button
                  type="button"
                  onClick={() => handleNavigate(pathToPart)}
                  className="text-gray-400 hover:text-gray-200 transition-colors"
                >
                  {part}
                </button>
              )}
            </React.Fragment>
          )
        })}
      </div>
    )
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={
        <div className="flex items-center gap-2">
          <Folder className="w-5 h-5 text-amber-500" />
          <span>Server Directory Browser</span>
        </div>
      }
      subtitle="Select a container-mounted destination folder for ad-hoc media"
      maxWidth="2xl"
      footer={
        <div className="flex items-center justify-between w-full">
          <div className="text-xs text-gray-400 truncate max-w-sm">
            <span className="font-semibold text-gray-300">Target:</span>{' '}
            <span className="font-mono text-blue-400">{currentPath || '...'}</span>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="secondary" size="sm" onClick={onClose}>
              Cancel
            </Button>
            <Button
              variant="primary"
              size="sm"
              onClick={handleConfirmSelect}
              disabled={isLoading || !currentPath}
              icon={<Check className="w-4 h-4" />}
            >
              Select This Folder
            </Button>
          </div>
        </div>
      }
    >
      <div className="space-y-3">
        {/* Breadcrumb Path Bar */}
        {renderBreadcrumbs()}

        {/* Toolbar: Up, Refresh, New Folder */}
        <div className="flex items-center justify-between gap-2 pt-1">
          <div className="flex items-center gap-2">
            <Button
              variant="secondary"
              size="sm"
              disabled={!parentPath || isLoading}
              onClick={() => parentPath && handleNavigate(parentPath)}
              icon={<ArrowUp className="w-3.5 h-3.5" />}
              title="Go up to parent directory"
            >
              Up
            </Button>
            <Button
              variant="ghost"
              size="sm"
              disabled={isLoading}
              onClick={() => fetchDirectory(currentPath)}
              icon={<RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />}
              title="Refresh directory contents"
            />
          </div>

          {!showNewFolderInput && (
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setShowNewFolderInput(true)}
              icon={<FolderPlus className="w-3.5 h-3.5 text-amber-400" />}
            >
              New Folder
            </Button>
          )}
        </div>

        {/* Inline New Folder Form */}
        {showNewFolderInput && (
          <div className="flex items-center gap-2 p-2.5 bg-gray-900/80 border border-gray-700 rounded-md">
            <FolderPlus className="w-4 h-4 text-amber-400 flex-shrink-0" />
            <input
              type="text"
              value={newFolderName}
              onChange={(e) => setNewFolderName(e.target.value)}
              placeholder="Enter folder name..."
              className="flex-1 bg-gray-950 border border-gray-700 rounded px-2.5 py-1 text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:border-blue-500"
              autoFocus
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleCreateFolder()
                if (e.key === 'Escape') setShowNewFolderInput(false)
              }}
            />
            <Button
              variant="primary"
              size="sm"
              onClick={handleCreateFolder}
              disabled={!newFolderName.trim() || isCreatingFolder}
              icon={isCreatingFolder ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : undefined}
            >
              Create
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setShowNewFolderInput(false)
                setNewFolderName('')
              }}
            >
              Cancel
            </Button>
          </div>
        )}

        {/* Directory Listing Area */}
        <div className="bg-gray-950/70 border border-gray-800 rounded-lg min-h-[260px] max-h-[340px] overflow-y-auto p-2">
          {isLoading ? (
            <div className="flex flex-col items-center justify-center py-12 text-gray-400 space-y-2">
              <Loader2 className="w-7 h-7 animate-spin text-blue-500" />
              <p className="text-xs">Reading server directory...</p>
            </div>
          ) : error ? (
            <div className="flex flex-col items-center justify-center py-12 text-red-400 space-y-2 px-4 text-center">
              <AlertCircle className="w-7 h-7" />
              <p className="text-sm font-medium">{error}</p>
              <Button variant="secondary" size="sm" onClick={() => fetchDirectory(rootPath)}>
                Return to Root
              </Button>
            </div>
          ) : subdirectories.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-gray-500 space-y-1">
              <Folder className="w-8 h-8 text-gray-600 mb-1" />
              <p className="text-xs">No subdirectories in this folder</p>
              <p className="text-[11px] text-gray-600">Click &quot;Select This Folder&quot; below to use it, or create a subfolder.</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
              {subdirectories.map((dir) => (
                <button
                  key={dir.path}
                  type="button"
                  onClick={() => handleNavigate(dir.path)}
                  className="flex items-center justify-between p-2 rounded-md bg-gray-900/60 hover:bg-gray-800/80 border border-gray-800/80 hover:border-gray-700 transition-colors text-left group"
                >
                  <div className="flex items-center gap-2.5 truncate">
                    <Folder className="w-4 h-4 text-amber-400 flex-shrink-0 group-hover:text-amber-300" />
                    <span className="text-sm text-gray-200 group-hover:text-white truncate font-medium">
                      {dir.name}
                    </span>
                  </div>
                  {dir.has_children && (
                    <ChevronRight className="w-3.5 h-3.5 text-gray-600 group-hover:text-gray-400 flex-shrink-0 ml-1" />
                  )}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </Modal>
  )
}
