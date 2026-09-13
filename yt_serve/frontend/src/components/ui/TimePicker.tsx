import { useState, useEffect } from 'react'

export interface TimePickerProps {
  value: string // "HH:MM" in 24-hour format (e.g. "04:00" or "16:30")
  onChange: (timeStr: string) => void
  id?: string
  className?: string
}

export function TimePicker({
  value = '04:00',
  onChange,
  id,
  className = '',
}: TimePickerProps) {
  // Parse incoming 24h "HH:MM" into 12h representation
  const parseTime = (timeStr: string): { hour12: number; minute: number; period: 'AM' | 'PM' } => {
    try {
      const [hStr, mStr] = (timeStr || '04:00').split(':')
      let h24 = parseInt(hStr, 10)
      if (isNaN(h24)) h24 = 4
      let m = parseInt(mStr, 10)
      if (isNaN(m)) m = 0

      const period: 'AM' | 'PM' = h24 >= 12 ? 'PM' : 'AM'
      let hour12 = h24 % 12
      if (hour12 === 0) hour12 = 12

      return { hour12, minute: m, period }
    } catch {
      return { hour12: 4, minute: 0, period: 'AM' }
    }
  }

  const initial = parseTime(value)
  const [hour, setHour] = useState<number>(initial.hour12)
  const [minute, setMinute] = useState<number>(initial.minute)
  const [period, setPeriod] = useState<'AM' | 'PM'>(initial.period)

  useEffect(() => {
    const parsed = parseTime(value)
    setHour(parsed.hour12)
    setMinute(parsed.minute)
    setPeriod(parsed.period)
  }, [value])

  const emitTime = (h12: number, m: number, p: 'AM' | 'PM') => {
    let h24 = h12 % 12
    if (p === 'PM') h24 += 12

    const hStr = h24.toString().padStart(2, '0')
    const mStr = m.toString().padStart(2, '0')
    onChange(`${hStr}:${mStr}`)
  }

  const handleHourChange = (newHour: number) => {
    let clamped = Math.max(1, Math.min(12, isNaN(newHour) ? 12 : newHour))
    setHour(clamped)
    emitTime(clamped, minute, period)
  }

  const handleMinuteChange = (newMin: number) => {
    let clamped = Math.max(0, Math.min(59, isNaN(newMin) ? 0 : newMin))
    setMinute(clamped)
    emitTime(hour, clamped, period)
  }

  const handlePeriodToggle = (newPeriod: 'AM' | 'PM') => {
    setPeriod(newPeriod)
    emitTime(hour, minute, newPeriod)
  }

  return (
    <div id={id} className={`flex items-center gap-2 ${className}`}>
      {/* Hour input */}
      <div className="relative">
        <input
          type="number"
          min={1}
          max={12}
          value={hour.toString().padStart(2, '0')}
          onChange={(e) => handleHourChange(parseInt(e.target.value, 10))}
          className="w-16 px-2.5 py-2.5 bg-gray-950 border border-gray-700 rounded-xl text-white font-mono text-center text-sm font-semibold focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          title="Hours (1-12)"
        />
        <span className="sr-only">Hour</span>
      </div>

      <span className="text-gray-400 font-bold text-lg select-none">:</span>

      {/* Minute input */}
      <div className="relative">
        <input
          type="number"
          min={0}
          max={59}
          value={minute.toString().padStart(2, '0')}
          onChange={(e) => handleMinuteChange(parseInt(e.target.value, 10))}
          className="w-16 px-2.5 py-2.5 bg-gray-950 border border-gray-700 rounded-xl text-white font-mono text-center text-sm font-semibold focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          title="Minutes (00-59)"
        />
        <span className="sr-only">Minute</span>
      </div>

      {/* AM / PM Segmented Toggle */}
      <div className="inline-flex rounded-xl bg-gray-950 p-1 border border-gray-700">
        <button
          type="button"
          onClick={() => handlePeriodToggle('AM')}
          className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
            period === 'AM'
              ? 'bg-blue-600 text-white shadow'
              : 'text-gray-400 hover:text-white'
          }`}
        >
          AM
        </button>
        <button
          type="button"
          onClick={() => handlePeriodToggle('PM')}
          className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
            period === 'PM'
              ? 'bg-blue-600 text-white shadow'
              : 'text-gray-400 hover:text-white'
          }`}
        >
          PM
        </button>
      </div>

      <span className="text-xs text-gray-500 font-mono ml-1 hidden sm:inline">
        ({value})
      </span>
    </div>
  )
}
