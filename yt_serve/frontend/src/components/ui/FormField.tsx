import { useState } from 'react'
import { Info, Zap, Music, Disc } from 'lucide-react'

export interface FieldHeaderProps {
  label: string
  required?: boolean
  recommended?: string
  infoText?: string
  id?: string
  className?: string
}

export function FieldHeader({
  label,
  required = false,
  recommended,
  infoText,
  id,
  className = '',
}: FieldHeaderProps) {
  const [open, setOpen] = useState(false)

  return (
    <div className={`mb-2 ${className}`}>
      <div className="flex items-center justify-start gap-2 flex-wrap min-h-[2rem]">
        <div className="flex items-center gap-1.5 flex-wrap">
          <label
            htmlFor={id}
            className="text-sm font-semibold text-gray-900 dark:text-gray-100 flex items-center gap-1"
          >
            <span>{label}</span>
            {required && <span className="text-rose-500 font-bold">*</span>}
          </label>

          {infoText && (
            <button
              type="button"
              onClick={() => setOpen(!open)}
              className={`px-1.5 py-0.5 rounded-md text-xs transition-colors flex items-center gap-1 shrink-0 ${
                open
                  ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/60 dark:text-blue-200'
                  : 'text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800'
              }`}
              title="Toggle explanation"
            >
              <Info className="w-3.5 h-3.5 text-blue-500" />
              <span className="text-[11px] font-medium">{open ? 'Hide' : 'Info'}</span>
            </button>
          )}

          {recommended && (
            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-400 border border-emerald-300 dark:border-emerald-800/80 shadow-xs">
              {recommended}
            </span>
          )}
        </div>
      </div>
      {open && infoText && (
        <div className="mt-1 p-2.5 bg-blue-50 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-800/80 rounded-lg text-xs text-blue-950 dark:text-blue-200 leading-relaxed shadow-sm animate-in fade-in duration-150">
          {infoText}
        </div>
      )}
    </div>
  )
}

export function AudioModeCard({ mode }: { mode: string }) {
  if (mode === 'copy') {
    return (
      <div className="mt-2.5 p-3.5 bg-emerald-950/40 backdrop-blur-md border border-emerald-500/40 rounded-xl text-xs space-y-1 shadow-[0_0_15px_rgba(16,185,129,0.15)]">
        <div className="font-semibold text-emerald-300 flex items-center gap-1.5">
          <Zap className="w-4 h-4 text-emerald-400" />
          Direct Stream Copy (Lossless & Instantaneous)
        </div>
        <p className="text-emerald-300/80 leading-relaxed">
          Extracts YouTube's original native audio track (<code className="font-mono bg-emerald-900/60 text-emerald-200 px-1 py-0.5 rounded">.m4a</code> for AAC, <code className="font-mono bg-emerald-900/60 text-emerald-200 px-1 py-0.5 rounded">.opus</code> for Opus) without transcoding. Takes ~0.2s per song with zero CPU load and zero acoustic compression loss.
        </p>
      </div>
    )
  }
  if (mode === 'mp3_best') {
    return (
      <div className="mt-2.5 p-3.5 bg-indigo-950/40 backdrop-blur-md border border-indigo-500/40 rounded-xl text-xs space-y-1 shadow-[0_0_15px_rgba(99,102,241,0.15)]">
        <div className="font-semibold text-indigo-300 flex items-center gap-1.5">
          <Music className="w-4 h-4 text-indigo-400" />
          MP3 Best Quality (VBR ~250–320 kbps)
        </div>
        <p className="text-indigo-300/80 leading-relaxed">
          Re-encodes audio to universal MP3 at maximum variable bitrate (<code className="font-mono bg-indigo-900/60 text-indigo-200 px-1 py-0.5 rounded">libmp3lame -q:a 0</code>). 100% compatible with older car stereos and legacy MP3 players.
        </p>
      </div>
    )
  }
  if (mode === 'mp3_high') {
    return (
      <div className="mt-2.5 p-3.5 bg-blue-950/40 backdrop-blur-md border border-blue-500/40 rounded-xl text-xs space-y-1 shadow-[0_0_15px_rgba(59,130,246,0.15)]">
        <div className="font-semibold text-blue-300 flex items-center gap-1.5">
          <Music className="w-4 h-4 text-blue-400" />
          MP3 High Quality (VBR ~190–250 kbps)
        </div>
        <p className="text-blue-300/80 leading-relaxed">
          Standard high-quality MP3 encoding (<code className="font-mono bg-blue-900/60 text-blue-200 px-1 py-0.5 rounded">libmp3lame -q:a 2</code>). Great balance of smaller file sizes and high audio fidelity.
        </p>
      </div>
    )
  }
  if (mode === 'opus') {
    return (
      <div className="mt-2.5 p-3.5 bg-purple-950/40 backdrop-blur-md border border-purple-500/40 rounded-xl text-xs space-y-1 shadow-[0_0_15px_rgba(168,85,247,0.15)]">
        <div className="font-semibold text-purple-300 flex items-center gap-1.5">
          <Disc className="w-4 h-4 text-purple-400" />
          Opus Audio (~160 kbps)
        </div>
        <p className="text-purple-300/80 leading-relaxed">
          Modern, highly-efficient Opus audio stream. Exceptional fidelity at lower bitrates.
        </p>
      </div>
    )
  }
  return null
}
