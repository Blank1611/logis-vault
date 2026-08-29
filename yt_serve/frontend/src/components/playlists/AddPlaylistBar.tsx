import React, { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { playlistsApi } from '../../services/api'
import { Button } from '../ui/Button'
import { Plus } from 'lucide-react'

export const AddPlaylistBar: React.FC = () => {
  const [url, setUrl] = useState('')
  const queryClient = useQueryClient()

  const addPlaylist = useMutation({
    mutationFn: (newUrl: string) => playlistsApi.create(newUrl),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['playlists'] })
      setUrl('')
    },
    onError: (err: any) => {
      const msg = err.response?.data?.detail || err.message
      alert(`Failed to add playlist:\n\n${msg}`)
    },
  })

  const handleAdd = (e: React.FormEvent) => {
    e.preventDefault()
    if (url.trim()) {
      addPlaylist.mutate(url.trim())
    }
  }

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6 mb-8 border border-gray-100 dark:border-gray-700">
      <h2 className="text-xl font-semibold mb-4 text-gray-900 dark:text-white">Add Playlist</h2>
      <form onSubmit={handleAdd} className="flex gap-2">
        <input
          type="text"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://www.youtube.com/playlist?list=... (YouTube supported)"
          className="flex-1 px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-500 dark:placeholder-gray-400 text-sm"
        />
        <Button
          type="submit"
          loading={addPlaylist.isPending}
          disabled={!url.trim()}
          icon={<Plus className="w-4 h-4" />}
          className="px-6"
        >
          Add
        </Button>
      </form>
    </div>
  )
}
