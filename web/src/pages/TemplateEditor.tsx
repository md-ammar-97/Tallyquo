import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { Lock, GripVertical } from 'lucide-react'
import { API_BASE_URL, api, ApiError } from '../api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

interface Theme {
  accent_color: string
  font_scale: number
  margins_mm: number
  logo_position: 'top_left' | 'top_center' | 'top_right' | 'none'
}

interface Template {
  id: string
  name: string
  theme: Theme
  blocks: string[]
  is_system: boolean
}

const REQUIRED_BLOCKS = ['supplier', 'document', 'bill_to', 'services', 'totals']
const OPTIONAL_BLOCK_LABELS: Record<string, string> = { payment: 'Payment instructions', footer: 'Notes / footer' }

const DEFAULT_THEME: Theme = { accent_color: '#1A365D', font_scale: 1.0, margins_mm: 20, logo_position: 'top_left' }

export default function TemplateEditor() {
  const { id } = useParams()
  const [searchParams] = useSearchParams()
  const cloneFrom = searchParams.get('clone')
  const navigate = useNavigate()

  const [name, setName] = useState('')
  const [theme, setTheme] = useState<Theme>(DEFAULT_THEME)
  // Every entry in `optionalBlocks` is shown (drag to reorder); `enabled`
  // controls whether it's actually included in the saved `blocks` array.
  const [optionalBlocks, setOptionalBlocks] = useState<{ key: string; enabled: boolean }[]>([
    { key: 'payment', enabled: true },
    { key: 'footer', enabled: true },
  ])
  const [loaded, setLoaded] = useState(id === undefined && cloneFrom === null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [logoUploading, setLogoUploading] = useState(false)
  const [hasLogo, setHasLogo] = useState<boolean | null>(null)
  const logoInputRef = useRef<HTMLInputElement>(null)

  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const previewUrlRef = useRef<string | null>(null)
  const dragIndex = useRef<number | null>(null)

  useEffect(() => {
    async function loadSource() {
      const sourceId = id ?? cloneFrom
      if (!sourceId) return
      const templates = await api.get<Template[]>('/templates')
      const source = templates.find((t) => t.id === sourceId)
      if (!source) {
        setError('Template not found.')
        setLoaded(true)
        return
      }
      setName(id ? source.name : `${source.name} (copy)`)
      setTheme({ ...DEFAULT_THEME, ...source.theme })
      setOptionalBlocks([
        { key: 'payment', enabled: source.blocks.includes('payment') },
        { key: 'footer', enabled: source.blocks.includes('footer') },
      ])
      setLoaded(true)
    }
    loadSource()
  }, [id, cloneFrom])

  useEffect(() => {
    api.get<{ logo_ref: string | null }>('/profile').then((p) => setHasLogo(!!p.logo_ref))
  }, [])

  function blocksArray(): string[] {
    return [...REQUIRED_BLOCKS, ...optionalBlocks.filter((b) => b.enabled).map((b) => b.key)]
  }

  // Live preview: re-fetch (debounced) whenever theme or block
  // selection/order changes. Renders against the tenant's real profile
  // data with canned sample line items -- never persisted.
  useEffect(() => {
    if (!loaded) return
    const timer = setTimeout(async () => {
      try {
        const token = localStorage.getItem('access_token')
        const res = await fetch(`${API_BASE_URL}/templates/preview`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
          body: JSON.stringify({ theme, blocks: blocksArray() }),
        })
        if (!res.ok) return
        const blob = await res.blob()
        const url = URL.createObjectURL(blob)
        if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current)
        previewUrlRef.current = url
        setPreviewUrl(url)
      } catch {
        /* preview is best-effort; a failed refresh just leaves the last one showing */
      }
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, 500)
    return () => clearTimeout(timer)
  }, [theme, optionalBlocks, loaded])

  useEffect(() => {
    return () => {
      if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current)
    }
  }, [])

  function handleDragStart(index: number) {
    dragIndex.current = index
  }

  function handleDragOver(e: React.DragEvent, index: number) {
    e.preventDefault()
    if (dragIndex.current === null || dragIndex.current === index) return
    const next = [...optionalBlocks]
    const [moved] = next.splice(dragIndex.current, 1)
    next.splice(index, 0, moved)
    dragIndex.current = index
    setOptionalBlocks(next)
  }

  function handleDragEnd() {
    dragIndex.current = null
  }

  async function handleLogoChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    setLogoUploading(true)
    setError(null)
    try {
      const body = new FormData()
      body.append('file', file)
      const headers: Record<string, string> = {}
      const token = localStorage.getItem('access_token')
      if (token) headers.Authorization = `Bearer ${token}`
      const res = await fetch(`${API_BASE_URL}/profile/logo`, { method: 'POST', headers, body })
      if (!res.ok) {
        const detail = await res.json().catch(() => ({}))
        throw new ApiError(res.status, detail.detail ?? 'Could not upload logo.')
      }
      setHasLogo(true)
      // Force a preview refresh now that the logo exists.
      setTheme((t) => ({ ...t }))
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not upload logo.')
    } finally {
      setLogoUploading(false)
      if (logoInputRef.current) logoInputRef.current.value = ''
    }
  }

  async function handleSave() {
    setSaving(true)
    setError(null)
    try {
      const body = { name, theme, blocks: blocksArray() }
      if (id) {
        await api.put(`/templates/${id}`, body)
      } else {
        await api.post('/templates', body)
      }
      navigate('/settings/profile')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not save template.')
    } finally {
      setSaving(false)
    }
  }

  if (!loaded) return <p className="text-body-sm text-mute">Loading…</p>

  const fileInputClass =
    'text-body-sm text-mute file:mr-3 file:h-8 file:rounded-md file:border file:border-ink file:bg-canvas file:px-3 file:text-body-sm file:font-medium'

  return (
    <div className="flex flex-col gap-6">
      <h1 className="font-display text-display-sm text-ink">{id ? 'Edit template' : 'New template'}</h1>
      <div className="grid grid-cols-1 items-start gap-4 lg:grid-cols-[260px_1fr_300px]">
        <Card>
          <CardHeader>
            <CardTitle className="font-display text-display-xs font-semibold text-ink">Blocks</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            <p className="text-body-sm text-mute">
              Required on every invoice — your client's accountant needs these fields.
            </p>
            <ul className="flex flex-col gap-2">
              <li
                className="flex items-center gap-2 rounded-md border border-divider bg-canvas-soft px-3 py-2 text-body-sm text-mute"
                title="Required on every invoice — your client's accountant needs these fields."
              >
                <Lock size={14} className="shrink-0" />
                Supplier, invoice details, bill-to, line items, totals
              </li>
            </ul>
            <p className="text-body-sm text-mute">Optional — drag to reorder, toggle to show or hide.</p>
            <ul className="flex flex-col gap-2">
              {optionalBlocks.map((b, i) => (
                <li
                  key={b.key}
                  className="flex cursor-grab items-center gap-2 rounded-md border border-divider px-3 py-2"
                  draggable
                  onDragStart={() => handleDragStart(i)}
                  onDragOver={(e) => handleDragOver(e, i)}
                  onDragEnd={handleDragEnd}
                >
                  <GripVertical size={14} className="shrink-0 text-mute" />
                  <label className="flex flex-1 items-center gap-2 text-body-sm text-ink">
                    <input
                      type="checkbox"
                      className="size-4 accent-ink"
                      checked={b.enabled}
                      onChange={(e) => {
                        const next = [...optionalBlocks]
                        next[i] = { ...next[i], enabled: e.target.checked }
                        setOptionalBlocks(next)
                      }}
                    />
                    {OPTIONAL_BLOCK_LABELS[b.key]}
                  </label>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>

        <Card className="min-h-[500px]">
          <CardHeader>
            <CardTitle className="font-display text-display-xs font-semibold text-ink">Preview</CardTitle>
          </CardHeader>
          <CardContent>
            {previewUrl ? (
              <iframe title="Template preview" src={previewUrl} className="h-[700px] w-full rounded-md border border-divider" />
            ) : (
              <p className="text-body-sm text-mute">Rendering…</p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="font-display text-display-xs font-semibold text-ink">Theme</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <Label>Name</Label>
              <Input value={name} onChange={(e) => setName(e.target.value)} required />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label>Accent colour</Label>
              <input
                type="color"
                className="h-9 w-16 rounded-md border border-ink bg-canvas"
                value={theme.accent_color}
                onChange={(e) => setTheme({ ...theme, accent_color: e.target.value })}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label>Font size ({Math.round(theme.font_scale * 100)}%)</Label>
              <input
                type="range"
                className="accent-ink"
                min={0.85}
                max={1.15}
                step={0.05}
                value={theme.font_scale}
                onChange={(e) => setTheme({ ...theme, font_scale: Number(e.target.value) })}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label>Margins ({theme.margins_mm}mm)</Label>
              <input
                type="range"
                className="accent-ink"
                min={12}
                max={30}
                step={1}
                value={theme.margins_mm}
                onChange={(e) => setTheme({ ...theme, margins_mm: Number(e.target.value) })}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label>Logo position</Label>
              <select
                className="h-9 rounded-md border border-ink bg-canvas px-3 text-body-sm"
                value={theme.logo_position}
                onChange={(e) => setTheme({ ...theme, logo_position: e.target.value as Theme['logo_position'] })}
              >
                <option value="top_left">Top left</option>
                <option value="top_center">Top centre</option>
                <option value="top_right">Top right</option>
                <option value="none">Hidden</option>
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label>Logo</Label>
              {hasLogo === false && <p className="text-body-sm text-mute">No logo uploaded yet.</p>}
              <input ref={logoInputRef} type="file" accept="image/png,image/jpeg,image/gif" onChange={handleLogoChange} className={fileInputClass} />
              {logoUploading && <p className="text-body-sm text-mute">Uploading…</p>}
            </div>

            {error && <p className="text-body-sm text-negative">{error}</p>}
            <div className="flex gap-2">
              <Button type="button" disabled={saving} onClick={handleSave}>
                {saving ? 'Saving…' : 'Save template'}
              </Button>
              <Button type="button" variant="outline" onClick={() => navigate('/settings/profile')}>
                Cancel
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
