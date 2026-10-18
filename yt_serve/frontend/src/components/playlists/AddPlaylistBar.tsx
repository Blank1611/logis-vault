import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { playlistsApi, profilesApi } from '../../services/api'
import { useToast } from '../../context/ToastContext'
import { Button } from '../ui/Button'
import { Plus } from 'lucide-react'

export const AddPlaylistBar: React.FC = () => {
  const [url, setUrl] = useState('')
  const [selectedProfile, setSelectedProfile] = useState('standard_1080p')
  const queryClient = useQueryClient()
  const { toast } = useToast()

  const { data: profiles = [] } = useQuery({
    queryKey: ['profiles'],
    queryFn: async () => {
      const res = await profilesApi.getAll()
      return res.data
    },
  })

  const addPlaylist = useMutation({
    mutationFn: (data: { url: string; quality_profile_id: string }) => playlistsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['playlists'] })
      setUrl('')
      toast.success('Playlist added successfully!')
    },
    onError: (err: any) => {
      const msg = err.response?.data?.detail || err.message
      toast.error(`Failed to add playlist: ${msg}`)
    },
  })

  const handleAdd = (e: React.FormEvent) => {
    e.preventDefault()
    if (url.trim()) {
      addPlaylist.mutate({ url: url.trim(), quality_profile_id: selectedProfile })
    }
  }

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6 mb-8 border border-gray-100 dark:border-gray-700">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-semibold text-gray-900 dark:text-white">Add Playlist</h2>
      </div>
      <form onSubmit={handleAdd} className="flex flex-col sm:flex-row gap-3">
        <input
          type="text"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://www.youtube.com/playlist?list=... (YouTube supported)"
          className="flex-1 px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-500 dark:placeholder-gray-400 text-sm"
        />
        <div className="flex items-center gap-2">
          <select
            value={selectedProfile}
            onChange={(e) => setSelectedProfile(e.target.value)}
            className="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-xs bg-gray-50 dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            title="Quality Profile"
          >
            {profiles.length > 0 ? (
              profiles.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} ({p.is_audio_only ? 'Audio Only' : `${p.max_resolution}p`})
                </option>
              ))
            ) : (
              <>
                <option value="standard_1080p">Standard HD (1080p)</option>
                <option value="standard_720p">Standard HD (720p)</option>
                <option value="ultra_4k">Ultra 4K (2160p)</option>
                <option value="fast_mixtape_360p">Fast 360p (Challenge-Free)</option>
                <option value="audio_only">Audio Only Vault</option>
              </>
            )}
          </select>
          <Button
            type="submit"
            loading={addPlaylist.isPending}
            disabled={!url.trim()}
            icon={<Plus className="w-4 h-4" />}
            className="px-6 shrink-0"
          >
            Add
          </Button>
        </div>
      </form>
    </div>
  )
}
