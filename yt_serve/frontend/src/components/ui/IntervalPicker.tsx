import { useState, useEffect } from 'react'

export interface IntervalPickerProps {
  valueMinutes: number
  onChange: (minutes: number) => void
  minMinutes?: number
  defaultUnit?: 'minutes' | 'hours' | 'days'
  className?: string
  id?: string
}

type Unit = 'minutes' | 'hours' | 'days'

interface Preset {
  label: string
  minutes: number
}

const DEFAULT_PRESETS: Preset[] = [
  { label: 'Every 15 Minutes', minutes: 15 },
  { label: 'Every 30 Minutes', minutes: 30 },
  { label: 'Every 1 Hour', minutes: 60 },
  { label: 'Every 6 Hours', minutes: 360 },
  { label: 'Every 12 Hours', minutes: 720 },
  { label: 'Once Daily (24 Hours)', minutes: 1440 },
]

export function IntervalPicker({
  valueMinutes,
  onChange,
  minMinutes = 1,
  className = '',
  id,
}: IntervalPickerProps) {
  // Check if current value matches any preset
  const matchingPreset = DEFAULT_PRESETS.find(p => p.minutes === valueMinutes)
  const [isCustom, setIsCustom] = useState<boolean>(!matchingPreset)

  // Custom state
  const decomposeMinutes = (total: number): { val: number; u: Unit } => {
    if (total >= 1440 && total % 1440 === 0) {
      return { val: Math.round(total / 1440), u: 'days' }
    }
    if (total >= 60 && total % 60 === 0) {
      return { val: Math.round(total / 60), u: 'hours' }
    }
    return { val: total, u: 'minutes' }
  }

  const initialCustom = decomposeMinutes(valueMinutes || 60)
  const [customValue, setCustomValue] = useState<number>(initialCustom.val)
  const [customUnit, setCustomUnit] = useState<Unit>(initialCustom.u)

  // Sync state if external value changes
  useEffect(() => {
    const preset = DEFAULT_PRESETS.find(p => p.minutes === valueMinutes)
    if (preset) {
      setIsCustom(false)
    } else {
      setIsCustom(true)
      const decomp = decomposeMinutes(valueMinutes)
      setCustomValue(decomp.val)
      setCustomUnit(decomp.u)
    }
  }, [valueMinutes])

  const handlePresetSelect = (mins: number) => {
    if (mins === -1) {
      setIsCustom(true)
      const decomp = decomposeMinutes(valueMinutes || 60)
      setCustomValue(decomp.val)
      setCustomUnit(decomp.u)
    } else {
      setIsCustom(false)
      onChange(mins)
    }
  }

  const handleCustomChange = (val: number, unit: Unit) => {
    const cleanVal = Math.max(1, isNaN(val) ? 1 : val)
    setCustomValue(cleanVal)
    setCustomUnit(unit)

    let totalMins = cleanVal
    if (unit === 'hours') totalMins = cleanVal * 60
    else if (unit === 'days') totalMins = cleanVal * 1440

    totalMins = Math.max(minMinutes, totalMins)
    onChange(totalMins)
  }

  // Format friendly text for summary badge
  const formatFriendlySummary = (mins: number): string => {
    if (mins < 60) return `every ${mins} minute${mins > 1 ? 's' : ''}`
    if (mins < 1440) {
      const hrs = (mins / 60).toFixed(mins % 60 === 0 ? 0 : 1)
      return `every ${hrs} hour${parseFloat(hrs) > 1 ? 's' : ''} (${mins} mins)`
    }
    const days = (mins / 1440).toFixed(mins % 1440 === 0 ? 0 : 1)
    return `every ${days} day${parseFloat(days) > 1 ? 's' : ''} (${mins} mins)`
  }

  return (
    <div className={`space-y-2.5 ${className}`}>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
        <div>
          <select
            id={id}
            value={isCustom ? -1 : valueMinutes}
            onChange={(e) => handlePresetSelect(parseInt(e.target.value, 10))}
            className="w-full px-3.5 py-2.5 bg-gray-950 border border-gray-700 rounded-xl text-white text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          >
            {DEFAULT_PRESETS.map((preset) => (
              <option key={preset.minutes} value={preset.minutes}>
                {preset.label}
              </option>
            ))}
            <option value={-1}>Custom Interval...</option>
          </select>
        </div>

        {isCustom && (
          <div className="flex items-center gap-2 animate-in fade-in duration-150">
            <input
              type="number"
              min={1}
              value={customValue}
              onChange={(e) => handleCustomChange(parseInt(e.target.value, 10) || 1, customUnit)}
              className="w-24 px-3 py-2.5 bg-gray-950 border border-gray-700 rounded-xl text-white font-mono text-sm text-center focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              placeholder="Value"
            />
            <select
              value={customUnit}
              onChange={(e) => handleCustomChange(customValue, e.target.value as Unit)}
              className="flex-1 px-3 py-2.5 bg-gray-950 border border-gray-700 rounded-xl text-white text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="minutes">Minute(s)</option>
              <option value="hours">Hour(s)</option>
              <option value="days">Day(s)</option>
            </select>
          </div>
        )}
      </div>

      <div className="flex items-center gap-2 text-xs text-gray-400">
        <span className="w-1.5 h-1.5 rounded-full bg-blue-400 shrink-0"></span>
        <span>Runs {formatFriendlySummary(valueMinutes)}</span>
      </div>
    </div>
  )
}
