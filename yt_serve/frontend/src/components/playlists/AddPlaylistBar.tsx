import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { playlistsApi, profilesApi } from '../../services/api'
import { useToast } from '../../context/ToastContext'
import { Plus } from 'lucide-react'
import { formatProfileOptionLabel } from '../../services/types'

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
    <div className="glass-panel rounded-2xl p-6 mb-8 border border-white/10 shadow-2xl">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-cyan-400 to-blue-600 flex items-center justify-center shadow-md">
            <Plus className="w-4 h-4 text-white" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-white tracking-tight">Add Playlist</h2>
            <p className="text-xs text-slate-400">Queue a playlist to archive, synchronize, or extract audio</p>
          </div>
        </div>
      </div>
      <form onSubmit={handleAdd} className="flex flex-col sm:flex-row gap-3">
        <input
          type="text"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://www.youtube.com/playlist?list=... (YouTube supported)"
          className="flex-1 glass-input px-4 py-2.5 rounded-xl text-sm placeholder-slate-400 focus:outline-none"
        />
        <div className="flex items-center gap-2">
          <select
            value={selectedProfile}
            onChange={(e) => setSelectedProfile(e.target.value)}
            className="glass-select px-3 py-2.5 rounded-xl text-xs text-slate-200 cursor-pointer focus:outline-none shadow-sm"
            title="Quality Profile"
          >
            {profiles.length > 0 ? (
              profiles.map((p) => (
                <option key={p.id} value={p.id} className="bg-slate-900 text-white">
                  {formatProfileOptionLabel(p)}
                </option>
              ))
            ) : (
              <>
                <option value="standard_1080p" className="bg-slate-900 text-white">Standard HD (1080p • Direct Copy)</option>
                <option value="standard_720p" className="bg-slate-900 text-white">Standard HD (720p • Direct Copy)</option>
                <option value="ultra_4k" className="bg-slate-900 text-white">Ultra 4K (2160p • Direct Copy)</option>
                <option value="fast_mixtape_360p" className="bg-slate-900 text-white">Fast 360p (360p • Direct Copy)</option>
                <option value="audio_only" className="bg-slate-900 text-white">Audio Only Vault (Audio Only • Direct Copy)</option>
              </>
            )}
          </select>
          <button
            type="submit"
            disabled={addPlaylist.isPending || !url.trim()}
            className="glass-btn-cyan px-6 py-2.5 rounded-xl text-xs font-bold shrink-0 flex items-center gap-1.5 disabled:opacity-50 transition-all cursor-pointer"
          >
            <Plus className="w-4 h-4" />
            <span>Add</span>
          </button>
        </div>
      </form>
    </div>
  )
}
