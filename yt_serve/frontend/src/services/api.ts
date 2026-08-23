import axios from 'axios'
import type { Playlist, Job, LogEntry } from './types'

const api = axios.create({
  baseURL: '/api',
})

export const playlistsApi = {
  list: () => api.get<Playlist[]>('/playlists'),
  get: (id: number) => api.get<Playlist>(`/playlists/${id}`),
  create: (url: string) => api.post<Playlist>('/playlists', { url }),
  update: (id: number, data: Partial<Playlist>) => api.put<Playlist>(`/playlists/${id}`, data),
  delete: (id: number) => api.delete(`/playlists/${id}`),
  refresh: (id: number) => api.post<Playlist>(`/playlists/${id}/refresh`),
  getVideoInfo: (id: number) => api.get<Record<string, { title: string; duration?: number; uploader?: string }>>(`/playlists/${id}/video-info`),
  openFolder: (id: number) => api.post<{ message: string; path: string }>(`/playlists/${id}/open-folder`),
}

export const jobsApi = {
  list: (playlistId?: number) => 
    api.get<Job[]>('/downloads/jobs', { params: { playlist_id: playlistId } }),
  get: (id: number) => api.get<Job>(`/downloads/jobs/${id}`),
  create: (playlistId: number, jobType: 'download' | 'extract' | 'both') =>
    api.post<Job>('/downloads/jobs', { playlist_id: playlistId, job_type: jobType }),
  cancel: (id: number) => api.post(`/downloads/jobs/${id}/cancel`),
  logs: (id: number, lines?: number) =>
    api.get<LogEntry[]>(`/downloads/jobs/${id}/logs`, { params: { lines } }),
  getDownloadLogUrl: (id: number) => `/api/downloads/jobs/${id}/download-log`,
  
  // Interrupted jobs handling
  getInterrupted: () => api.get<{
    jobs: Array<{
      id: number
      job_type: string
      playlist_id: number
      playlist_title: string
      created_at: string
    }>
    count: number
  }>('/downloads/interrupted-jobs'),
  
  handleInterrupted: (action: 'resume_all' | 'cancel_all' | 'individual', jobDecisions?: Record<string, 'resume' | 'cancel'>) =>
    api.post<{
      message: string
      processed: number
      resumed: number
      cancelled: number
    }>('/downloads/handle-interrupted-jobs', {
      action,
      job_decisions: jobDecisions,
    }),

  testIntegrity: (params: { file_path?: string; playlist_id?: number; video_id?: string }) =>
    api.post<{
      file_path: string
      valid: boolean
      has_video: boolean
      has_audio: boolean
      duration?: number
      error?: string
      details: Record<string, any>
    }>('/downloads/test-integrity', params),
}

export interface Config {
  base_download_path: string
  temp_download_path?: string | null
  audio_extract_mode: string
  max_extraction_workers: number
  max_concurrent_downloads: number
  batch_size: number
  sleep_interval_min?: number
  sleep_interval_max?: number
  concurrent_fragments?: number
  enable_daily_auto_refresh?: boolean
  daily_refresh_interval_hours?: number
  enable_git_metadata_sync?: boolean
  git_remote_url?: string | null
  git_auth_token?: string | null
  git_branch?: string
  cookies_file: string | null
  use_browser_cookies: boolean
  browser_name: string
  enable_stream_integrity_check?: boolean
  flaresolverr_url?: string | null
  needs_setup: boolean
}

export interface CookieStatus {
  is_installed: boolean
  status: 'valid' | 'expiring_soon' | 'expired' | 'invalid' | 'not_installed'
  status_message: string
  file_path?: string | null
  file_size_bytes?: number | null
  last_modified?: string | null
  earliest_expiration?: string | null
  days_remaining?: number | null
  auth_cookies_found: string[]
}

export const configApi = {
  get: () => api.get<Config>('/config'),
  update: (config: Partial<Config>) => api.put<Config>('/config', config),
  getYtdlpVersion: () => api.get<{ version: string }>('/config/ytdlp-version'),
  updateYtdlp: () => api.post<{
    success: boolean
    message: string
    old_version: string
    new_version: string
    output: string
  }>('/config/update-ytdlp'),
  testFlareSolverr: (url?: string) => api.post<{
    success: boolean
    message: string
    version?: string
    response_time_ms?: number
  }>('/config/test-flaresolverr', { url }),
  testGitSync: () => api.post<{
    success: boolean
    message: string
  }>('/config/test-git-sync'),
  getCookiesStatus: () => api.get<CookieStatus>('/config/cookies-status'),
  uploadCookies: (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post<CookieStatus>('/config/upload-cookies', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  },
  deleteCookies: () => api.delete<CookieStatus>('/config/cookies'),
}

export default api
