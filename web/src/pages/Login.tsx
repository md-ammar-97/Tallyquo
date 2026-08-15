import { useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { isAuthenticated, requestOtp, verifyOtp, ApiError } from '../api'

export default function Login() {
  const [email, setEmail] = useState('')
  const [code, setCode] = useState('')
  const [stage, setStage] = useState<'email' | 'code'>('email')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  // Pre-existing gap, not introduced by this redesign: a logged-in user
  // could still load /login and see the form again. Closed here since
  // this file is already being touched for WI.B's routing inversion.
  if (isAuthenticated()) return <Navigate to="/" replace />

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

  async function handleVerify(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      await verifyOtp(email, code)
      navigate('/')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <main
      style={{
        display: 'flex',
        minHeight: '100vh',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <div className="block" style={{ width: 360 }}>
        <div className="block-header">
          <h2>Tallyquo</h2>
        </div>
        <div className="block-body">
          {stage === 'email' ? (
            <form onSubmit={handleRequestOtp}>
              <div className="field">
                <label htmlFor="email">Email</label>
                <input
                  id="email"
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  autoFocus
                />
              </div>
              {error && <p className="error-text">{error}</p>}
              <button type="submit" className="primary" disabled={loading} style={{ width: '100%' }}>
                {loading ? 'Sending…' : 'Send code'}
              </button>
              <p className="caption" style={{ marginTop: 12 }}>
                No account yet? Signing in creates one automatically.
              </p>
            </form>
          ) : (
            <form onSubmit={handleVerify}>
              <p className="caption" style={{ marginBottom: 12 }}>
                Enter the 6-digit code sent to {email}.
              </p>
              <div className="field">
                <label htmlFor="code">Code</label>
                <input
                  id="code"
                  required
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  autoFocus
                  inputMode="numeric"
                />
              </div>
              {error && <p className="error-text">{error}</p>}
              <button type="submit" className="primary" disabled={loading} style={{ width: '100%' }}>
                {loading ? 'Verifying…' : 'Verify'}
              </button>
            </form>
          )}
        </div>
      </div>
    </main>
  )
}
