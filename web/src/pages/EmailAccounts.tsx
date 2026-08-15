import { useEffect, useState } from 'react'
import { api, ApiError } from '../api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'

interface EmailAccount {
  id: string
  label: string
  from_name: string
  from_address: string
  smtp_host: string
  smtp_port: number
  smtp_security: string
  smtp_username: string
  is_default: boolean
  verified_at: string | null
}

const emptyForm = {
  label: '',
  from_name: '',
  from_address: '',
  smtp_host: '',
  smtp_port: '587',
  smtp_security: 'starttls',
  smtp_username: '',
  password: '',
  is_default: false,
}

export default function EmailAccounts() {
  const [accounts, setAccounts] = useState<EmailAccount[]>([])
  const [form, setForm] = useState(emptyForm)
  const [showForm, setShowForm] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [verifying, setVerifying] = useState<string | null>(null)
  const [verifyMessage, setVerifyMessage] = useState<Record<string, string>>({})

  function load() {
    api.get<EmailAccount[]>('/email-accounts').then(setAccounts)
  }

  useEffect(load, [])

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    setSaving(true)
    setError(null)
    try {
      await api.post('/email-accounts', { ...form, smtp_port: Number(form.smtp_port) })
      setForm(emptyForm)
      setShowForm(false)
      load()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not save this account.')
    } finally {
      setSaving(false)
    }
  }

  async function handleVerify(id: string) {
    setVerifying(id)
    setVerifyMessage((m) => ({ ...m, [id]: '' }))
    try {
      await api.post(`/email-accounts/${id}/verify`)
      setVerifyMessage((m) => ({ ...m, [id]: 'Verified.' }))
      load()
    } catch (err) {
      setVerifyMessage((m) => ({ ...m, [id]: err instanceof ApiError ? err.message : 'Could not verify.' }))
    } finally {
      setVerifying(null)
    }
  }

  async function handleArchive(id: string) {
    if (!window.confirm('Remove this email account?')) return
    await api.delete(`/email-accounts/${id}`)
    load()
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="font-display text-display-sm text-ink">Email accounts</h1>
        <p className="text-body-sm text-mute">
          Invoices are emailed through your own mail server, never a shared sender identity — add the account you
          want to send from below.
        </p>
      </div>

      <Card>
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle className="font-display text-display-xs font-semibold text-ink">Configured accounts</CardTitle>
          <Button onClick={() => setShowForm((s) => !s)}>{showForm ? 'Cancel' : 'Add account'}</Button>
        </CardHeader>
        {showForm && (
          <CardContent className="border-b border-divider pb-6">
            <form onSubmit={handleCreate} className="flex flex-col gap-4">
              <div className="flex flex-wrap gap-4">
                <div className="flex flex-1 flex-col gap-1.5">
                  <Label>Label</Label>
                  <Input required placeholder="My Gmail" value={form.label} onChange={(e) => setForm({ ...form, label: e.target.value })} />
                </div>
                <div className="flex flex-1 flex-col gap-1.5">
                  <Label>From name</Label>
                  <Input required value={form.from_name} onChange={(e) => setForm({ ...form, from_name: e.target.value })} />
                </div>
              </div>
              <div className="flex flex-col gap-1.5">
                <Label>From address</Label>
                <Input required type="email" value={form.from_address} onChange={(e) => setForm({ ...form, from_address: e.target.value })} />
              </div>
              <div className="flex flex-wrap gap-4">
                <div className="flex flex-1 flex-col gap-1.5">
                  <Label>SMTP host</Label>
                  <Input
                    required
                    placeholder="smtp.gmail.com"
                    value={form.smtp_host}
                    onChange={(e) => setForm({ ...form, smtp_host: e.target.value })}
                  />
                </div>
                <div className="flex flex-1 flex-col gap-1.5">
                  <Label>Port</Label>
                  <Input required value={form.smtp_port} onChange={(e) => setForm({ ...form, smtp_port: e.target.value })} />
                </div>
              </div>
              <div className="flex flex-wrap gap-4">
                <div className="flex flex-1 flex-col gap-1.5">
                  <Label>Security</Label>
                  <select
                    className="h-9 rounded-md border border-ink bg-canvas px-3 text-body-sm"
                    value={form.smtp_security}
                    onChange={(e) => setForm({ ...form, smtp_security: e.target.value })}
                  >
                    <option value="starttls">STARTTLS</option>
                    <option value="tls">TLS</option>
                    <option value="none">None</option>
                  </select>
                </div>
                <div className="flex flex-1 flex-col gap-1.5">
                  <Label>Username</Label>
                  <Input required value={form.smtp_username} onChange={(e) => setForm({ ...form, smtp_username: e.target.value })} />
                </div>
              </div>
              <div className="flex flex-col gap-1.5">
                <Label>Password (or app password)</Label>
                <Input required type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
              </div>
              <label className="flex items-center gap-2 text-body-sm text-ink">
                <input
                  type="checkbox"
                  className="size-4 accent-ink"
                  checked={form.is_default}
                  onChange={(e) => setForm({ ...form, is_default: e.target.checked })}
                />
                Use as default sending account
              </label>
              {error && <p className="text-body-sm text-negative">{error}</p>}
              <Button type="submit" disabled={saving} className="self-start">
                {saving ? 'Saving…' : 'Add account'}
              </Button>
            </form>
          </CardContent>
        )}
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Label</TableHead>
                <TableHead>From</TableHead>
                <TableHead>Server</TableHead>
                <TableHead>Status</TableHead>
                <TableHead></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {accounts.map((a) => (
                <TableRow key={a.id}>
                  <TableCell className="flex items-center gap-2">
                    {a.label} {a.is_default && <Badge variant="secondary">default</Badge>}
                  </TableCell>
                  <TableCell>
                    {a.from_name} &lt;{a.from_address}&gt;
                  </TableCell>
                  <TableCell>
                    {a.smtp_host}:{a.smtp_port} ({a.smtp_security})
                  </TableCell>
                  <TableCell>
                    {a.verified_at ? (
                      <Badge variant="secondary" className="bg-positive/15 text-positive-deep">verified</Badge>
                    ) : (
                      <Badge variant="secondary">unverified</Badge>
                    )}
                    {verifyMessage[a.id] && <div className="mt-1 text-caption text-mute">{verifyMessage[a.id]}</div>}
                  </TableCell>
                  <TableCell className="flex gap-2">
                    <Button variant="outline" size="sm" onClick={() => handleVerify(a.id)} disabled={verifying === a.id}>
                      {verifying === a.id ? 'Testing…' : 'Test'}
                    </Button>
                    <Button variant="destructive" size="sm" onClick={() => handleArchive(a.id)}>
                      Remove
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
              {accounts.length === 0 && (
                <TableRow>
                  <TableCell colSpan={5} className="py-6 text-center text-body-sm text-mute">
                    No email accounts yet. Add one to send invoices from your own address.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  )
}
