import React from 'react'
import { Modal } from '../ui/Modal'
import { Button } from '../ui/Button'
import { adhocApi, type AdhocMediaItem } from '../../services/api'
import { Download, Film, Music, Folder } from 'lucide-react'

export interface MediaPreviewModalProps {
  isOpen: boolean
  onClose: () => void
  item: AdhocMediaItem | null
}

export const MediaPreviewModal: React.FC<MediaPreviewModalProps> = ({
  isOpen,
  onClose,
  item,
}) => {
  if (!item) return null

  const targetPath = (item.media_type === 'audio' && item.audio_filepath)
    ? item.audio_filepath
    : (item.filepath || item.audio_filepath || '')
  const streamUrl = adhocApi.getStreamUrl(targetPath)
  const isVideo = item.media_type === 'video'

  const formatBytes = (bytes: number) => {
    if (!bytes) return '0 B'
    const k = 1024
    const sizes = ['B', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={
        <div className="flex items-center gap-2 truncate max-w-xl">
          {isVideo ? (
            <Film className="w-5 h-5 text-blue-400 flex-shrink-0" />
          ) : (
            <Music className="w-5 h-5 text-purple-400 flex-shrink-0" />
          )}
          <span className="truncate">{item.title}</span>
        </div>
      }
      subtitle={
        <div className="flex items-center gap-3 text-xs text-gray-400">
          <span className="flex items-center gap-1">
            <Folder className="w-3.5 h-3.5 text-amber-400" />
            {item.directory_display}
          </span>
          {item.resolution && <span>• {item.resolution}</span>}
          {item.audio_codec && <span>• {item.audio_codec.toUpperCase()}</span>}
          <span>• {formatBytes(item.size_bytes)}</span>
        </div>
      }
      maxWidth="4xl"
      footer={
        <div className="flex items-center justify-between w-full">
          <div className="text-xs text-gray-400 truncate max-w-md font-mono">
            {item.filename}
          </div>
          <div className="flex items-center gap-2">
            <a
              href={streamUrl}
              download={item.filename}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium bg-gray-800 hover:bg-gray-700 text-gray-200 hover:text-white transition-colors"
            >
              <Download className="w-3.5 h-3.5" />
              Download File
            </a>
            <Button variant="secondary" size="sm" onClick={onClose}>
              Close
            </Button>
          </div>
        </div>
      }
    >
      <div className="bg-black rounded-lg overflow-hidden flex flex-col items-center justify-center min-h-[300px] max-h-[65vh]">
        {isVideo ? (
          <video
            controls
            autoPlay
            playsInline
            src={streamUrl}
            className="w-full h-full max-h-[62vh] object-contain"
          >
            Your browser does not support HTML5 video streaming.
          </video>
        ) : (
          <div className="p-8 w-full flex flex-col items-center justify-center space-y-6">
            <div className="w-24 h-24 rounded-full bg-purple-950/60 border border-purple-800 flex items-center justify-center shadow-lg">
              <Music className="w-12 h-12 text-purple-400 animate-pulse" />
            </div>
            <div className="text-center space-y-1">
              <h3 className="text-base font-medium text-gray-200">{item.title}</h3>
              <p className="text-xs text-gray-400">{item.uploader} • {(item.format || 'audio').toUpperCase()}</p>
            </div>
            <audio
              controls
              autoPlay
              src={streamUrl}
              className="w-full max-w-md"
            >
              Your browser does not support HTML5 audio playback.
            </audio>
          </div>
        )}
      </div>
    </Modal>
  )
}
