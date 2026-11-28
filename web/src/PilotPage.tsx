import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import type { User } from 'oidc-client-ts'
import { beginOidcSignIn, completeOidcSignIn, endOidcSession, oidcConfigured, readOidcUser } from './pilotAuth'

type Workspace = { id: string; name: string; role: 'owner' | 'editor' | 'viewer' }
type Incident = {
  id: string; incident_key: string; title: string; severity: string; summary: string; status: string
  workspace_id: string; started_at: string; service: { id: string; name: string; owner_team: string }
  signal_counts: Record<string, number>; missing_signals: string[]
}
type TimelineEvent = {
  evidence_id: string; kind: string; source: string; service_id: string; occurred_at: string
  title: string; summary: string; payload: Record<string, unknown>
}
type Hypothesis = {
  id: string; rank: number; statement: string; confidence: string; confidence_note: string
  supporting_evidence_ids: string[]; contradicting_evidence_ids: string[]; next_read_only_check: string
  mitigation?: { id: string; summary: string }
}
type Report = {
  id: string; incident_id: string; workspace_id: string; source: string; analysis_mode: string
  model_call_made: boolean; evidence_snapshot_id: string; evidence_snapshot_sha256: string
  captured_evidence_count: number; evidence_gaps: string[]; uncertainty: string; hypotheses: Hypothesis[]
  simulation_only: boolean; external_action_performed: boolean; created_at?: string
}
type Evidence = {
  evidence_id: string; kind: string; source: string; service_id: string; observed_at: string
  snapshot_id: string; snapshot_sha256: string; payload: Record<string, unknown>
}
type Member = { subject: string; role: 'owner' | 'editor' | 'viewer' }
type AuditEvent = { id: string; subject: string; action: string; entity_type: string; entity_id: string; occurred_at: string }

const API_BASE = (import.meta.env.VITE_API_BASE_URL || '/api/v1').replace(/\/$/, '')
const DEV_USERS = [
  'pilot.payments.owner', 'pilot.payments.editor', 'pilot.payments.viewer',
  'pilot.platform.owner', 'pilot.platform.editor', 'pilot.platform.viewer',
]
const DEV_MODE = import.meta.env.DEV || import.meta.env.VITE_PILOT_DEV_AUTH === 'true'

function localSubject() {
  try { return window.sessionStorage.getItem('incident-atlas:pilot-dev-subject') ?? '' } catch { return '' }
}

function usePilotRequest(user: User | null, subject: string) {
  return useCallback(async <T,>(path: string, init: RequestInit = {}): Promise<T> => {
    const headers = new Headers(init.headers)
    headers.set('Accept', 'application/json, application/problem+json')
    if (user?.access_token) headers.set('Authorization', `Bearer ${user.access_token}`)
    else if (subject) headers.set('X-Atlas-Dev-User', subject)
    if (init.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json')
    const response = await fetch(`${API_BASE}${path}`, { ...init, headers, credentials: 'omit' })
    const body = await response.json().catch(() => ({})) as Record<string, unknown>
    if (!response.ok) {
      const detail = typeof body.detail === 'string' ? body.detail : `Request failed with HTTP ${response.status}.`
      const code = typeof body.code === 'string' ? ` (${body.code})` : ''
      throw new Error(`${detail}${code}`)
    }
    return body as T
  }, [user, subject])
}

function dateTime(value: string) {
  return new Intl.DateTimeFormat('en', { dateStyle: 'medium', timeStyle: 'medium', timeZone: 'UTC' }).format(new Date(value)) + ' UTC'
}

function eventSourceLabel(event: TimelineEvent) {
  if (event.source === 'synthetic_fixture') return 'synthetic fixture'
  if (event.source === 'github' && event.payload.integration_source === 'exercise_fixture') return 'synthetic GitHub event'
  if (event.source === 'github') return 'GitHub deployment'
  return `ingested ${event.kind}`
}

export default function PilotPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [user, setUser] = useState<User | null>(null)
  const [subject, setSubject] = useState(localSubject)
  const [subjectInput, setSubjectInput] = useState(localSubject)
  const [workspaces, setWorkspaces] = useState<Workspace[]>([])
  const [workspaceId, setWorkspaceId] = useState(searchParams.get('workspace') ?? '')
  const [incidents, setIncidents] = useState<Incident[]>([])
  const [incidentId, setIncidentId] = useState('')
  const [timeline, setTimeline] = useState<TimelineEvent[]>([])
  const [members, setMembers] = useState<Member[]>([])
  const [audit, setAudit] = useState<AuditEvent[]>([])
  const [reports, setReports] = useState<Report[]>([])
  const [report, setReport] = useState<Report | null>(null)
  const [reportOrigin, setReportOrigin] = useState<'fresh' | 'stored' | null>(null)
  const [evidence, setEvidence] = useState<Evidence | null>(null)
  const [ownerTeam, setOwnerTeam] = useState('')
  const [memberSubject, setMemberSubject] = useState('')
  const [memberRole, setMemberRole] = useState<Member['role']>('viewer')
  const [loading, setLoading] = useState(false)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const callbackStarted = useRef(false)
  const request = usePilotRequest(user, subject)
  const authenticated = Boolean(user?.access_token || subject)
  const selectedWorkspace = workspaces.find(item => item.id === workspaceId)
  const selectedIncident = incidents.find(item => item.id === incidentId)
  const requestedWorkspace = searchParams.get('workspace')

  useEffect(() => {
    let active = true
    async function initialize() {
      if (window.location.pathname === '/pilot/callback' && oidcConfigured && !callbackStarted.current) {
        callbackStarted.current = true
        try { await completeOidcSignIn(); window.location.assign('/pilot') }
        catch (failure) { if (active) setError(failure instanceof Error ? failure.message : 'Sign-in could not be completed.') }
        return
      }
      if (oidcConfigured) {
        try { const value = await readOidcUser(); if (active) setUser(value) }
        catch { if (active) setError('The saved sign-in session could not be read.') }
      }
    }
    void initialize()
    return () => { active = false }
  }, [])

  useEffect(() => {
    if (!authenticated) { setWorkspaces([]); setWorkspaceId(''); return }
    let active = true
    setLoading(true)
    setError('')
    void request<{ items: Workspace[] }>('/pilot/workspaces').then(result => {
      if (!active) return
      setWorkspaces(result.items)
      const next = result.items.some(item => item.id === requestedWorkspace) ? requestedWorkspace! : result.items[0]?.id ?? ''
      setWorkspaceId(next)
      if (next) setSearchParams({ workspace: next }, { replace: true })
    }).catch(failure => { if (active) setError(failure instanceof Error ? failure.message : 'Workspaces could not be loaded.') })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [authenticated, request, requestedWorkspace, setSearchParams])

  useEffect(() => {
    if (!workspaceId) { setIncidents([]); setMembers([]); return }
    let active = true
    setLoading(true)
    setError('')
    const root = `/pilot/workspaces/${encodeURIComponent(workspaceId)}`
    void Promise.all([
      request<{ items: Incident[] }>(`${root}/incidents`),
      request<{ items: Member[] }>(`${root}/members`),
      request<{ items: AuditEvent[] }>(`${root}/audit`),
    ]).then(([incidentResult, memberResult, auditResult]) => {
      if (!active) return
      setIncidents(incidentResult.items)
      setMembers(memberResult.items)
      setAudit(auditResult.items)
      const nextIncident = incidentResult.items.some(item => item.id === incidentId) ? incidentId : incidentResult.items[0]?.id ?? ''
      setIncidentId(nextIncident)
    }).catch(failure => { if (active) setError(failure instanceof Error ? failure.message : 'Workspace data could not be loaded.') })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [workspaceId, request])

  const loadIncidentResources = useCallback(async () => {
    if (!workspaceId || !incidentId) return
    const root = `/pilot/workspaces/${encodeURIComponent(workspaceId)}/incidents/${encodeURIComponent(incidentId)}`
    setError('')
    try {
      const [timelineResult, reportResult] = await Promise.all([
        request<{ items: TimelineEvent[] }>(`${root}/timeline`),
        request<{ items: Report[] }>(`${root}/reports`),
      ])
      setTimeline(timelineResult.items)
      setReports(reportResult.items)
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'Incident evidence could not be loaded.') }
  }, [workspaceId, incidentId, request])

  useEffect(() => { void loadIncidentResources() }, [loadIncidentResources])

  const setDevIdentity = () => {
    const value = subjectInput.trim()
    if (!DEV_USERS.includes(value)) { setError('Choose one of the seeded local exercise identities.'); return }
    try { window.sessionStorage.setItem('incident-atlas:pilot-dev-subject', value) } catch { /* The current tab identity remains usable. */ }
    setSubject(value)
    setError('')
  }

  const signOut = async () => {
    await endOidcSession()
    try { window.sessionStorage.removeItem('incident-atlas:pilot-dev-subject') } catch { /* Continue in-memory. */ }
    setUser(null); setSubject(''); setWorkspaces([]); setWorkspaceId(''); setReport(null); setEvidence(null)
  }

  const chooseWorkspace = (value: string) => {
    setWorkspaceId(value)
    setSearchParams(value ? { workspace: value } : {})
    setIncidentId(''); setTimeline([]); setReport(null); setEvidence(null)
  }

  const openReport = async (item: Report, origin: 'fresh' | 'stored') => {
    setReport(item); setReportOrigin(origin); setEvidence(null)
    if (origin === 'stored' && workspaceId) {
      try { const saved = await request<Report>(`/pilot/workspaces/${encodeURIComponent(workspaceId)}/reports/${encodeURIComponent(item.id)}`); setReport(saved) }
      catch (failure) { setError(failure instanceof Error ? failure.message : 'Saved report could not be opened.') }
    }
  }

  const investigate = async () => {
    if (!selectedWorkspace || !selectedIncident) return
    setBusy('investigate'); setError(''); setNotice('')
    try {
      const result = await request<Report>(`/pilot/workspaces/${encodeURIComponent(workspaceId)}/incidents/${encodeURIComponent(incidentId)}/investigations`, { method: 'POST', body: '{}' })
      setReport(result); setReportOrigin('fresh'); setEvidence(null); setNotice('A fresh rules-baseline report was saved against an immutable evidence snapshot.')
      await loadIncidentResources()
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'The investigation could not be completed.') }
    finally { setBusy('') }
  }

  const openCitation = async (evidenceId: string) => {
    if (!workspaceId || !report) return
    setBusy(`evidence:${evidenceId}`); setError('')
    try {
      const item = await request<Evidence>(`/pilot/workspaces/${encodeURIComponent(workspaceId)}/snapshots/${encodeURIComponent(report.evidence_snapshot_id)}/evidence/${encodeURIComponent(evidenceId)}`)
      setEvidence(item)
    } catch (failure) { setEvidence(null); setError(failure instanceof Error ? failure.message : 'The citation could not be resolved.') }
    finally { setBusy('') }
  }

  const refreshAudit = async () => {
    if (!workspaceId) return
    try {
      const result = await request<{ items: AuditEvent[] }>(`/pilot/workspaces/${encodeURIComponent(workspaceId)}/audit`)
      setAudit(result.items)
    } catch { /* The successful operation remains visible; the next refresh can reload audit rows. */ }
  }

  const updateRole = async (target: Member, role: Member['role']) => {
    setBusy(`member:${target.subject}`); setError('')
    try {
      await request(`/pilot/workspaces/${encodeURIComponent(workspaceId)}/members/${encodeURIComponent(target.subject)}`, { method: 'PUT', body: JSON.stringify({ role }) })
      const result = await request<{ items: Member[] }>(`/pilot/workspaces/${encodeURIComponent(workspaceId)}/members`)
      setMembers(result.items); setNotice(`Updated ${target.subject} to ${role}. New permissions apply on the next request.`)
      await refreshAudit()
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'The role change failed.') }
    finally { setBusy('') }
  }

  const removeMember = async (target: Member) => {
    if (!window.confirm(`Remove ${target.subject} from this workspace?`)) return
    setBusy(`member:${target.subject}`); setError('')
    try {
      await request(`/pilot/workspaces/${encodeURIComponent(workspaceId)}/members/${encodeURIComponent(target.subject)}`, { method: 'DELETE' })
      const result = await request<{ items: Member[] }>(`/pilot/workspaces/${encodeURIComponent(workspaceId)}/members`)
      setMembers(result.items); setNotice(`Removed ${target.subject}. Access is revoked on the next request.`)
      await refreshAudit()
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'The member could not be removed.') }
    finally { setBusy('') }
  }

  const addMember = async () => {
    if (!memberSubject.trim()) return
    setBusy('add-member'); setError('')
    try {
      await request(`/pilot/workspaces/${encodeURIComponent(workspaceId)}/members/${encodeURIComponent(memberSubject.trim())}`, { method: 'PUT', body: JSON.stringify({ role: memberRole }) })
      const result = await request<{ items: Member[] }>(`/pilot/workspaces/${encodeURIComponent(workspaceId)}/members`)
      setMembers(result.items); setMemberSubject(''); setNotice('Workspace access was updated and recorded in the audit trail.')
      await refreshAudit()
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'The member could not be added.') }
    finally { setBusy('') }
  }

  const changeOwner = async () => {
    if (!selectedIncident || !ownerTeam.trim()) return
    setBusy('owner'); setError('')
    try {
      await request(`/pilot/workspaces/${encodeURIComponent(workspaceId)}/services/${encodeURIComponent(selectedIncident.service.id)}/owner`, { method: 'PATCH', body: JSON.stringify({ owner_team: ownerTeam.trim() }) })
      setNotice(`Service ownership changed to ${ownerTeam.trim()} and was recorded in the audit trail.`)
      setOwnerTeam('')
      const result = await request<{ items: Incident[] }>(`/pilot/workspaces/${encodeURIComponent(workspaceId)}/incidents`)
      setIncidents(result.items)
      await refreshAudit()
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'Service ownership could not be changed.') }
    finally { setBusy('') }
  }

  const confidenceTone = useMemo(() => report?.hypotheses[0]?.confidence ?? 'none', [report])
  const pilotEnabled = import.meta.env.VITE_PILOT_ENABLED === 'true' || import.meta.env.DEV

  if (!pilotEnabled) return <div className="page-wrap pilot-page"><header className="page-title-row"><div><div className="eyebrow">TEAM WORKSPACE PILOT</div><h1>Workspace pilot is not enabled</h1><p className="page-description">The public static demo is still available. Enable the separate pilot API and OIDC configuration to open team workspaces.</p></div></header></div>

  return <div className="page-wrap pilot-page">
    <header className="page-title-row"><div><div className="eyebrow">AUTHENTICATED · WORKSPACE PILOT</div><h1>Evidence handoff</h1><p className="page-description">One shared incident timeline, scoped to your team. New telemetry, saved reports, and local exercise fixtures are labeled at the source.</p></div><div className="pilot-title-actions">{authenticated && <span className="pilot-role">{selectedWorkspace?.role ?? 'member'}</span>}{authenticated && <button className="button button-secondary" onClick={() => void signOut()}>Sign out</button>}</div></header>
    {!authenticated ? <section className="pilot-auth-card" aria-labelledby="pilot-auth-title">
      <div><span className="eyebrow">PRIVATE WORKSPACES</span><h2 id="pilot-auth-title">Sign in to continue</h2><p>Workspace data is checked against a server-side membership on every request. The public synthetic demo does not require this sign-in.</p></div>
      {oidcConfigured ? <button className="button button-primary" onClick={() => void beginOidcSignIn().catch(failure => setError(failure instanceof Error ? failure.message : 'Sign-in could not start.'))}>Sign in with identity provider</button> : DEV_MODE ? <div className="pilot-dev-login"><label>Local seeded identity<select value={subjectInput} onChange={event => setSubjectInput(event.target.value)}>{DEV_USERS.map(item => <option key={item}>{item}</option>)}</select></label><button className="button button-primary" onClick={setDevIdentity}>Open local exercise workspace</button><small>Development-only identity switch. The API rejects this header in production.</small></div> : <div className="pilot-auth-error">OIDC sign-in is not configured for this deployment.</div>}
    </section> : <>
      {error && <div className="pilot-alert pilot-alert-error" role="alert"><strong>Request failed</strong><span>{error}</span><button onClick={() => setError('')} aria-label="Dismiss error">×</button></div>}
      {notice && <div className="pilot-alert pilot-alert-success" role="status"><strong>Updated</strong><span>{notice}</span><button onClick={() => setNotice('')} aria-label="Dismiss notice">×</button></div>}
      {loading && <p className="pilot-loading" role="status">Loading workspace data…</p>}
      <div className="pilot-toolbar">
        <label>Workspace<select value={workspaceId} onChange={event => chooseWorkspace(event.target.value)}>{workspaces.map(item => <option key={item.id} value={item.id}>{item.name} · {item.role}</option>)}</select></label>
        <label>Incident<select value={incidentId} onChange={event => { setIncidentId(event.target.value); setReport(null); setEvidence(null) }}>{incidents.map(item => <option key={item.id} value={item.id}>{item.title}</option>)}</select></label>
        <button className="button button-secondary" onClick={() => void loadIncidentResources()} disabled={!incidentId}>Refresh evidence</button>
      </div>
      {selectedIncident && <>
        <section className="pilot-incident-card">
          <div className="pilot-incident-head"><div><div className="pilot-chip-row"><span className="pilot-chip pilot-chip-severity">{selectedIncident.severity}</span><span className="pilot-chip">{selectedIncident.status}</span><span className="pilot-chip">OWNER · {selectedIncident.service.owner_team}</span></div><h2>{selectedIncident.title}</h2><p>{selectedIncident.summary}</p></div><div className="pilot-incident-actions">{selectedWorkspace?.role !== 'viewer' && <button className="button button-primary" onClick={() => void investigate()} disabled={busy !== ''}>{busy === 'investigate' ? 'Capturing evidence…' : 'Open investigation'}</button>}</div></div>
          <div className="pilot-coverage"><strong>Evidence coverage</strong><span>{Object.entries(selectedIncident.signal_counts).map(([key, count]) => <span className="pilot-coverage-item" key={key}>{key} <b>{count}</b></span>)}</span><p>{selectedIncident.missing_signals.length ? `Missing signals: ${selectedIncident.missing_signals.join(', ')}.` : 'Metrics, logs, traces, and deployment events are present.'}</p></div>
        </section>

        {selectedWorkspace?.role === 'owner' && <section className="pilot-admin-grid">
          <div className="pilot-panel"><div className="pilot-panel-heading"><div><span className="eyebrow">ACCESS CONTROL</span><h2>Workspace members</h2></div><span>{members.length} members</span></div><div className="pilot-member-list">{members.map(member => <div className="pilot-member-row" key={member.subject}><code>{member.subject}</code><select value={member.role} disabled={busy === `member:${member.subject}`} onChange={event => void updateRole(member, event.target.value as Member['role'])} aria-label={`Role for ${member.subject}`}><option value="owner">Owner</option><option value="editor">Editor</option><option value="viewer">Viewer</option></select><button className="button button-secondary pilot-remove-member" onClick={() => void removeMember(member)} disabled={busy === `member:${member.subject}`}>Remove</button></div>)}</div><div className="pilot-add-member"><input value={memberSubject} onChange={event => setMemberSubject(event.target.value)} placeholder="OIDC subject identifier" aria-label="OIDC subject identifier"/><select value={memberRole} onChange={event => setMemberRole(event.target.value as Member['role'])} aria-label="New member role"><option value="viewer">Viewer</option><option value="editor">Editor</option><option value="owner">Owner</option></select><button className="button button-secondary" onClick={() => void addMember()} disabled={busy === 'add-member'}>Add member</button></div></div>
          <div className="pilot-panel"><div className="pilot-panel-heading"><div><span className="eyebrow">SERVICE OWNERSHIP</span><h2>{selectedIncident.service.name}</h2></div><span className="pilot-owner-team">{selectedIncident.service.owner_team}</span></div><p>Ownership is workspace-scoped. Changing the responsible team is recorded in the audit trail.</p><div className="pilot-add-member"><input value={ownerTeam} onChange={event => setOwnerTeam(event.target.value)} placeholder="New owner team" aria-label="New service owner team"/><button className="button button-secondary" onClick={() => void changeOwner()} disabled={busy === 'owner'}>Update owner</button></div></div>
          <div className="pilot-panel"><div className="pilot-panel-heading"><div><span className="eyebrow">AUDIT TRAIL</span><h2>Recent workspace changes</h2></div><span>{audit.length} events</span></div>{audit.length === 0 ? <div className="pilot-empty"><p>No recorded changes yet.</p></div> : <div className="pilot-audit-list">{audit.slice(0, 12).map(item => <div className="pilot-audit-row" key={item.id}><div><strong>{item.action.replaceAll('_', ' ')}</strong><small>{item.subject} · {item.entity_type} {item.entity_id}</small></div><time>{dateTime(item.occurred_at)}</time></div>)}</div>}</div>
        </section>}

        <div className="pilot-content-grid">
          <section className="pilot-panel" aria-labelledby="pilot-timeline-title"><div className="pilot-panel-heading"><div><span className="eyebrow">SHARED INCIDENT RECORD</span><h2 id="pilot-timeline-title">Timeline</h2></div><span>{timeline.length} records</span></div>
            {timeline.length === 0 ? <div className="pilot-empty"><strong>No telemetry has arrived yet.</strong><p>Run the controlled exercise to send synthetic OpenTelemetry and a signed GitHub-style deployment event.</p></div> : <div className="pilot-timeline">{timeline.map(event => <article className="pilot-event" key={event.evidence_id}><div className="pilot-event-top"><time>{dateTime(event.occurred_at)}</time><span className={`pilot-chip ${event.source === 'synthetic_fixture' ? 'pilot-chip-synthetic' : ''}`}>{eventSourceLabel(event)}</span></div><h3>{event.title}</h3><p>{event.summary}</p><button className="pilot-citation" onClick={() => { if (report) void openCitation(event.evidence_id); else setNotice('Open an investigation to capture this record in a stable, report-linked evidence snapshot.') }}>{event.evidence_id}</button></article>)}</div>}
          </section>
          <section className="pilot-panel" aria-labelledby="pilot-reports-title"><div className="pilot-panel-heading"><div><span className="eyebrow">SAVED INVESTIGATIONS</span><h2 id="pilot-reports-title">Reports</h2></div><span>{reports.length}</span></div>
            {reports.length === 0 ? <div className="pilot-empty"><strong>No saved reports yet.</strong><p>A fresh rules-baseline run captures this timeline before analysis and keeps every citation resolvable.</p></div> : <div className="pilot-report-list">{reports.map(item => <button key={item.id} className={`pilot-report-row ${report?.id === item.id ? 'active' : ''}`} onClick={() => void openReport(item, 'stored')}><span>{item.source === 'rules_fresh_analysis' ? 'Rules baseline' : 'Stored report'} · {item.hypotheses.length ? `${item.hypotheses.length} hypotheses` : 'abstained'}</span><small>{item.id}</small></button>)}</div>}
            {report && <article className="pilot-report-detail"><div className="pilot-report-labels"><span className="pilot-chip">{reportOrigin === 'stored' ? 'STORED REPORT' : 'FRESH ANALYSIS'}</span><span className="pilot-chip">RULES BASELINE</span><span className="pilot-chip">MODEL CALL · NO</span></div><h3>{report.hypotheses.length ? 'Evidence-backed hypothesis' : 'Rules baseline abstained'}</h3><p className="pilot-report-uncertainty">{report.uncertainty}</p>{report.evidence_gaps.length > 0 && <p className="pilot-gaps"><strong>Evidence gaps:</strong> {report.evidence_gaps.join(', ')}.</p>}{report.hypotheses.map(hypothesis => <div className="pilot-hypothesis" key={hypothesis.id}><div className="pilot-hypothesis-head"><strong>H{hypothesis.rank} · {hypothesis.confidence} confidence</strong><span className={`pilot-chip confidence-${confidenceTone}`}>{hypothesis.confidence}</span></div><p>{hypothesis.statement}</p><p className="pilot-confidence-note">{hypothesis.confidence_note}</p><div className="pilot-citations"><strong>Supporting evidence</strong>{hypothesis.supporting_evidence_ids.map(id => <button className="pilot-citation" key={id} onClick={() => void openCitation(id)} disabled={busy === `evidence:${id}`}>{busy === `evidence:${id}` ? 'Resolving…' : id}</button>)}</div><p className="pilot-next-check"><strong>Next read-only check:</strong> {hypothesis.next_read_only_check}</p><div className="pilot-sim-note">{hypothesis.mitigation?.summary ?? 'No mitigation proposed.'} Approval and remediation actions are not available in this pilot.</div></div>)}<div className="pilot-snapshot-stamp"><span>Snapshot <code>{report.evidence_snapshot_id}</code></span><span>SHA-256 <code>{report.evidence_snapshot_sha256}</code></span><span>{report.captured_evidence_count} captured records</span></div></article>}
            {evidence && <article className="pilot-evidence-detail"><div className="pilot-panel-heading"><div><span className="eyebrow">{evidence.source.toUpperCase()} · {evidence.kind.toUpperCase()}</span><h3>{String(evidence.payload.title ?? evidence.payload.metric_name ?? evidence.payload.operation ?? evidence.payload.message ?? evidence.evidence_id)}</h3></div><button className="pilot-close" onClick={() => setEvidence(null)} aria-label="Close evidence detail">×</button></div><p>{dateTime(evidence.observed_at)} · {evidence.service_id}</p><pre>{JSON.stringify(evidence.payload, null, 2)}</pre><small>Resolved from captured snapshot {evidence.snapshot_id} · SHA-256 {evidence.snapshot_sha256}</small></article>}
          </section>
        </div>
        <footer className="pilot-data-note"><span>Retention: telemetry, report snapshots, and saved reports expire after 30 days by default (operator setting: 7–365 days). Audit events are retained for 365 days.</span><span>All changes are tenant-scoped and audited. Mitigations remain simulation-only.</span></footer>
      </>}
    </>}
  </div>
}
