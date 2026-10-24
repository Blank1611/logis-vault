export interface QualityProfile {
  id: string
  name: string
  description?: string
  max_resolution: number
  audio_format: string
  cipher_strategy: string
  is_audio_only: boolean
  is_builtin: boolean
  created_at?: string
  updated_at?: string
}

export function formatProfileOptionLabel(p: QualityProfile): string {
  const audio = (p.audio_format || 'copy').toLowerCase()
  let audioLabel = 'Direct Copy'
  if (audio === 'opus') audioLabel = 'Opus'
  else if (audio === 'mp3_best' || audio === 'mp3_320') audioLabel = 'MP3 320k'
  else if (audio === 'mp3_high' || audio === 'mp3_192') audioLabel = 'MP3 192k'
  else if (audio === 'flac') audioLabel = 'FLAC'
  else if (audio === 'm4a') audioLabel = 'M4A'
  else if (audio !== 'copy') audioLabel = audio.toUpperCase()

  if (p.is_audio_only || p.max_resolution <= 0) {
    return `${p.name} (Audio Only • ${audioLabel})`
  }
  return `${p.name} (${p.max_resolution}p • ${audioLabel})`
}

export interface Playlist {
  id: number
  url: string
  title: string
  local_count: number
  playlist_count: number
  unavailable_count: number
  last_download: string | null
  last_extract: string | null
  excluded_ids: string[]
  quality_profile_id?: string
}

export interface AdhocResolutionOption {
  height: number
  label: string
  fps?: number
  vcodec?: string
  is_direct?: boolean
  badge?: string
  badge_tooltip?: string
  filesize?: number
}

export interface DiskVersion {
  resolution: string
  filename: string
  filepath: string
  size_bytes: number
}

export interface PlaylistTrack {
  video_id: string
  title: string
  artist?: string
  duration?: number
  primary_filepath?: string
  primary_audio_filepath?: string
  primary_resolution?: string
  downloaded_resolutions: string[]
  downloaded_fps?: number
  downloaded_audio_codec?: string
  downloaded_audio_bitrate?: string
  available_resolutions: AdhocResolutionOption[]
  highest_available_resolution?: string
  resolutions_last_checked?: string | null
  video_size_bytes: number
  audio_size_bytes: number
  is_hardlinked: boolean
  disk_versions: DiskVersion[]
}

export interface Job {
  id: number
  playlist_id: number
  job_type: 'download' | 'extract' | 'both' | 'adhoc_both' | 'adhoc_video_only' | 'adhoc_audio_only' | string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
  progress: number
  total_items: number
  completed_items: number
  failed_items: number
  
  // Separate download progress
  download_status: string | null
  download_total: number
  download_completed: number
  download_failed: number
  download_batch_info: string | null
  
  // Separate extraction progress
  extract_status: string | null
  extract_total: number
  extract_completed: number
  extract_failed: number
  
  // In-flight active track telemetry (Dual-Tier progress)
  current_video_title?: string | null
  current_video_id?: string | null
  current_video_bytes_downloaded?: number | null
  current_video_bytes_total?: number | null
  current_video_speed?: number | null
  current_video_eta?: number | null
  
  created_at: string
  started_at: string | null
  completed_at: string | null
  error: string | null
}

export interface LogEntry {
  message: string
}
