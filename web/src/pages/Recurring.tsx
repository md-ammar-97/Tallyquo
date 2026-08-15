import { useEffect, useState } from 'react'
import { api, ApiError } from '../api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'

interface Rule {
  id: string
  client_name: string | null
  cadence: string
  next_run_date: string
  auto_issue: boolean
  is_paused: boolean
  last_run_date: string | null
  occurrences_remaining: number | null
}

export default function Recurring() {
  const [rules, setRules] = useState<Rule[]>([])
  const [error, setError] = useState<string | null>(null)

  function load() {
    api.get<Rule[]>('/recurring').then(setRules)
  }

  useEffect(load, [])

  async function act(id: string, action: 'pause' | 'resume' | 'skip') {
    setError(null)
    try {
      await api.post(`/recurring/${id}/${action}`)
      load()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : `Could not ${action} rule.`)
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <h1 className="font-display text-display-sm text-ink">Recurring invoices</h1>

      <Card>
        <CardHeader>
          <CardTitle className="font-display text-display-xs font-semibold text-ink">All rules</CardTitle>
        </CardHeader>
        <CardContent>
          {error && <p className="mb-3 text-body-sm text-negative">{error}</p>}
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Client</TableHead>
                <TableHead>Cadence</TableHead>
                <TableHead>Next run</TableHead>
                <TableHead>Auto-issue</TableHead>
                <TableHead>Status</TableHead>
                <TableHead></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rules.map((rule) => (
                <TableRow key={rule.id}>
                  <TableCell>{rule.client_name ?? '—'}</TableCell>
                  <TableCell>{rule.cadence}</TableCell>
                  <TableCell>{rule.next_run_date}</TableCell>
                  <TableCell>{rule.auto_issue ? 'Yes' : 'No, drafts only'}</TableCell>
                  <TableCell>
                    <Badge variant="secondary" className={`capitalize ${!rule.is_paused ? 'bg-positive/15 text-positive-deep' : ''}`}>
                      {rule.is_paused ? 'paused' : 'active'}
                    </Badge>
                  </TableCell>
                  <TableCell className="flex gap-2">
                    {rule.is_paused ? (
                      <Button variant="outline" size="sm" onClick={() => act(rule.id, 'resume')}>Resume</Button>
                    ) : (
                      <>
                        <Button variant="outline" size="sm" onClick={() => act(rule.id, 'skip')}>Skip next</Button>
                        <Button variant="outline" size="sm" onClick={() => act(rule.id, 'pause')}>Pause</Button>
                      </>
                    )}
                  </TableCell>
                </TableRow>
              ))}
              {rules.length === 0 && (
                <TableRow>
                  <TableCell colSpan={6} className="py-6 text-center text-body-sm text-mute">
                    No recurring rules yet. Open an invoice and choose "Make recurring" to set one up.
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
