import { useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { useReducedMotion } from 'motion/react'
import { isAuthenticated, requestOtp, verifyOtp, ApiError } from '../api'
import OtpInput, { type OtpStatus } from '@/components/auth/OtpInput'
import { Button } from '@/components/ui/button'
import logo from '../assets/logo.svg'

export default function Login() {
  const [email, setEmail] = useState('')
  const [code, setCode] = useState('')
  const [stage, setStage] = useState<'email' | 'code'>('email')
  const [otpStatus, setOtpStatus] = useState<OtpStatus>('idle')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()
  const reducedMotion = useReducedMotion() ?? false

  // Pre-existing gap, not introduced by this redesign: a logged-in user
  // could still load /login and see the form again. Closed here since
  // this file is already being touched for WI.B's routing inversion.
  // Captured once at mount, not re-evaluated every render: a plain
  // `if (isAuthenticated())` re-runs on every render, so it would fire
  // the instant verifyOtp() succeeds (setOtpStatus('success') itself
  // triggers the next render) and force-navigate away immediately,
  // skipping the whole success animation this page exists to show. The
  // handleVerify success path below owns navigation for a user who logs
  // in during this component's lifetime; this guard only ever needs to
  // catch someone arriving already authenticated.
  const [wasAlreadyAuthenticated] = useState(isAuthenticated)
  if (wasAlreadyAuthenticated) return <Navigate to="/" replace />

  async function handleRequestOtp(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      await requestOtp(email)
      setStage('code')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong.')
    } finally {
      setLoading(false)
    }
  }

  async function handleVerify() {
    if (code.length !== 6 || otpStatus === 'verifying' || otpStatus === 'success') return
    setError(null)
    setOtpStatus('verifying')
    try {
      await verifyOtp(email, code)
      setOtpStatus('success')
      // Let the converge + tick animation play before leaving the page --
      // navigating instantly would cut off the one payoff moment this
      // whole animation exists for. Collapses under reduced motion, same
      // as the animation itself.
      setTimeout(() => navigate('/'), reducedMotion ? 150 : 1100)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'That code didn’t match.')
      setOtpStatus('error')
    }
  }

  function handleErrorAnimationComplete() {
    setCode('')
    setOtpStatus('idle')
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-background px-4 font-sans">
      <div className="w-full max-w-sm rounded-xl bg-card p-8 ring-1 ring-ink/10">
        <img src={logo} alt="Tallyquo" className="mx-auto mb-6 h-11 w-auto" />

        {stage === 'email' ? (
          <form onSubmit={handleRequestOtp} className="flex flex-col gap-4">
            <div className="text-center">
              <h1 className="font-display text-display-xs text-ink">Welcome back</h1>
              <p className="mt-1 text-body-sm text-mute">Sign in with just your email.</p>
            </div>
            <div className="flex flex-col gap-1.5">
              <label htmlFor="email" className="text-body-sm font-semibold text-ink">
                Email
              </label>
              <input
                id="email"
                type="email"
                required
                autoFocus
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="h-12 rounded-md border border-input bg-card px-4 text-body-md text-ink outline-none focus:border-ring focus:ring-3 focus:ring-ring/40"
              />
            </div>
            {error && <p className="text-body-sm text-negative">{error}</p>}
            <Button type="submit" disabled={loading} className="h-12 text-button-md">
              {loading ? 'Sending…' : 'Send code'}
            </Button>
            <p className="text-center text-caption text-mute">No account yet? Signing in creates one automatically.</p>
          </form>
        ) : (
          <div className="flex flex-col items-center gap-5">
            <div className="text-center">
              <h1 className="font-display text-display-xs text-ink">Enter your code</h1>
              <p className="mt-1 text-body-sm text-mute">
                We sent a 6-digit code to <span className="font-semibold text-ink">{email}</span>.
              </p>
            </div>

            <OtpInput
              value={code}
              onChange={setCode}
              length={6}
              status={otpStatus}
              onErrorAnimationComplete={handleErrorAnimationComplete}
            />

            {error && otpStatus !== 'verifying' && <p className="text-body-sm text-negative">{error}</p>}

            <Button
              onClick={handleVerify}
              disabled={code.length !== 6 || otpStatus === 'verifying' || otpStatus === 'success'}
              className="h-12 w-full text-button-md"
            >
              {otpStatus === 'verifying' ? 'Verifying…' : otpStatus === 'success' ? 'Verified' : 'Verify'}
            </Button>

            <button
              type="button"
              onClick={() => {
                setStage('email')
                setCode('')
                setOtpStatus('idle')
                setError(null)
              }}
              className="text-body-sm font-semibold text-primary-active hover:underline"
            >
              Use a different email
            </button>
          </div>
        )}
      </div>
    </main>
  )
}
