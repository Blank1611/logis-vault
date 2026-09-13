import { useState } from 'react'
import { AlertTriangle, CheckCircle2, XCircle, Loader2 } from 'lucide-react'
import { useToast } from '../context/ToastContext'

interface InterruptedJob {
  id: number
  job_type: string
  playlist_id: number
  playlist_title: string
  created_at: string
}

interface InterruptedJobsDialogProps {
  jobs: InterruptedJob[]
  onResumeAll: () => Promise<void>
  onCancelAll: () => Promise<void>
  onIndividual: (decisions: Record<string, 'resume' | 'cancel'>) => Promise<void>
  isLoading: boolean
}

export function InterruptedJobsDialog({
  jobs,
  onResumeAll,
  onCancelAll,
  onIndividual,
  isLoading,
}: InterruptedJobsDialogProps) {
  const { toast } = useToast()
  const [mode, setMode] = useState<'individual' | null>(null)
  const [individualDecisions, setIndividualDecisions] = useState<Record<string, 'resume' | 'cancel'>>({})
  const [processingAction, setProcessingAction] = useState(false)

  const handleResumeAll = async () => {
    setProcessingAction(true)
    try {
      await onResumeAll()
    } finally {
      setProcessingAction(false)
    }
  }

  const handleCancelAll = async () => {
    setProcessingAction(true)
    try {
      await onCancelAll()
    } finally {
      setProcessingAction(false)
    }
  }

  const handleIndividualSubmit = async () => {
    // Check if all jobs have decisions
    const allDecided = jobs.every(job => individualDecisions[job.id])
    if (!allDecided) {
      toast.info('Please make a decision for all jobs')
      return
    }

    setProcessingAction(true)
    try {
      await onIndividual(individualDecisions)
    } finally {
      setProcessingAction(false)
    }
  }

  const handleJobDecision = (jobId: number, decision: 'resume' | 'cancel') => {
    setIndividualDecisions(prev => ({
      ...prev,
      [jobId]: decision,
    }))
  }

  if (!jobs.length) {
    return null
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-2xl w-full mx-4 max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="bg-amber-50 dark:bg-amber-900/20 border-b border-amber-200 dark:border-amber-900/50 p-6">
          <div className="flex items-start gap-3">
            <AlertTriangle className="w-6 h-6 text-amber-600 dark:text-amber-400 flex-shrink-0 mt-1" />
            <div>
              <h2 className="text-xl font-bold text-amber-900 dark:text-amber-100">
                Interrupted Jobs Detected
              </h2>
              <p className="text-sm text-amber-700 dark:text-amber-200 mt-1">
                {jobs.length} job{jobs.length !== 1 ? 's' : ''} were running when the server was last stopped.
              </p>
            </div>
          </div>
        </div>

        {/* Content */}
        <div className="p-6">
          {mode === null ? (
            // Initial choice screen
            <div className="space-y-6">
              <div className="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-4 space-y-3">
                {jobs.map(job => (
                  <div key={job.id} className="flex items-start gap-3 text-sm">
                    <div className="text-gray-400 dark:text-gray-500 font-mono min-w-fit">
                      Job #{job.id}
                    </div>
                    <div className="flex-1">
                      <p className="font-medium text-gray-900 dark:text-gray-100">
                        {job.job_type} - {job.playlist_title}
                      </p>
                      <p className="text-gray-500 dark:text-gray-400 text-xs mt-1">
                        Started: {new Date(job.created_at).toLocaleString()}
                      </p>
                    </div>
                  </div>
                ))}
              </div>

              <div className="space-y-3">
                <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  What would you like to do?
                </p>

                <button
                  onClick={handleResumeAll}
                  disabled={isLoading || processingAction}
                  className="w-full bg-green-50 dark:bg-green-900/20 border-2 border-green-200 dark:border-green-900/50 rounded-lg p-4 hover:bg-green-100 dark:hover:bg-green-900/30 transition text-left disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <div className="flex items-start gap-3">
                    <CheckCircle2 className="w-5 h-5 text-green-600 dark:text-green-400 flex-shrink-0 mt-0.5" />
                    <div>
                      <p className="font-semibold text-green-900 dark:text-green-100">
                        {processingAction ? 'Resuming...' : 'Resume all interrupted jobs'}
                      </p>
                      <p className="text-sm text-green-700 dark:text-green-200 mt-1">
                        Continue where they left off
                      </p>
                    </div>
                  </div>
                </button>

                <button
                  onClick={() => setMode('individual')}
                  disabled={isLoading || processingAction}
                  className="w-full bg-blue-50 dark:bg-blue-900/20 border-2 border-blue-200 dark:border-blue-900/50 rounded-lg p-4 hover:bg-blue-100 dark:hover:bg-blue-900/30 transition text-left disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <div className="flex items-start gap-3">
                    <div className="w-5 h-5 rounded border-2 border-blue-600 dark:border-blue-400 flex items-center justify-center flex-shrink-0 mt-0.5">
                      <span className="text-blue-600 dark:text-blue-400 text-xs font-bold">?</span>
                    </div>
                    <div>
                      <p className="font-semibold text-blue-900 dark:text-blue-100">
                        Decide for each job individually
                      </p>
                      <p className="text-sm text-blue-700 dark:text-blue-200 mt-1">
                        Choose resume or cancel for each job
                      </p>
                    </div>
                  </div>
                </button>

                <button
                  onClick={handleCancelAll}
                  disabled={isLoading || processingAction}
                  className="w-full bg-red-50 dark:bg-red-900/20 border-2 border-red-200 dark:border-red-900/50 rounded-lg p-4 hover:bg-red-100 dark:hover:bg-red-900/30 transition text-left disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <div className="flex items-start gap-3">
                    <XCircle className="w-5 h-5 text-red-600 dark:text-red-400 flex-shrink-0 mt-0.5" />
                    <div>
                      <p className="font-semibold text-red-900 dark:text-red-100">
                        {processingAction ? 'Cancelling...' : 'Cancel all interrupted jobs'}
                      </p>
                      <p className="text-sm text-red-700 dark:text-red-200 mt-1">
                        Mark them as cancelled
                      </p>
                    </div>
                  </div>
                </button>
              </div>
            </div>
          ) : (
            // Individual job selection screen
            <div className="space-y-6">
              <div className="space-y-3">
                {jobs.map(job => (
                  <div key={job.id} className="border border-gray-200 dark:border-gray-700 rounded-lg p-4">
                    <div className="mb-3">
                      <p className="font-medium text-gray-900 dark:text-gray-100">
                        Job #{job.id}: {job.job_type}
                      </p>
                      <p className="text-sm text-gray-600 dark:text-gray-400">
                        Playlist: {job.playlist_title}
                      </p>
                      <p className="text-xs text-gray-500 dark:text-gray-500 mt-1">
                        Started: {new Date(job.created_at).toLocaleString()}
                      </p>
                    </div>

                    <div className="flex gap-2">
                      <button
                        onClick={() => handleJobDecision(job.id, 'resume')}
                        className={`flex-1 px-3 py-2 rounded-lg text-sm font-medium transition ${
                          individualDecisions[job.id] === 'resume'
                            ? 'bg-green-600 dark:bg-green-700 text-white'
                            : 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
                        }`}
                        disabled={processingAction}
                      >
                        ✓ Resume
                      </button>
                      <button
                        onClick={() => handleJobDecision(job.id, 'cancel')}
                        className={`flex-1 px-3 py-2 rounded-lg text-sm font-medium transition ${
                          individualDecisions[job.id] === 'cancel'
                            ? 'bg-red-600 dark:bg-red-700 text-white'
                            : 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
                        }`}
                        disabled={processingAction}
                      >
                        ✕ Cancel
                      </button>
                    </div>
                  </div>
                ))}
              </div>

              <div className="flex gap-3">
                <button
                  onClick={() => setMode(null)}
                  disabled={processingAction}
                  className="flex-1 px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700/50 transition disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Back
                </button>
                <button
                  onClick={handleIndividualSubmit}
                  disabled={
                    processingAction ||
                    !jobs.every(job => individualDecisions[job.id])
                  }
                  className="flex-1 px-4 py-2 bg-blue-600 dark:bg-blue-700 text-white rounded-lg hover:bg-blue-700 dark:hover:bg-blue-800 transition disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                >
                  {processingAction ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      Processing...
                    </>
                  ) : (
                    'Apply Decisions'
                  )}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
