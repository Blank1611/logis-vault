import axios from 'axios'
import type { Playlist, Job, LogEntry, QualityProfile, PlaylistTrack } from './types'

const api = axios.create({
  baseURL: '/api',
})

export const playlistsApi = {
  list: () => api.get<Playlist[]>('/playlists'),
  get: (id: number) => api.get<Playlist>(`/playlists/${id}`),
  create: (data: { url: string; title?: string; quality_profile_id?: string } | string) =>
    api.post<Playlist>('/playlists', typeof data === 'string' ? { url: data } : data),
  update: (id: number, data: Partial<Playlist>) => api.put<Playlist>(`/playlists/${id}`, data),
  delete: (id: number) => api.delete(`/playlists/${id}`),
  refresh: (id: number) => api.post<Playlist>(`/playlists/${id}/refresh`),
  getVideoInfo: (id: number) => api.get<Record<string, { title: string; duration?: number; uploader?: string }>>(`/playlists/${id}/video-info`),
  openFolder: (id: number) => api.post<{ message: string; path: string }>(`/playlists/${id}/open-folder`),
  getTracks: (id: number) => api.get<PlaylistTrack[]>(`/playlists/${id}/tracks`),
  refreshResolutions: (id: number) => api.post<{ message: string; playlist_id: number }>(`/playlists/${id}/tracks/refresh-resolutions`),
  upgradeTrack: (playlistId: number, videoId: string, data: { target_resolution: number; delete_older?: boolean }) =>
    api.post<{ status: string; video_id: string; resolution: string; primary_filepath: string; downloaded_resolutions: string[] }>(`/playlists/${playlistId}/tracks/${videoId}/upgrade`, data),
  upgradeAudio: (playlistId: number, videoId: string, data: { audio_format: string }) =>
    api.post<{ status: string; audio_filepath: string; codec?: string; bitrate?: string }>(`/playlists/${playlistId}/tracks/${videoId}/upgrade-audio`, data),
  setPrimaryVersion: (playlistId: number, videoId: string, resolution: string) =>
    api.post<{ status: string; primary_filepath: string; primary_resolution: string }>(`/playlists/${playlistId}/tracks/${videoId}/set-primary`, { resolution }),
  deleteTrackVersion: (playlistId: number, videoId: string, resolution: string) =>
    api.delete<{ status: string; deleted: boolean; remaining_resolutions: string[]; primary_filepath: string }>(`/playlists/${playlistId}/tracks/${videoId}/versions/${resolution}`),
  extractTrackAudio: (playlistId: number, videoId: string, format: string = 'mp3') =>
    api.post<{ status: string; audio_filepath: string; format: string; codec?: string; bitrate?: string }>(`/playlists/${playlistId}/tracks/${videoId}/extract-audio`, null, { params: { format } }),
  getExportAudioZipUrl: (playlistId: number, format: string = 'mp3') =>
    `/api/playlists/${playlistId}/export-audio/zip?format=${encodeURIComponent(format)}`,
}

export const profilesApi = {
  getAll: () => api.get<QualityProfile[]>('/profiles'),
  getById: (id: string) => api.get<QualityProfile>(`/profiles/${id}`),
  create: (data: Partial<QualityProfile>) => api.post<QualityProfile>('/profiles', data),
  update: (id: string, data: Partial<QualityProfile>) => api.put<QualityProfile>(`/profiles/${id}`, data),
  delete: (id: string) => api.delete(`/profiles/${id}`),
}

export const jobsApi = {
  list: (playlistId?: number) => 
    api.get<Job[]>('/downloads/jobs', { params: { playlist_id: playlistId } }),
  get: (id: number) => api.get<Job>(`/downloads/jobs/${id}`),
  create: (playlistId: number, jobType: 'download' | 'extract' | 'both', targetFormat?: string) =>
    api.post<Job>('/downloads/jobs', { playlist_id: playlistId, job_type: jobType, target_format: targetFormat }),
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

export interface ServerLogEntry {
  id: string
  timestamp: string
  level: string
  logger: string
  message: string
  source?: string
  job_id?: number | null
  exception?: string | null
}

export const logsApi = {
  getRecent: (params?: { limit?: number; level?: string; source?: string; job_id?: number; search?: string }) =>
    api.get<ServerLogEntry[]>('/logs/recent', { params }),
  clear: () => api.delete<{ status: string; message: string }>('/logs/clear'),
  getLogFileUrl: () => '/api/logs/file',
}

export interface IndexedTrack {
  video_id: string
  title: string
  artist?: string | null
  duration?: number | null
  primary_filepath: string
  primary_audio_filepath?: string | null
  playlists: number[]
  is_hardlinked: boolean
  created_at: string
  updated_at: string
}

export interface PendingMoveItem {
  video_id: string
  title: string
  from_playlist_id: number
  from_playlist_title: string
  to_playlist_id: number
  to_playlist_title: string
  type: string
  suggested_action: string
}

export interface MovedHistoryItem {
  id: number
  video_id: string
  title: string
  from_playlist_id: number
  from_playlist_title: string
  to_playlist_id: number
  to_playlist_title: string
  status: string
  moved_at: string
}

export const tracksApi = {
  getIndex: (params?: { search?: string; limit?: number; offset?: number }) =>
    api.get<{ total: number; items: IndexedTrack[] }>('/tracks/index', { params }),
  getPendingMoves: () =>
    api.get<{ count: number; pending: PendingMoveItem[] }>('/tracks/reorganize/pending'),
  applyMoves: (moves: Array<{ video_id: string; from_playlist_id: number; to_playlist_id: number; action?: string }>) =>
    api.post<{ processed: number; results: any[] }>('/tracks/reorganize/apply', { moves }),
  getMoveHistory: (params?: { limit?: number; offset?: number }) =>
    api.get<{ total: number; items: MovedHistoryItem[] }>('/tracks/reorganize/history', { params }),
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
  daily_refresh_time?: string
  daily_refresh_timezone?: string
  daily_refresh_mode?: 'scheduled' | 'interval'
  daily_refresh_interval_minutes?: number
  enable_git_metadata_sync?: boolean
  enable_git_remote_push?: boolean
  git_remote_url?: string | null
  git_auth_token?: string | null
  git_branch?: string
  git_user_name?: string
  git_user_email?: string
  cookies_file: string | null
  use_browser_cookies: boolean
  browser_name: string
  cookies_auth_mode?: 'cookies_txt' | 'browser' | 'none'
  enable_stream_integrity_check?: boolean
  flaresolverr_url?: string | null
  enable_auto_discovery?: boolean
  auto_discovery_interval_minutes?: number
  setup_completed?: boolean
  needs_setup: boolean
  adhoc_download_path?: string | null
  use_custom_adhoc_path?: boolean
  effective_adhoc_download_path?: string
  excluded_dirs?: string
  rename_folder_on_link?: boolean
}

export interface UnmanagedFolder {
  folder_name: string
  folder_path: string
  video_count: number
  audio_count: number
  total_files: number
}

export interface SchedulerStatus {
  is_scanning: boolean
  current_playlist?: string | null
  completed_count: number
  total_count: number
  last_scan_at?: string | null
  next_scan_at?: string | null
  last_scan_summary?: string | null
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
  get: () => api.get<Config>('/config/'),
  update: (config: Partial<Config>) => api.put<Config>('/config/', config),
  getSchedulerStatus: () => api.get<SchedulerStatus>('/config/scheduler-status'),
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
  testGitSync: (payload?: { git_remote_url?: string; git_auth_token?: string; git_branch?: string }) =>
    api.post<{
      success: boolean
      message: string
    }>('/config/test-git-sync', payload),
  getCookiesStatus: () => api.get<CookieStatus>('/config/cookies-status'),
  uploadCookies: (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post<CookieStatus>('/config/upload-cookies', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  },
  deleteCookies: () => api.delete<CookieStatus>('/config/cookies'),
  getUnmanagedFolders: () => api.get<{
    base_path: string
    unmanaged_folders_count: number
    unmanaged_folders: UnmanagedFolder[]
    excluded_folders_count?: number
    excluded_folders?: ExcludedFolderItem[]
  }>('/config/unmanaged-folders'),
  batchLinkUnmanagedFolders: (
    items: Array<{ folder_path?: string; folder_name?: string; playlist_url: string; rename_folder?: boolean }>,
    global_rename?: boolean
  ) =>
    api.post<{
      success: boolean
      linked_count: number
      failed_count: number
      results: Array<{ folder_path: string; folder_name?: string; success: boolean; playlist_id?: number; title?: string; error?: string }>
    }>('/config/batch-link-unmanaged-folders', { items, global_rename }),
  batchExcludeFolders: (folder_names: string[]) =>
    api.post<{ success: boolean; excluded_folders: string[] }>('/config/batch-exclude-folders', { folder_names }),
  restoreExcludedFolder: (folder_name: string) =>
    api.post<{ success: boolean; restored_folder: string }>('/config/restore-excluded-folder', { folder_name }),
}

export interface ExcludedFolderItem {
  folder_name: string
  reason?: string
  created_at?: string
}

export interface DiscoveredPlaylistItem {
  folder_name: string
  folder_path: string
  title: string
  url: string
  video_count: number
  audio_count: number
  archived_count: number
  total_online_count: number
}

export interface DiscoveredLibraryPreview {
  base_path: string
  exists: boolean
  total_folders_scanned: number
  discovered_playlists_count: number
  unmanaged_folders_count?: number
  total_estimated_tracks: number
  discovered_playlists: DiscoveredPlaylistItem[]
  unmanaged_folders?: UnmanagedFolder[]
}

export interface OnboardingResult {
  status: string
  playlists_imported: number
  playlists_skipped: number
  tracks_indexed: number
  total_playlists: number
  total_tracks: number
}

export interface DuplicateFileInfo {
  video_id: string
  filename: string
  filepath: string
  file_size: number
  playlist_folder: string
  extension: string
  is_audio: boolean
}

export interface DuplicateGroup {
  video_id: string
  title: string
  media_type: string
  master_file: DuplicateFileInfo
  redundant_copies: DuplicateFileInfo[]
  already_hardlinked_count: number
  reclaimable_bytes: number
  formatted_reclaimable_space: string
  playlists: string[]
}

export interface DeduplicationScanResult {
  status: string
  base_path: string
  total_scanned_files: number
  duplicate_groups_count: number
  total_duplicate_files: number
  reclaimable_bytes: number
  formatted_reclaimable_space: string
  duplicate_groups: DuplicateGroup[]
  message?: string
}

export interface DeduplicationApplyResult {
  status: string
  files_converted: number
  space_reclaimed_bytes: number
  formatted_space_reclaimed: string
  errors: string[]
}

export const onboardingApi = {
  scan: (base_path?: string) =>
    api.post<DiscoveredLibraryPreview>('/config/onboarding/scan', { base_path }),
  confirm: (params?: { base_path?: string; items?: any[] }) =>
    api.post<OnboardingResult>('/config/onboarding/confirm', params || {}),
}

export const housekeepingApi = {
  scanDuplicates: (base_path?: string) =>
    api.post<DeduplicationScanResult>('/housekeeping/deduplicate/scan', { base_path }),
  applyDeduplication: (params?: { base_path?: string; duplicate_groups?: any[] }) =>
    api.post<DeduplicationApplyResult>('/housekeeping/deduplicate/apply', params || {}),
}

export interface VideoResolutionOption {
  height: number
  label: string
  fps?: number
  vcodec?: string
  is_direct?: boolean
  badge?: string
  badge_tooltip?: string
  filesize?: number
}

export interface AdhocProbeResult {
  status: string
  video_id: string
  title: string
  uploader: string
  duration: number
  formatted_duration: string
  thumbnail: string
  view_count: number
  description: string
  available_resolutions: VideoResolutionOption[]
  default_download_path: string
  message?: string
}

export interface AdhocDownloadParams {
  url: string
  video_quality?: string
  audio_format?: string
  extract_mode?: 'video_only' | 'audio_only' | 'both'
  custom_download_path?: string
}

export interface AdhocStartResult {
  status: string
  job_id: number
  job_type: string
  message: string
}

export const adhocApi = {
  probe: (url: string) =>
    api.post<AdhocProbeResult>('/downloads/adhoc/probe', { url }),
  start: (params: AdhocDownloadParams) =>
    api.post<AdhocStartResult>('/downloads/adhoc/start', params),
}

export default api
