# Component Structure: InterruptedJobsDialog

## Component Props

```typescript
interface InterruptedJobsDialogProps {
  jobs: InterruptedJob[]
  onResumeAll: () => Promise<void>
  onCancelAll: () => Promise<void>
  onIndividual: (decisions: Record<string, 'resume' | 'cancel'>) => Promise<void>
  isLoading: boolean
}

interface InterruptedJob {
  id: number
  job_type: string
  playlist_id: number
  playlist_title: string
  created_at: string
}
```

## Component State

```typescript
// Selected interaction mode
const [mode, setMode] = useState<'choice' | 'individual' | null>(null)

// Individual job decisions (only in individual mode)
const [individualDecisions, setIndividualDecisions] = useState<Record<string, 'resume' | 'cancel'>>({})

// Whether an action is being processed
const [processingAction, setProcessingAction] = useState(false)
```

## Layout Structure

```
Dialog Container (dark overlay + white card)
├── Header Section
│   ├── AlertTriangle Icon
│   ├── Title: "Interrupted Jobs Detected"
│   └── Count: "X job(s) were running..."
│
├── Content Section (3 variants based on mode)
│   │
│   ├─ NULL Mode (Initial Screen)
│   │  ├── Job List
│   │  │  ├── Job #1
│   │  │  ├── Job #2
│   │  │  └── ...
│   │  └── Three Action Buttons
│   │     ├── ✓ Resume All
│   │     ├── ? Decide Individually
│   │     └── ✕ Cancel All
│   │
│   ├─ 'choice' Mode (Processing)
│   │  ├── Status Message with spinner
│   │  └── Back Button
│   │
│   └─ 'individual' Mode (Per-Job Selection)
│      ├── Job Cards (for each job)
│      │  ├── Job Title & Info
│      │  ├── ✓ Resume Button
│      │  └── ✕ Cancel Button
│      └── Action Buttons
│         ├── Back Button
│         └── Apply Decisions Button
```

## Visual Styling

### Colors
- **Header**: Amber (warning) background
- **Resume**: Green (#22c55e)
- **Cancel**: Red (#ef4444)
- **Individual**: Blue (#3b82f6)
- **Processing**: Yellow (#eab308)

### Dark Mode
- All colors auto-adjust for dark theme
- Consistent with app's dark mode system

### Responsive
- Max width: 2xl (42rem)
- Padding: responsive (mx-4)
- Height: auto with max-height + overflow
- Full viewport height usage on mobile

## User Interactions

### Initial Screen
1. **Resume All Button**
   - Sets mode to 'choice'
   - Calls `onResumeAll()`
   - Sets `processingAction = true`
   - Shows spinner

2. **Individual Button**
   - Sets mode to 'individual'
   - Shows job list for selection

3. **Cancel All Button**
   - Sets mode to 'choice'
   - Calls `onCancelAll()`
   - Sets `processingAction = true`
   - Shows spinner

### Individual Screen
1. **Resume/Cancel Buttons** (per job)
   - Toggle job decision state
   - Visual feedback with colors

2. **Back Button**
   - Returns to initial screen
   - Preserves decisions until submitted

3. **Apply Decisions Button**
   - Validates all jobs decided
   - Calls `onIndividual(decisions)`
   - Disabled until all decided

### Processing
- Auto-dismisses on success
- Updates parent state in App.tsx

## Accessibility

- Proper heading hierarchy (h2)
- ARIA-friendly color usage (not relying on color alone)
- Clear button labels
- Keyboard navigation support
- Disabled state feedback

## Error Handling

- Missing decisions: Alert shown
- API failures: Handled in App.tsx
- Network timeout: Request fails gracefully
- User can retry by refreshing

## Integration with App.tsx

```typescript
{/* Interrupted Jobs Dialog */}
{showInterruptedDialog && interruptedJobs.length > 0 && (
  <InterruptedJobsDialog
    jobs={interruptedJobs}
    onResumeAll={async () => {
      await handleInterruptedJobs.mutateAsync({
        action: 'resume_all',
      })
    }}
    onCancelAll={async () => {
      await handleInterruptedJobs.mutateAsync({
        action: 'cancel_all',
      })
    }}
    onIndividual={async (decisions) => {
      await handleInterruptedJobs.mutateAsync({
        action: 'individual',
        jobDecisions: decisions,
      })
    }}
    isLoading={handleInterruptedJobs.isPending}
  />
)}
```

## Side Effects After Dialog Close

On successful completion:
1. Dialog closes
2. `interruptedJobsHandled` flag set to true
3. Jobs query invalidated
4. Playlists query invalidated
5. App refetches latest data
6. User sees updated job statuses

## Styling Classes Reference

### Tailwind Classes Used
- Layout: `fixed`, `inset-0`, `flex`, `items-center`, `justify-center`, `z-50`
- Spacing: `mx-4`, `p-4`, `p-6`, `gap-2`, `gap-3`, `gap-6`, `space-y-*`
- Colors: `bg-white`, `dark:bg-gray-800`, `border-amber-*`, `text-green-*`, etc.
- Effects: `shadow-xl`, `rounded-lg`, `transition`, `opacity-50`
- Interactive: `hover:`, `disabled:`, `cursor-not-allowed`

## Performance Considerations

- Component re-renders only when props change
- Decisions state updates efficiently with spread operator
- No unnecessary API calls (mutation handles this)
- Dialog removes from DOM when not shown
- Smooth animations via CSS transitions

## Browser Compatibility

- Modern browsers (Chrome, Firefox, Safari, Edge)
- React 18+
- TypeScript support
- Tailwind CSS 3+
- Lucide React icons
