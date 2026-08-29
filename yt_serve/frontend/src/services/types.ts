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
}

export interface Job {
  id: number
  playlist_id: number
  job_type: 'download' | 'extract' | 'both'
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
