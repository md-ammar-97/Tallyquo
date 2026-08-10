import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { API_BASE_URL, api, ApiError } from '../api'

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

  if (!loaded) return <p className="caption">Loading…</p>

  return (
    <div>
      <h1>{id ? 'Edit template' : 'New template'}</h1>
      <div className="editor-layout">
        <div className="block">
          <div className="block-header">
            <h2>Blocks</h2>
          </div>
          <div className="block-body">
            <p className="caption" style={{ marginBottom: 12 }}>
              Required on every invoice — your client's accountant needs these fields.
            </p>
            <ul className="block-list">
              <li className="block-list-item locked">
                <span title="Required on every invoice — your client's accountant needs these fields.">
                  🔒 Supplier, invoice details, bill-to, line items, totals
                </span>
              </li>
            </ul>
            <p className="caption" style={{ margin: '16px 0 8px' }}>
              Optional — drag to reorder, toggle to show or hide.
            </p>
            <ul className="block-list">
              {optionalBlocks.map((b, i) => (
                <li
                  key={b.key}
                  className="block-list-item"
                  draggable
                  onDragStart={() => handleDragStart(i)}
                  onDragOver={(e) => handleDragOver(e, i)}
                  onDragEnd={handleDragEnd}
                >
                  <span className="drag-handle">⠿</span>
                  <label style={{ flex: 1 }}>
                    <input
                      type="checkbox"
                      style={{ width: 'auto', marginRight: 8 }}
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
          </div>
        </div>

        <div className="block editor-preview">
          <div className="block-header">
            <h2>Preview</h2>
          </div>
          <div className="block-body">
            {previewUrl ? (
              <iframe title="Template preview" src={previewUrl} className="preview-frame" />
            ) : (
              <p className="caption">Rendering…</p>
            )}
          </div>
        </div>

        <div className="block">
          <div className="block-header">
            <h2>Theme</h2>
          </div>
          <div className="block-body">
            <div className="field">
              <label>Name</label>
              <input value={name} onChange={(e) => setName(e.target.value)} required />
            </div>
            <div className="field">
              <label>Accent colour</label>
              <input
                type="color"
                value={theme.accent_color}
                onChange={(e) => setTheme({ ...theme, accent_color: e.target.value })}
              />
            </div>
            <div className="field">
              <label>Font size ({Math.round(theme.font_scale * 100)}%)</label>
              <input
                type="range"
                min={0.85}
                max={1.15}
                step={0.05}
                value={theme.font_scale}
                onChange={(e) => setTheme({ ...theme, font_scale: Number(e.target.value) })}
              />
            </div>
            <div className="field">
              <label>Margins ({theme.margins_mm}mm)</label>
              <input
                type="range"
                min={12}
                max={30}
                step={1}
                value={theme.margins_mm}
                onChange={(e) => setTheme({ ...theme, margins_mm: Number(e.target.value) })}
              />
            </div>
            <div className="field">
              <label>Logo position</label>
              <select
                value={theme.logo_position}
                onChange={(e) => setTheme({ ...theme, logo_position: e.target.value as Theme['logo_position'] })}
              >
                <option value="top_left">Top left</option>
                <option value="top_center">Top centre</option>
                <option value="top_right">Top right</option>
                <option value="none">Hidden</option>
              </select>
            </div>
            <div className="field">
              <label>Logo</label>
              {hasLogo === false && <p className="caption">No logo uploaded yet.</p>}
              <input ref={logoInputRef} type="file" accept="image/png,image/jpeg,image/gif" onChange={handleLogoChange} />
              {logoUploading && <p className="caption">Uploading…</p>}
            </div>

            {error && <p className="error-text">{error}</p>}
            <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
              <button type="button" className="primary" disabled={saving} onClick={handleSave}>
                {saving ? 'Saving…' : 'Save template'}
              </button>
              <button type="button" onClick={() => navigate('/settings/profile')}>
                Cancel
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
