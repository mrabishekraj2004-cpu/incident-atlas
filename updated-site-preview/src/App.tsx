import { createContext, useContext, useEffect, useMemo, useRef, useState } from 'react'
import { Link, Navigate, NavLink, Outlet, Route, Routes, useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { dataClient, dataMode } from './dataClient'
import { ApiClientError } from './apiClient'
import { canRunLiveInvestigation, evidenceLinkPath, reportPath as investigationPath } from './uiContracts'
import type { ApprovalResponse, Confidence, DemoCapabilities, DependenciesResponse, EvidenceItemOut, IncidentCard, IncidentDetail as IncidentDetailType, InvestigationReport, LogEventOut, MetricPointOut, Source, SpanOut, TelemetryKind, TimelineEventOut } from './contracts'
import { useResource, type Resource } from './useResource'
import { AccountProvider, LoginPage, RegisterPage, ThemeProvider, useAccount, useTheme } from './account'

const CapabilitiesContext = createContext<Resource<DemoCapabilities> & { retry: () => void }>({ status: 'loading', retry: () => undefined })

function Icon({ name, size = 18 }: { name: 'atlas' | 'grid' | 'book' | 'chevron' | 'arrow' | 'clock' | 'activity' | 'trace' | 'file' | 'server' | 'check' | 'external' | 'search' | 'alert' | 'arrowUp' | 'arrowDown' | 'settings' | 'user' | 'logout' | 'bell' | 'sun' | 'moon'; size?: number }) {
  const common = { width: size, height: size, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 1.8, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const, 'aria-hidden': true as const }
  const paths: Record<typeof name, React.ReactNode> = {
    atlas: <><circle cx="12" cy="12" r="9"/><path d="M3.5 9h17M3.5 15h17M12 3c2.4 2.5 3.5 5.5 3.5 9s-1.1 6.5-3.5 9c-2.4-2.5-3.5-5.5-3.5-9S9.6 5.5 12 3Z"/></>,
    grid: <><rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/></>,
    book: <><path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v17H6.5A2.5 2.5 0 0 0 4 22z"/><path d="M4 5.5v14A2.5 2.5 0 0 1 6.5 17H20M8 7h8M8 10h8"/></>,
    chevron: <path d="m9 18 6-6-6-6"/>, arrow: <><path d="M5 12h14"/><path d="m13 6 6 6-6 6"/></>, clock: <><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></>,
    activity: <><path d="M3 12h4l3-8 4 16 3-8h4"/></>, trace: <><path d="M6 4v5a3 3 0 0 0 3 3h6a3 3 0 0 1 3 3v5"/><circle cx="6" cy="4" r="2"/><circle cx="18" cy="20" r="2"/><circle cx="18" cy="4" r="2"/><path d="M18 6v3a3 3 0 0 1-3 3h-1"/></>,
    file: <><path d="M13 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V10z"/><path d="M13 3v7h7M8 14h8M8 17h6"/></>, server: <><rect x="3" y="4" width="18" height="7" rx="2"/><rect x="3" y="13" width="18" height="7" rx="2"/><path d="M7 7.5h.01M7 16.5h.01M11 7.5h6M11 16.5h6"/></>,
    check: <><path d="m5 12 4 4L19 6"/></>, external: <><path d="M14 4h6v6M20 4 11 13"/><path d="M18 13v5a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h5"/></>,
    search: <><circle cx="10.8" cy="10.8" r="6.8"/><path d="m16 16 4.5 4.5"/></>, alert: <><path d="M12 3 2.8 19h18.4L12 3Z"/><path d="M12 9v4M12 16h.01"/></>, arrowUp: <><path d="M12 19V5M6 11l6-6 6 6"/></>, arrowDown: <><path d="M12 5v14m6-6-6 6-6-6"/></>,
    settings: <><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-1.8 1.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.5v.2h-2.6v-.2a1.7 1.7 0 0 0-1-1.5 1.7 1.7 0 0 0-1.9.3l-.1.1-1.8-1.8.1-.1A1.7 1.7 0 0 0 8 15a1.7 1.7 0 0 0-1.5-1H6.3v-2.6h.2a1.7 1.7 0 0 0 1.5-1 1.7 1.7 0 0 0-.3-1.9l-.1-.1 1.8-1.8.1.1a1.7 1.7 0 0 0 1.9.3 1.7 1.7 0 0 0 1-1.5v-.2H15v.2a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.9-.3l.1-.1 1.8 1.8-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.5 1h.2V14h-.2a1.7 1.7 0 0 0-1.5 1Z"/></>,
    sun: <><circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M4.93 4.93l1.41 1.41m11.32 11.32 1.41 1.41M2 12h2m16 0h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"/></>,
    moon: <path d="M20.5 14.2A8.6 8.6 0 0 1 9.8 3.5 8.8 8.8 0 1 0 20.5 14.2Z"/>,
    user: <><circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/></>, logout: <><path d="M10 17l5-5-5-5M15 12H3"/><path d="M12 3h6a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-6"/></>, bell: <><path d="M18 9a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4"/></>,
  }
  return <svg {...common} data-icon={name}>{paths[name]}</svg>
}

function Shell() {
  const capabilities = useContext(CapabilitiesContext)
  const { theme, toggleTheme } = useTheme()
  const location = useLocation()
  const sourceLabel = dataMode === 'fixtures' ? 'Synthetic fixture preview' : 'Backend API data'
  const pageLabel = location.pathname.startsWith('/incidents/') ? 'Incident workspace' : location.pathname.startsWith('/incidents') ? 'Incident library' : location.pathname.startsWith('/investigations/') ? 'Investigation review' : location.pathname.startsWith('/methodology') ? 'Methodology' : location.pathname.startsWith('/settings') ? 'Settings' : 'Overview'
  return <div className="app-shell">
    <a className="skip-link" href="#main">Skip to content</a>
    <aside className="sidebar">
      <Link to="/" className="brand brand-wordmark"><span>INCIDENT</span><strong>Atlas</strong></Link>
      <div className="side-label">INVESTIGATE</div>
      <nav className="primary-nav" aria-label="Primary navigation">
        <NavLink to="/" end className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}><Icon name="grid" /> Overview</NavLink>
        <NavLink to="/incidents" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}><Icon name="alert" /> Incident library <span className="nav-count">03</span></NavLink>
        <NavLink to="/methodology" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}><Icon name="book" /> Methodology</NavLink>
      </nav>
      <div className="side-label side-label-preferences">PREFERENCES</div>
      <nav className="primary-nav" aria-label="Preferences navigation">
        <NavLink to="/settings" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}><Icon name="settings" /> Settings</NavLink>
      </nav>
      <div className="sidebar-spacer" />
    </aside>
    <div className="main-column">
      <header className="topbar"><div className="breadcrumb"><span className="breadcrumb-dot"/><span className="breadcrumb-home">Incident Atlas</span><Icon name="chevron" size={14} /> <span>{pageLabel}</span></div><div className="topbar-right"><span className="env-pill"><span/> {sourceLabel}</span><button className="theme-toggle" type="button" onClick={toggleTheme} aria-label={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`} title={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`}><Icon name={theme === 'light' ? 'moon' : 'sun'} size={17}/><span>{theme === 'light' ? 'Dark' : 'Light'}</span></button><AccountMenu/></div></header>
      {dataMode === 'api' && <div className="mode-status" role="status">{capabilities.status === 'loading' ? 'Checking API capabilities…' : capabilities.status === 'error' ? 'API capability check failed · live investigation remains unavailable until checked' : capabilities.data.live_ai_enabled ? `Live AI enabled · ${capabilities.data.live_label}` : `Live AI disabled · ${capabilities.data.live_label}`}</div>}
      <main id="main" tabIndex={-1}><Outlet/></main>
    </div>
  </div>
}

function AccountMenu() {
  const { user, authenticated, signOut } = useAccount()
  const navigate = useNavigate()
  if (!authenticated) return <div className="topbar-auth-actions"><Link to="/login" className="topbar-login">Sign in</Link><Link to="/register" className="topbar-register">Register</Link></div>
  return <div className="account-session"><span>{user?.name || 'Preview session'}</span><button type="button" onClick={() => { signOut(); navigate('/login') }}>Sign out</button></div>
}

function Severity({ value }: { value: string }) { return <span className={`severity severity-${value.toLowerCase().replace('-', '')}`}><i />{value}</span> }
function SourceTag({ children, tone = 'neutral' }: { children: React.ReactNode; tone?: 'neutral' | 'blue' | 'amber' | 'green' }) { return <span className={`source-tag tag-${tone}`}>{children}</span> }
function PageTitle({ eyebrow, title, description, actions }: { eyebrow: string; title: string; description: string; actions?: React.ReactNode }) { return <div className="page-title-row"><div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1><p className="page-description">{description}</p></div>{actions && <div className="title-actions">{actions}</div>}</div> }
function EmptyState({ title, body, action }: { title: string; body: string; action?: React.ReactNode }) { return <div className="empty-state"><span className="empty-icon"><Icon name="search" size={20} /></span><h3>{title}</h3><p>{body}</p>{action}</div> }
function Notice({ kind, title, children }: { kind: 'info' | 'warning' | 'error' | 'success'; title: string; children: React.ReactNode }) { return <div className={`notice notice-${kind}`} role={kind === 'error' ? 'alert' : 'status'}><span className="notice-symbol">{kind === 'success' ? <Icon name="check" size={17} /> : kind === 'warning' || kind === 'error' ? <Icon name="alert" size={17} /> : 'i'}</span><div><strong>{title}</strong><div>{children}</div></div></div> }
function LoadingState({ label = 'Loading incident data', compact = false }: { label?: string; compact?: boolean }) { return <div className={`loading-state ${compact ? 'loading-compact' : ''}`} role="status" aria-live="polite" aria-busy="true"><span className="spinner" aria-hidden="true"/><div><b>{label}</b><span>{dataMode === 'fixtures' ? 'Development fixture source' : 'Backend API · UTC timestamps'}</span></div></div> }
function ResourceError({ title, error, retry }: { title: string; error: Error; retry: () => void }) { return <div className="resource-error"><Notice kind="error" title={title}>{error.message || 'The requested data could not be loaded.'}{error instanceof ApiClientError ? ` (${error.code}; request ${error.requestId})` : ''}</Notice><button className="button button-secondary" onClick={retry}>Retry read</button></div> }

function LiveRunError({ error, onRetry }: { error: Error; onRetry: () => void }) {
  const retryDeadline = useMemo(() => error instanceof ApiClientError ? retryAfterDeadline(error.retryAfter) : null, [error])
  const [waitSeconds, setWaitSeconds] = useState(0)
  useEffect(() => {
    if (retryDeadline === null) { setWaitSeconds(0); return }
    const refresh = () => setWaitSeconds(Math.max(0, Math.ceil((retryDeadline - Date.now()) / 1000)))
    refresh()
    const timer = window.setInterval(refresh, 250)
    return () => window.clearInterval(timer)
  }, [retryDeadline])
  const code = error instanceof ApiClientError ? error.code : error.name === 'TimeoutError' ? 'investigation_timeout' : 'live_request_failed'
  const title = code === 'investigation_timeout' ? 'Live investigation timed out' : code === 'provider_refused' ? 'The model refused this request' : code === 'invalid_model_output' ? 'Live result failed validation' : code === 'rate_limited' || code === 'live_capacity_reached' ? 'Live request limit reached' : code === 'live_analysis_disabled' ? 'Live analysis is disabled' : 'Live investigation unavailable'
  const retry = error instanceof ApiClientError && error.retryAfter ? ` Retry-After: ${error.retryAfter}.` : ''
  return <div className="resource-error"><Notice kind={code === 'investigation_timeout' || code === 'rate_limited' || code === 'live_capacity_reached' ? 'warning' : 'error'} title={title}>{error.message}{retry} No hypothesis was shown from this failed request.{error instanceof ApiClientError ? ` Request ID: ${error.requestId}.` : ''} The stored replay remains available.</Notice><button className="button button-secondary" onClick={onRetry} disabled={waitSeconds > 0}>{waitSeconds > 0 ? `Retry available in ${waitSeconds}s` : 'Try live request again'}</button></div>
}

function retryAfterDeadline(value: string | null): number | null {
  if (!value) return null
  const seconds = Number(value)
  if (Number.isFinite(seconds)) return Date.now() + Math.max(0, seconds * 1000)
  const date = Date.parse(value)
  return Number.isNaN(date) ? null : date
}

function IncidentCardView({ incident }: { incident: IncidentCard }) {
  const serviceText = incident.primary_service.replaceAll('-', ' ')
  return <Link to={`/incidents/${incident.id}`} className="incident-card">
    <div className="incident-card-top"><Severity value={incident.severity} />{incident.replay_available ? <span className="replay-available"><span className="replay-dot"/> Replay ready</span> : <span className="replay-unavailable">Replay unavailable</span>}</div>
    <h3>{incident.title}</h3><p>{incident.symptom_summary}</p>
    <div className="card-meta"><span><Icon name="server" size={15}/>{serviceText}</span><span><Icon name="clock" size={15}/>{dateTime(incident.started_at)} UTC</span></div>
    <div className="card-foot"><span>{dataMode === 'fixtures' ? 'DEV FIXTURE' : 'SYNTHETIC API DATA'} · {incident.fixture_version}</span><span className="card-arrow"><Icon name="arrow" size={16}/></span></div>
  </Link>
}

function Dashboard() {
  const incidentResource = useResource('incident-list', signal => dataClient.listIncidents(signal))
  const incidents = incidentResource.status === 'ready' ? incidentResource.data : []
  const replays = incidents.filter(incident => incident.replay_available).length
  return <div className="page-wrap dashboard-page">
    <header className="workspace-page-heading dashboard-heading"><div><span className="eyebrow">OPERATIONS</span><h1>Incident queue</h1><p>Review a case, inspect its evidence, and open a stored investigation.</p></div><Link to="/incidents" className="saas-primary-button">Browse incidents <Icon name="arrow" size={16}/></Link></header>
    <section className="queue-summary" aria-label="Incident summary"><div><span>Cases</span><strong>{incidentResource.status === 'ready' ? incidents.length : '—'}</strong></div><i/><div><span>Replays available</span><strong>{incidentResource.status === 'ready' ? replays : '—'}</strong></div><i/><div><span>Investigation mode</span><strong>Stored replay</strong></div></section>
    <div className="dashboard-content-grid">
      <section className="dashboard-main-panel queue-panel">
        <div className="section-heading dashboard-section-heading"><div><div className="eyebrow">ACTIVE CASES</div><h2>Choose an incident</h2></div><Link to="/incidents" className="text-link">Full library <Icon name="arrow" size={14}/></Link></div>
        {incidentResource.status === 'loading' ? <LoadingState label="Loading incidents"/> : incidentResource.status === 'error' ? <ResourceError title="Incident catalogue unavailable" error={incidentResource.error} retry={incidentResource.retry}/> : incidents.length ? <div className="incident-queue">{incidents.map(incident => <IncidentQueueRow key={incident.id} incident={incident}/>)}</div> : <EmptyState title="No incidents are available" body="The incident catalogue is empty."/>}
      </section>
      <aside className="dashboard-aside">
        <section className="panel workflow-panel"><div className="eyebrow">WORKFLOW</div><h2>Review sequence</h2><ol className="workflow-list"><li><span className="workflow-step-number">01</span><div><strong>Inspect</strong><small>Timeline, services, and telemetry</small></div></li><li><span className="workflow-step-number">02</span><div><strong>Investigate</strong><small>Ranked hypotheses with citations</small></div></li><li><span className="workflow-step-number">03</span><div><strong>Review</strong><small>Simulated mitigation approval</small></div></li></ol><Link to="/methodology" className="panel-link">How the demo works <Icon name="arrow" size={14}/></Link></section>
        <section className="panel data-boundary"><span className="data-boundary-rule"/><div><strong>Isolated demo data</strong><p>All telemetry is synthetic. Approvals change no external system.</p></div></section>
      </aside>
    </div>
  </div>
}

function IncidentQueueRow({ incident }: { incident: IncidentCard }) {
  return <Link to={`/incidents/${incident.id}`} className="incident-queue-row">
    <span className={`queue-severity ${incident.severity.toLowerCase().replace('-', '')}`}>{incident.severity}</span>
    <span className="queue-case"><strong>{incident.title}</strong><small>{incident.symptom_summary}</small></span>
    <span className="queue-service"><small>PRIMARY SERVICE</small>{incident.primary_service.replaceAll('-', ' ')}</span>
    <span className="queue-time"><small>STARTED · UTC</small>{dateTime(incident.started_at)}</span>
    <span className={`queue-replay ${incident.replay_available ? 'ready' : ''}`}>{incident.replay_available ? 'Replay ready' : 'No replay'}<Icon name="chevron" size={15}/></span>
  </Link>
}

function SettingsPage() {
  const { theme, setTheme } = useTheme()
  const { user, authenticated, signOut } = useAccount()
  const capabilities = useContext(CapabilitiesContext)
  const liveStatus = dataMode === 'fixtures'
    ? 'Unavailable in fixture preview'
    : capabilities.status === 'ready'
      ? capabilities.data.live_ai_enabled ? `Enabled · ${capabilities.data.live_label}` : `Disabled · ${capabilities.data.live_label}`
      : capabilities.status === 'error' ? 'Status unavailable' : 'Checking…'
  return <div className="page-wrap settings-page">
    <PageTitle eyebrow="PREFERENCES" title="Settings" description="Set the workspace appearance and review what this preview connects to." />
    <div className="settings-layout">
      <nav className="settings-nav" aria-label="Settings sections">
        <a href="#appearance"><Icon name="sun" size={16}/> Appearance</a>
        <a href="#workspace"><Icon name="grid" size={16}/> Workspace</a>
        <a href="#notifications"><Icon name="bell" size={16}/> Notifications</a>
        <a href="#integrations"><Icon name="activity" size={16}/> Integrations</a>
        <a href="#data-privacy"><Icon name="server" size={16}/> Data &amp; privacy</a>
      </nav>
      <div className="settings-sections">
        <section className="panel settings-card" id="appearance" aria-labelledby="appearance-title">
          <div className="settings-card-heading"><span className="settings-card-icon"><Icon name="sun" size={17}/></span><div><h2 id="appearance-title">Appearance</h2><p>Choose the color theme for this browser.</p></div></div>
          <div className="theme-choices" role="group" aria-label="Color theme">
            <button className={`theme-choice ${theme === 'light' ? 'selected' : ''}`} type="button" onClick={() => setTheme('light')} aria-pressed={theme === 'light'}><span className="theme-preview theme-preview-light"><i/><i/><i/></span><strong>Light</strong><small>Bright canvas</small></button>
            <button className={`theme-choice ${theme === 'dark' ? 'selected' : ''}`} type="button" onClick={() => setTheme('dark')} aria-pressed={theme === 'dark'}><span className="theme-preview theme-preview-dark"><i/><i/><i/></span><strong>Dark</strong><small>Low-light workspace</small></button>
          </div>
          <div className="settings-detail-row"><div><strong>Incident timestamps</strong><small>UTC is fixed so evidence stays aligned across the case.</small></div><span className="settings-value">UTC</span></div>
        </section>

        <section className="panel settings-card" id="workspace" aria-labelledby="workspace-title">
          <div className="settings-card-heading"><span className="settings-card-icon"><Icon name="grid" size={17}/></span><div><h2 id="workspace-title">Workspace</h2><p>Details for this demo environment.</p></div></div>
          <div className="settings-info-grid"><div><small>Workspace</small><strong>Incident Atlas</strong></div><div><small>Site access</small><strong>Private preview</strong></div><div><small>Environment</small><strong>{dataMode === 'fixtures' ? 'Synthetic fixtures' : 'Backend API'}</strong></div><div><small>External actions</small><strong>Disabled</strong></div></div>
        </section>

        <section className="panel settings-card" id="notifications" aria-labelledby="notifications-title">
          <div className="settings-card-heading"><span className="settings-card-icon"><Icon name="bell" size={17}/></span><div><h2 id="notifications-title">Notifications</h2><p>Notification delivery is not configured for this preview.</p></div><span className="settings-status">Unavailable</span></div>
          <div className="settings-detail-row"><div><strong>Email updates</strong><small>No email address is connected to a notification service.</small></div><span className="settings-disabled-toggle" aria-label="Email notifications unavailable"><i/></span></div>
          <div className="settings-detail-row"><div><strong>In-app alerts</strong><small>This preview does not run background alerts.</small></div><span className="settings-disabled-toggle" aria-label="In-app alerts unavailable"><i/></span></div>
        </section>

        <section className="panel settings-card" id="integrations" aria-labelledby="integrations-title">
          <div className="settings-card-heading"><span className="settings-card-icon"><Icon name="activity" size={17}/></span><div><h2 id="integrations-title">Integrations</h2><p>Current data and analysis connections.</p></div></div>
          <div className="integration-row"><span className="integration-glyph"><Icon name="server" size={17}/></span><div><strong>Telemetry source</strong><small>{dataMode === 'fixtures' ? 'Bundled synthetic incident fixtures' : 'Incident Atlas API'}</small></div><span className="settings-status status-ready">{dataMode === 'fixtures' ? 'Fixture data' : 'API mode'}</span></div>
          <div className="integration-row"><span className="integration-glyph"><Icon name="trace" size={17}/></span><div><strong>Live investigation</strong><small>Stored replay remains available without a model provider.</small></div><span className="settings-status">{liveStatus}</span></div>
          <div className="settings-inline-links"><Link to="/incidents">Browse incidents <Icon name="arrow" size={14}/></Link><Link to="/methodology">Review methodology <Icon name="arrow" size={14}/></Link></div>
        </section>

        <section className="panel settings-card" id="data-privacy" aria-labelledby="data-privacy-title">
          <div className="settings-card-heading"><span className="settings-card-icon"><Icon name="file" size={17}/></span><div><h2 id="data-privacy-title">Data &amp; privacy</h2><p>What this browser preview stores and uses.</p></div></div>
          <div className="privacy-note"><strong>Fixture data only</strong><p>No production telemetry is loaded. Approving a mitigation records a simulation and changes no external system.</p></div>
          <div className="settings-detail-row"><div><strong>Preview identity</strong><small>{authenticated ? `${user?.name || 'Preview user'} · held in this browser session` : 'Guest · no app session'}. Passwords are never stored or sent.</small></div>{authenticated ? <button className="settings-action" type="button" onClick={signOut}>Sign out</button> : <Link className="settings-action" to="/login">Sign in</Link>}</div>
          <div className="settings-detail-row"><div><strong>Theme preference</strong><small>Saved locally on this device.</small></div><span className="settings-value">{theme === 'dark' ? 'Dark' : 'Light'}</span></div>
        </section>
      </div>
    </div>
  </div>
}

function IncidentLibrary() {
  const [query, setQuery] = useState('')
  const [severity, setSeverity] = useState('all')
  const incidentResource = useResource('incident-library', signal => dataClient.listIncidents(signal))
  const incidents = useMemo(() => (incidentResource.status === 'ready' ? incidentResource.data : []).filter(item => (severity === 'all' || item.severity === severity) && `${item.title} ${item.primary_service} ${item.symptom_summary}`.toLowerCase().includes(query.toLowerCase())), [incidentResource, query, severity])
  return <div className="page-wrap">
    <PageTitle eyebrow="INCIDENT LIBRARY · 03 CASES" title="Choose an incident" description="Three reproducible scenarios with a clear symptom window, service graph, and stored investigation replay." actions={<SourceTag tone="blue">{dataMode === 'fixtures' ? 'DEV FIXTURE DATA' : 'API DATA'}</SourceTag>} />
    <div className="filter-bar"><label className="search-field"><Icon name="search" size={17}/><span className="sr-only">Search incidents</span><input value={query} onChange={event => setQuery(event.target.value)} placeholder="Search incidents or services" /></label><label className="select-field"><span className="sr-only">Filter by severity</span><select value={severity} onChange={event => setSeverity(event.target.value)}><option value="all">All severities</option><option>SEV-1</option><option>SEV-2</option><option>SEV-3</option><option>SEV-4</option></select></label><span className="result-count">{incidents.length} of {incidentResource.status === 'ready' ? incidentResource.data.length : '…'} cases</span></div>
    {incidentResource.status === 'loading' ? <LoadingState label="Loading the incident catalogue"/> : incidentResource.status === 'error' ? <ResourceError title="Incident catalogue unavailable" error={incidentResource.error} retry={incidentResource.retry}/> : incidents.length ? <div className="incident-grid">{incidents.map(incident => <IncidentCardView key={incident.id} incident={incident}/>)}</div> : <EmptyState title="No matching incidents" body="Try a different service, incident name, or severity filter." action={<button className="button button-secondary" onClick={() => { setQuery(''); setSeverity('all') }}>Clear filters</button>} />}
    <div className="catalog-footer"><span><Icon name="clock" size={15}/> All timestamps are simulated and shown in UTC.</span><span>Stored replays make no model call.</span></div>
  </div>
}

function ServiceGraph({ incident, resource }: { incident: IncidentDetailType; resource: Resource<DependenciesResponse | undefined> & { retry: () => void } }) {
  if (resource.status === 'loading') return <LoadingState label="Loading service dependencies" compact/>
  if (resource.status === 'error') return <ResourceError title="Dependency data unavailable" error={resource.error} retry={resource.retry}/>
  const dependencies = resource.data
  if (!dependencies) return <EmptyState title="Dependencies unavailable" body="The service graph could not be loaded." />
  return <div className="dependency-layout">
    <div className="service-nodes" aria-label="Services in this incident">{dependencies.nodes.map((node, index) => <div key={node.id} className={`service-node ${node.id === incident.primary_service ? 'primary' : ''}`}><div className="service-node-icon"><Icon name={node.tier.includes('data') ? 'server' : 'activity'} size={16}/></div><div><b>{node.name}</b><small>{node.role} · {node.team}</small></div><span className="node-index">0{index + 1}</span></div>)}</div>
    <div className="dependency-edges"><div className="subsection-label">OBSERVED CALL PATHS</div>{dependencies.edges.map(edge => <div className="dependency-edge" key={edge.id}><span>{edge.from_service_id}</span><i/><span>{edge.to_service_id}</span><small>{edge.relationship}</small></div>)}</div>
    <p className="graph-caption">Text relationships are shown alongside the graph for small screens and assistive technology.</p>
  </div>
}

function Timeline({ events, onEvidence }: { events: TimelineEventOut[]; onEvidence: (id: string) => void }) {
  const [filter, setFilter] = useState<'all' | 'changes' | 'alerts'>('all')
  const visible = events.filter(event => filter === 'all' || filter === 'changes' && event.kind === 'deploy' || filter === 'alerts' && event.kind === 'alert')
  const kindLabel: Record<string, string> = { deploy: 'CHANGE', alert: 'ALERT', marker: 'MARKER' }
  return <><div className="timeline-filters" role="group" aria-label="Filter incident timeline">{([['all', 'All events'], ['changes', 'Changes'], ['alerts', 'Alerts']] as const).map(([key, label]) => <button key={key} className={filter === key ? 'timeline-filter active' : 'timeline-filter'} aria-pressed={filter === key} onClick={() => setFilter(key)}>{label}<span>{key === 'all' ? events.length : events.filter(event => key === 'changes' ? event.kind === 'deploy' : event.kind === 'alert').length}</span></button>)}</div><div className="timeline-list">{visible.map((event, index) => <article className="timeline-event" key={event.evidence_id}>
    <div className="timeline-rail"><span className={`timeline-point ${event.kind}`}>{event.kind === 'deploy' ? <Icon name="arrowUp" size={12}/> : event.kind === 'alert' ? <Icon name="alert" size={12}/> : <span/>}</span>{index < events.length - 1 && <i/>}</div>
    <div className="timeline-content"><div className="timeline-meta"><span>{time(event.occurred_at)} UTC</span><SourceTag tone={event.kind === 'alert' ? 'amber' : 'neutral'}>{kindLabel[event.kind] ?? event.kind.toUpperCase()}</SourceTag><span className="timeline-service">{event.service_id}</span></div><h4>{event.title}</h4><p>{event.summary}</p><button className="evidence-inline" onClick={() => onEvidence(event.evidence_id)}><Icon name="file" size={13}/>{event.evidence_id}</button></div>
  </article>)}</div>{visible.length === 0 && <EmptyState title="No matching events" body="This incident has no events in the selected category."/>}</>
}

function MetricChart({ rows, onEvidence }: { rows: MetricPointOut[]; onEvidence: (id: string) => void }) {
  const groups = useMemo(() => rows.reduce<Record<string, MetricPointOut[]>>((result, row) => { (result[row.series_id] ??= []).push(row); return result }, {}), [rows])
  const palette = ['#177e78', '#d88b31', '#4774af', '#77875b']
  return <div className="metric-grid">{Object.entries(groups).map(([seriesId, points], seriesIndex) => {
    const values = points!.map(point => point.value)
    const low = Math.min(...values); const high = Math.max(...values); const range = high - low || 1
    const linePoints = points!.map((point, index) => `${24 + index * (252 / Math.max(1, points!.length - 1))},${100 - ((point.value - low) / range) * 70}`).join(' ')
    return <div className="metric-card" key={seriesId}>
      <div className="metric-head"><div><span>{points![0].service_id}</span><h4>{points![0].metric_name}</h4></div><span className="metric-value">{compact(values.at(-1)!)} <small>{points![0].unit}</small></span></div>
      <svg className="metric-svg" viewBox="0 0 300 130" role="group" aria-label={`${points![0].metric_name} across the simulated incident window. Select a point for evidence.`}><title>{points![0].metric_name} telemetry</title><desc>Line chart with {points!.length} fixture values. Every point is an evidence record.</desc><line x1="24" y1="100" x2="276" y2="100" className="chart-axis"/><line x1="24" y1="64" x2="276" y2="64" className="chart-gridline"/><polyline points={linePoints} fill="none" stroke={palette[seriesIndex % palette.length]} strokeWidth="2.4" strokeLinejoin="round" strokeLinecap="round"/>{points!.map((point, index) => { const x = 24 + index * (252 / Math.max(1, points!.length - 1)); const y = 100 - ((point.value - low) / range) * 70; return <circle key={point.evidence_id} cx={x} cy={y} r="5" className="chart-point" style={{ color: palette[seriesIndex % palette.length] }} tabIndex={0} role="button" aria-label={`${time(point.observed_at)} UTC, ${point.value} ${point.unit}. Open evidence ${point.evidence_id}`} onClick={() => onEvidence(point.evidence_id)} onKeyDown={event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); onEvidence(point.evidence_id) } }} />})}</svg>
      <div className="chart-foot"><span>{time(points![0].observed_at)} UTC</span><span>16 points · synthetic</span><span>{time(points!.at(-1)!.observed_at)} UTC</span></div>
    </div>
  })}</div>
}

function EvidenceDetails({ resource, selected, onClose }: { resource: Resource<EvidenceItemOut | undefined>; selected: boolean; onClose: () => void }) {
  if (!selected) return <div className="evidence-placeholder"><span className="evidence-placeholder-icon"><Icon name="file" size={17}/></span><div><b>Evidence detail</b><p>Choose a timeline event, chart point, log, or span to inspect its source record.</p></div><span className="key-hint">LINKED ITEMS OPEN HERE</span></div>
  if (resource.status === 'loading') return <LoadingState label="Resolving linked evidence" compact/>
  if (resource.status === 'error') return <Notice kind="error" title="Evidence could not be resolved">{resource.error.message}. No substitute evidence is shown.{resource.error instanceof ApiClientError ? ` Code: ${resource.error.code}; request ${resource.error.requestId}.` : ''}</Notice>
  const evidence = resource.data
  if (!evidence) return <EmptyState title="Evidence item not found" body="This reference is not present in the recorded incident snapshot." action={<button className="button button-secondary" onClick={onClose}>Clear selection</button>} />
  const payload = evidence.payload
  return <section className="evidence-detail" id={`evidence-${evidence.evidence_id}`} tabIndex={-1} aria-labelledby="evidence-title">
    <div className="evidence-detail-top"><div><div className="eyebrow">SOURCE RECORD · {evidence.kind.toUpperCase()}</div><h3 id="evidence-title">{String(payload.title ?? payload.metric_name ?? payload.operation ?? payload.message ?? evidence.evidence_id)}</h3></div><button className="icon-button" aria-label="Clear selected evidence" onClick={onClose}>×</button></div>
    <div className="evidence-id-row"><code>{evidence.evidence_id}</code><span>{evidence.service_id ?? 'No service'} · {time(evidence.observed_at)} UTC</span></div>
    <p className="evidence-summary">{String(payload.summary ?? payload.message ?? (payload.metric_name ? `${payload.value} ${payload.unit} · ${payload.statistic}` : payload.operation ? `${payload.duration_ms} ms · ${payload.status}` : 'Fixture evidence record'))}</p>
    <details className="raw-evidence"><summary>Inspect evidence payload</summary><pre>{JSON.stringify(payload, null, 2)}</pre></details>
    <div className="snapshot-meta"><span>Snapshot <code>{evidence.snapshot_id}</code></span><span>SHA-256 <code>{evidence.snapshot_sha256.slice(0, 12)}…</code></span></div>
  </section>
}

function IncidentWorkspace() {
  const { incidentId = '' } = useParams()
  const [query] = useSearchParams()
  const capabilities = useContext(CapabilitiesContext)
  const [tab, setTab] = useState<TelemetryKind>('metrics')
  const [liveRun, setLiveRun] = useState<{ status: 'idle' | 'running' | 'error'; error?: Error }>({ status: 'idle' })
  const [selectedId, setSelectedId] = useState(query.get('evidence') ?? '')
  const [search, setSearch] = useState('')
  const navigate = useNavigate()
  const liveController = useRef<AbortController | null>(null)
  const liveIdempotencyKey = useRef<string | null>(null)
  const incidentResource = useResource(`incident:${incidentId}`, signal => dataClient.getIncident(incidentId, signal))
  const timelineResource = useResource(`timeline:${incidentId}`, signal => dataClient.getTimeline(incidentId, signal))
  const dependenciesResource = useResource(`dependencies:${incidentId}`, signal => dataClient.getDependencies(incidentId, signal))
  const metricsResource = useResource(`telemetry:${incidentId}:metrics`, signal => dataClient.getTelemetry(incidentId, 'metrics', signal))
  const logsResource = useResource(`telemetry:${incidentId}:logs`, signal => dataClient.getTelemetry(incidentId, 'logs', signal))
  const spansResource = useResource(`telemetry:${incidentId}:traces`, signal => dataClient.getTelemetry(incidentId, 'traces', signal))
  const replayResource = useResource(`replay-for:${incidentId}`, signal => dataClient.getReplay(incidentId, signal))
  const incident = incidentResource.status === 'ready' ? incidentResource.data : undefined
  const timeline = timelineResource.status === 'ready' ? timelineResource.data : []
  const metrics = metricsResource.status === 'ready' ? metricsResource.data as MetricPointOut[] : []
  const logs = logsResource.status === 'ready' ? logsResource.data as LogEventOut[] : []
  const spans = spansResource.status === 'ready' ? spansResource.data as SpanOut[] : []
  const replay = replayResource.status === 'ready' ? replayResource.data : undefined
  const evidenceSnapshotId = query.get('snapshot') ?? replay?.evidence_snapshot_id
  const evidenceResource = useResource(selectedId ? `evidence:${incidentId}:${evidenceSnapshotId ?? 'resolve'}:${selectedId}` : 'no-evidence', signal => selectedId ? dataClient.getEvidence(incidentId, selectedId, evidenceSnapshotId, signal) : Promise.resolve(undefined))
  useEffect(() => { const id = query.get('evidence'); if (id) setSelectedId(id) }, [query])
  useEffect(() => () => liveController.current?.abort(), [])
  const runLiveInvestigation = async () => {
    if (!canRunLiveInvestigation(dataMode, capabilities)) return
    liveController.current?.abort()
    const controller = new AbortController()
    liveController.current = controller
    setLiveRun({ status: 'running' })
    const timeout = window.setTimeout(() => controller.abort(new DOMException('The live investigation exceeded its 20 second deadline.', 'TimeoutError')), 20_000)
    try {
      liveIdempotencyKey.current ??= crypto.randomUUID()
      const report = await dataClient.createInvestigation({ incident_id: incidentId, evidence_window_minutes: 15 }, liveIdempotencyKey.current, controller.signal)
      if (report.source !== 'live_ai' || report.model_call_made !== true) throw new Error('The backend response did not confirm live AI provenance. No report was shown.')
      liveIdempotencyKey.current = null
      navigate(`/investigations/${encodeURIComponent(report.id)}?source=live_ai`)
    } catch (reason) {
      if (controller.signal.aborted && controller.signal.reason instanceof DOMException && controller.signal.reason.name === 'AbortError') return
      const error = controller.signal.aborted ? new Error('The live investigation timed out. No report was returned; the stored replay remains available.') : reason instanceof Error ? reason : new Error('The live investigation failed.')
      setLiveRun({ status: 'error', error })
    } finally {
      window.clearTimeout(timeout)
      if (liveController.current === controller) liveController.current = null
    }
  }
  const resolvedEvidence = evidenceResource.status === 'ready' ? evidenceResource.data : undefined
  useEffect(() => { if (selectedId && resolvedEvidence) { const element = document.getElementById(`evidence-${selectedId}`); if (element) { const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches; element.scrollIntoView({ behavior: reducedMotion ? 'auto' : 'smooth', block: 'center' }); element.focus({ preventScroll: true }) } } }, [selectedId, resolvedEvidence])
  if (incidentResource.status === 'loading') return <div className="page-wrap"><PageTitle eyebrow="LOADING FIXTURE" title="Opening incident workspace" description="Resolving the incident summary and read-only evidence."/><LoadingState label="Loading the incident fixture"/></div>
  if (incidentResource.status === 'error') return <div className="page-wrap"><PageTitle eyebrow="INCIDENT DATA UNAVAILABLE" title="Could not open this incident" description="The read request failed. No fixture values are shown as a substitute."/><ResourceError title="Incident service unavailable" error={incidentResource.error} retry={incidentResource.retry}/><Link className="button button-secondary" to="/incidents">Back to incident library</Link></div>
  if (!incident) return <div className="page-wrap"><PageTitle eyebrow="INCIDENT NOT FOUND" title="This incident is unavailable" description="The requested fixture does not exist in this version."/><Link className="button button-secondary" to="/incidents">Back to incident library</Link></div>
  const telemetryTitle = tab === 'metrics' ? 'Metric series' : tab === 'logs' ? 'Log events' : 'Trace spans'
  const telemetryKinds: TelemetryKind[] = ['metrics', 'logs', 'traces']
  const moveTelemetryTab = (current: TelemetryKind, delta: number) => {
    const next = telemetryKinds[(telemetryKinds.indexOf(current) + delta + telemetryKinds.length) % telemetryKinds.length]
    setTab(next)
    document.querySelector<HTMLButtonElement>(`[data-telemetry-tab="${next}"]`)?.focus()
  }
  const selectEvidence = (id: string) => { setSelectedId(id); setSearch('') }
  const filteredLogs = logs.filter(row => `${row.message} ${row.service_id} ${row.severity}`.toLowerCase().includes(search.toLowerCase()))
  const filteredSpans = spans.filter(row => `${row.operation} ${row.service_id} ${row.status}`.toLowerCase().includes(search.toLowerCase()))
  return <div className="page-wrap incident-page">
    <div className="back-row"><Link to="/incidents"><span>←</span> Incident library</Link><span className="path-divider">/</span><code>{incident.id}</code><div className="back-right"><SourceTag tone="blue">{dataMode === 'fixtures' ? 'DEV FIXTURE PREVIEW' : 'BACKEND SYNTHETIC DATA'}</SourceTag></div></div>
    <div className="incident-header"><div className="incident-title-line"><Severity value={incident.severity}/><span className="incident-window"><Icon name="clock" size={14}/> {date(incident.started_at)} · {time(incident.started_at)}–{time(incident.ended_at)} UTC · simulated</span></div><h1>{incident.title}</h1><p>{incident.symptom_summary}</p><div className="incident-byline"><span>Primary service <b>{incident.primary_service}</b></span><span>Fixture <b>{incident.fixture_version}</b></span><span>Reproducible scenario <b>YES</b></span></div></div>
    <div className="symptom-strip"><div className="symptom-icon"><Icon name="activity" size={19}/></div><div><span>INCIDENT SIGNAL</span><p>{incident.symptom_summary}</p></div><span className="fixture-caption">SYNTHETIC TELEMETRY</span></div>
    {[timelineResource, metricsResource, logsResource, spansResource].some(resource => resource.status === 'error') && <Notice kind="warning" title="Partial incident data">Some telemetry reads are unavailable. Loaded timeline and telemetry panels remain visible where available.</Notice>}
    <div className="workspace-columns">
      <div className="workspace-main">
        <section className="panel"><div className="panel-heading"><div><div className="eyebrow">SERVICE TOPOLOGY</div><h2>Dependency map</h2></div><span className="muted-small">{incident.services.length} services · observed paths</span></div><ServiceGraph incident={incident} resource={dependenciesResource}/></section>
        <section className="panel timeline-panel"><div className="panel-heading"><div><div className="eyebrow">EVENT SEQUENCE</div><h2>Incident timeline</h2></div><span className="muted-small">All times UTC</span></div>{timelineResource.status === 'loading' ? <LoadingState label="Loading incident timeline" compact/> : timelineResource.status === 'error' ? <ResourceError title="Timeline unavailable" error={timelineResource.error} retry={timelineResource.retry}/> : timeline.length ? <Timeline events={timeline} onEvidence={selectEvidence}/> : <EmptyState title="No timeline events" body="No event records are available for this incident window."/>}</section>
      </div>
      <aside className="workspace-aside">
        <section className="panel investigation-start"><div className="eyebrow">INVESTIGATION PATH</div><h2>Ready to investigate?</h2><p>Stored replay is instant and makes no model call. Live analysis is separate and may be rate-limited.</p><button className="button button-primary button-wide" disabled={!replay} onClick={() => { if (replay) navigate(`/investigations/${encodeURIComponent(replay.replay_id ?? replay.id)}?source=stored_replay`) }}>{replayResource.status === 'loading' ? 'Loading replay…' : 'View stored replay'} {replay && <Icon name="arrow" size={16}/>}</button>{replayResource.status === 'error' && <ResourceError title="Stored replay unavailable" error={replayResource.error} retry={replayResource.retry}/>}<div className="replay-provenance"><span className="replay-dot"/><div><b>Stored replay</b><small>Saved result · no model call</small></div></div>
          {canRunLiveInvestigation(dataMode, capabilities) ? <><button className="button button-secondary button-wide" disabled={liveRun.status === 'running'} onClick={runLiveInvestigation}>{liveRun.status === 'running' ? 'Running bounded investigation…' : 'Run live AI investigation'} {liveRun.status !== 'running' && <Icon name="arrow" size={15}/>}</button><p className="live-reason">One server-side request · synthetic evidence · no visitor API key. The result will be labeled LIVE AI.</p>{liveRun.status === 'error' && <LiveRunError error={liveRun.error ?? new Error('Live run failed.')} onRetry={runLiveInvestigation}/>}</> : <div className="live-lock"><span className="lock-icon">•••</span><div><b>Live AI investigation</b><small>{capabilities.status === 'loading' ? 'Checking server capability…' : capabilities.status === 'error' ? 'Unavailable because API capability could not be checked.' : dataMode === 'fixtures' ? 'Unavailable in development fixture mode.' : capabilities.data.live_label}</small></div>{capabilities.status === 'error' ? <button onClick={capabilities.retry}>Retry check</button> : <button disabled aria-label="Live AI investigation unavailable">Unavailable</button>}</div>}
        </section>
        <section className="panel service-summary"><div className="panel-heading compact"><div><div className="eyebrow">AFFECTED SERVICES</div><h3>In scope</h3></div><span className="scope-count">{incident.services.length}</span></div>{incident.services.map(service => { const role = dependenciesResource.status === 'ready' ? dependenciesResource.data?.nodes.find(node => node.id === service.id)?.role ?? 'dependency' : service.id === incident.primary_service ? 'affected' : 'dependency'; return <div className="service-row" key={service.id}><span className={`service-status ${role}`}/><div><b>{service.name}</b><small>{role} · {service.tier}</small></div><span className="team-label">{service.team}</span></div> })}</section>
      </aside>
    </div>
    <section className="panel telemetry-panel"><div className="panel-heading"><div><div className="eyebrow">OBSERVABILITY DATA</div><h2>Telemetry explorer</h2><p>Every signal belongs to the synthetic evidence snapshot.</p></div><SourceTag tone="blue">{dataMode === 'fixtures' ? 'READ-ONLY DEV FIXTURE' : 'READ-ONLY API DATA'}</SourceTag></div>
      <div className="tab-row" role="tablist" aria-label="Telemetry type">{telemetryKinds.map(kind => <button key={kind} id={`tab-${kind}`} data-telemetry-tab={kind} tabIndex={tab === kind ? 0 : -1} role="tab" aria-selected={tab === kind} aria-controls="telemetry-panel" className={tab === kind ? 'tab active' : 'tab'} onClick={() => setTab(kind)} onKeyDown={event => { if (event.key === 'ArrowRight') moveTelemetryTab(kind, 1); if (event.key === 'ArrowLeft') moveTelemetryTab(kind, -1) }}><Icon name={kind === 'metrics' ? 'activity' : kind === 'logs' ? 'file' : 'trace'} size={16}/>{kind === 'traces' ? 'Traces' : kind[0].toUpperCase() + kind.slice(1)}<span>{kind === 'metrics' ? metrics.length : kind === 'logs' ? logs.length : spans.length}</span></button>)}</div>
      <div className="telemetry-content" id="telemetry-panel" role="tabpanel" aria-labelledby={`tab-${tab}`}><div className="telemetry-subhead"><div><h3>{telemetryTitle}</h3><span>Window centered on incident start · point-in-time evidence</span></div>{tab !== 'metrics' && <label className="search-field search-compact"><Icon name="search" size={15}/><span className="sr-only">Filter {tab}</span><input value={search} onChange={event => setSearch(event.target.value)} placeholder={`Filter ${tab}`} /></label>}</div>
        {(() => { const active = tab === 'metrics' ? metricsResource : tab === 'logs' ? logsResource : spansResource; if (active.status === 'loading') return <LoadingState label={`Loading ${tab}`} compact/>; if (active.status === 'error') return <div className="resource-error"><Notice kind="error" title={`${capitalizeTelemetry(tab)} unavailable`}>This telemetry read failed. Other panels remain available.</Notice><button className="button button-secondary" onClick={active.retry}>Retry read</button></div>; if (tab === 'metrics') return metrics.length ? <MetricChart rows={metrics} onEvidence={selectEvidence}/> : <EmptyState title="No metric points" body="No metric points are available for this incident window."/>; if (tab === 'logs') return filteredLogs.length ? <div className="log-list">{filteredLogs.map(row => <article className="log-row" key={row.evidence_id}><span className={`log-severity ${row.severity.toLowerCase()}`}>{row.severity}</span><div className="log-row-main"><div><b>{row.service_id}</b><span>{time(row.observed_at)} UTC</span></div><p>{row.message}</p><code>{row.evidence_id}</code></div><button className="icon-button evidence-open" onClick={() => selectEvidence(row.evidence_id)} aria-label={`Inspect evidence ${row.evidence_id}`}><Icon name="chevron" size={16}/></button></article>)}</div> : <EmptyState title="No matching log events" body="Adjust the filter to include another service or severity."/>; return filteredSpans.length ? <div className="trace-list">{filteredSpans.map(row => <article className="trace-row" key={row.evidence_id}><div className="trace-icon"><Icon name="trace" size={17}/></div><div className="trace-main"><div className="trace-head"><b>{row.operation}</b><span className={row.status === 'ERROR' ? 'trace-status bad' : 'trace-status'}>{row.status}</span></div><div className="trace-meta"><span>{row.service_id}</span><span>{time(row.started_at)} UTC</span><span>{compact(row.duration_ms)} ms</span></div><code>trace {row.trace_id.slice(0, 12)}… · {row.evidence_id}</code></div><button className="icon-button evidence-open" onClick={() => selectEvidence(row.evidence_id)} aria-label={`Inspect evidence ${row.evidence_id}`}><Icon name="chevron" size={16}/></button></article>)}</div> : <EmptyState title="No matching spans" body="Adjust the filter to find a trace operation."/> })()}
        <EvidenceDetails resource={evidenceResource} selected={Boolean(selectedId)} onClose={() => setSelectedId('')}/>
      </div>
    </section>
    <div className="bottom-callout"><div className="callout-icon"><Icon name="file" size={17}/></div><div><b>Evidence stays connected to its source</b><p>Replay citations open the exact timeline or telemetry record inside this incident snapshot.</p></div><SourceTag tone="green">SNAPSHOT {incident.fixture_version}</SourceTag></div>
  </div>
}

function HypothesisCard({ report, hypothesis, onReview }: { report: InvestigationReport; hypothesis: InvestigationReport['hypotheses'][number]; onReview: () => void }) {
  const evidence = [...hypothesis.supporting_evidence_ids.map(id => ({ id, support: true })), ...hypothesis.contradicting_evidence_ids.map(id => ({ id, support: false }))]
  return <article className="hypothesis-card"><div className="hypothesis-top"><div className="rank-label">RANK <strong>0{hypothesis.rank}</strong></div><span className={`confidence confidence-${hypothesis.confidence}`}><span/>{capitalize(hypothesis.confidence)} confidence</span></div><h3>{hypothesis.statement}</h3><p className="confidence-note">{hypothesis.confidence_note}</p><div className="evidence-section"><div className="evidence-heading"><span>LINKED EVIDENCE</span><span>{hypothesis.supporting_evidence_ids.length} supporting · {hypothesis.contradicting_evidence_ids.length} contradicting</span></div><div className="evidence-links">{evidence.map(item => <Link key={item.id} to={evidenceLinkPath(report.incident_id, report.evidence_snapshot_id, item.id)} className="evidence-link"><span className={item.support ? 'evidence-dot support' : 'evidence-dot contradict'}/><span className="evidence-link-copy"><b>{item.id}</b><small>{item.support ? 'Supports this hypothesis' : 'Contradicts this hypothesis'}</small></span><Icon name="arrow" size={14}/></Link>)}</div></div><div className="next-check"><span className="next-check-icon"><Icon name="search" size={15}/></span><div><span>SAFE NEXT READ-ONLY CHECK</span><p>{hypothesis.next_read_only_check}</p></div></div>{hypothesis.mitigation && <div className="mitigation-preview"><div><span className="eyebrow">PROPOSED MITIGATION · SIMULATION ONLY</span><p>{hypothesis.mitigation.summary}</p></div><button className="button button-secondary" onClick={onReview}>Review proposal <Icon name="arrow" size={15}/></button></div>}</article>
}

function useReplayBundle(reportId: string) {
  const [searchParams] = useSearchParams()
  const source: Source = searchParams.get('source') === 'live_ai' ? 'live_ai' : 'stored_replay'
  const reportResource = useResource(`report:${source}:${reportId}`, signal => dataClient.getReport(reportId, source, signal))
  const report = reportResource.status === 'ready' ? reportResource.data : undefined
  const incidentResource = useResource(report ? `incident:${report.incident_id}` : 'replay-incident:none', signal => report ? dataClient.getIncident(report.incident_id, signal) : Promise.resolve(undefined))
  const provenanceValid = !report || report.source === source && (source === 'stored_replay' ? report.model_call_made === false : report.model_call_made === true)
  return { reportResource, report, source, provenanceValid, incidentResource, incident: incidentResource.status === 'ready' ? incidentResource.data : undefined }
}

function InvestigationReportPage() {
  const { reportId = '' } = useParams()
  const { reportResource, report, source, provenanceValid, incidentResource, incident } = useReplayBundle(reportId)
  const navigate = useNavigate()
  if (reportResource.status === 'loading' || reportResource.status === 'ready' && incidentResource.status === 'loading') return <div className="page-wrap"><PageTitle eyebrow={source === 'live_ai' ? 'LIVE INVESTIGATION' : 'STORED REPLAY'} title="Opening investigation report" description="Resolving the report and its recorded evidence snapshot."/><LoadingState label={source === 'live_ai' ? 'Loading persisted live report' : 'Loading stored replay'}/></div>
  if (reportResource.status === 'error') return <div className="page-wrap"><Notice kind="error" title={source === 'live_ai' ? 'Live report unavailable' : 'Stored report unavailable'}>{reportResource.error.message}. No alternate result was loaded.</Notice><button className="button button-secondary" onClick={reportResource.retry}>Retry this report</button></div>
  if (!report || incidentResource.status === 'error') return <div className="page-wrap"><Notice kind="error" title={source === 'live_ai' ? 'Live report unavailable' : 'Stored report unavailable'}>This {source === 'live_ai' ? 'live investigation' : 'replay'} or its incident is not available. No alternate result was loaded.</Notice><Link to="/incidents" className="button button-secondary">Return to incident library</Link></div>
  if (!provenanceValid) return <div className="page-wrap"><Notice kind="error" title="Report provenance mismatch">The API response does not match the requested result source. This report is withheld to avoid confusing a replay with live analysis.</Notice><Link to={`/incidents/${report.incident_id}`} className="button button-secondary">Return to incident</Link></div>
  if (!incident) return <div className="page-wrap"><Notice kind="error" title="Incident details unavailable">The report is available, but the incident context could not be resolved.</Notice><Link to="/incidents" className="button button-secondary">Return to incident library</Link></div>
  return <div className="page-wrap report-page">
    <div className="back-row"><Link to={`/incidents/${report.incident_id}`}><span>←</span> Back to incident</Link><span className="path-divider">/</span><code>{report.id}</code></div>
    <div className="report-banner"><div className="report-banner-icon"><Icon name="file" size={20}/></div><div className="report-banner-copy"><span>PROVENANCE · {report.source === 'stored_replay' ? 'STORED REPLAY' : 'LIVE AI INVESTIGATION'}</span><h1>Investigation report</h1><p>{report.source === 'stored_replay' ? 'Saved report; it was not produced by a live AI call.' : 'Fresh server-side model request over bounded synthetic evidence. This remains a ranked hypothesis, not proof.'}</p></div><div className="report-banner-stamp"><span>MODEL CALL</span><strong>{report.model_call_made ? 'YES' : 'NO'}</strong><small>{report.source === 'stored_replay' ? `Stored ${dateTime(report.originally_generated_at ?? report.completed_at)} UTC` : `Completed ${dateTime(report.completed_at)} UTC`}</small></div></div>
    <div className="report-context"><div><div className="eyebrow">INCIDENT</div><Link to={`/incidents/${report.incident_id}`} className="context-incident">{incident.title}<Icon name="arrow" size={14}/></Link></div><div><div className="eyebrow">FIXTURE VERSION</div><span>{report.fixture_version} · synthetic</span></div><div><div className="eyebrow">EVIDENCE SNAPSHOT</div><code>{report.evidence_snapshot_id}</code></div></div>
    <Notice kind="warning" title="A ranked hypothesis is not a proven root cause">The report describes explanations supported by the recorded evidence. Review linked items and uncertainty before considering a simulated mitigation.</Notice>
    <div className="report-layout"><div className="report-main"><div className="section-heading report-section-heading"><div><div className="eyebrow">RANKED HYPOTHESES · {report.hypotheses.length}</div><h2>What may explain the symptoms?</h2><p>Rank reflects evidence alignment in this report, not certainty.</p></div><SourceTag tone="amber">UNCERTAINTY EXPLICIT</SourceTag></div>{report.hypotheses.map(hypothesis => <HypothesisCard key={hypothesis.id} report={report} hypothesis={hypothesis} onReview={() => navigate(`/investigations/${report.id}/mitigation?source=${report.source}`)} />)}
      <section className="uncertainty-card"><div className="uncertainty-icon">?</div><div><div className="eyebrow">WHAT REMAINS UNCERTAIN</div><p>{report.uncertainty}</p></div></section>
      <section className="baseline-card"><div className="baseline-head"><div><div className="eyebrow">COMPARATOR · RULES BASELINE</div><h3>Simple signal rules</h3></div><span>{report.rules_baseline.version}</span></div><p>Rules are a transparent baseline comparator. Their labels are signals, not ground truth.</p><div className="rule-labels">{report.rules_baseline.ranked_labels.map(label => <span key={label}>{label.replaceAll('_', ' ')}</span>)}</div><div className="fired-rules">{report.rules_baseline.fired_rules.map(rule => <span key={rule.rule_id}><Icon name="check" size={13}/>{rule.rule_id} · {rule.evidence_ids.length} cited signals</span>)}</div></section>
    </div><aside className="report-aside"><div className="panel aside-provenance"><div className="eyebrow">REPORT DETAILS</div><div className="detail-list"><div><span>Result source</span><b>{report.source === 'stored_replay' ? 'Stored replay' : 'Live AI'}</b></div><div><span>Model call made</span><b>{report.model_call_made ? 'Yes' : 'No'}</b></div><div><span>Model identifier</span><b>{report.model_id}</b></div><div><span>Prompt version</span><b>{report.prompt_version}</b></div><div><span>Token usage</span><b>{report.usage.input_tokens} input · {report.usage.output_tokens} output</b></div><div><span>Snapshot SHA-256</span><code>{report.evidence_snapshot_sha256.slice(0, 14)}…</code></div></div><div className="provenance-foot"><span className="replay-dot"/> {report.source === 'stored_replay' ? 'Reproducible stored result' : `Live run · ${report.trace_id ?? 'trace unavailable'}`}</div></div><div className="panel approval-aside"><div className="approval-icon"><Icon name="check" size={17}/></div><h3>Human approval boundary</h3><p>Review a proposed action as a simulation. Approval changes no external system.</p><button className="button button-primary button-wide" onClick={() => navigate(`/investigations/${report.id}/mitigation?source=${report.source}`)}>Review simulated mitigation <Icon name="arrow" size={15}/></button><small>{dataMode === 'fixtures' ? 'Development preview · local only' : 'Persisted simulation record · no external action'}</small></div></aside></div>
    <div className="report-footnote"><Icon name="clock" size={15}/> Originally generated {dateTime(report.originally_generated_at ?? report.completed_at)} UTC <span>·</span> Evidence references resolve against the recorded snapshot.</div>
  </div>
}

function ApprovalDialog({ open, onCancel, onApprove, mitigation, busy, error }: { open: boolean; onCancel: () => void; onApprove: () => Promise<void>; mitigation: string; busy: boolean; error: Error | null }) {
  const ref = useRef<HTMLDialogElement>(null)
  const [ackError, setAckError] = useState(false)
  const [acknowledged, setAcknowledged] = useState(false)
  useEffect(() => { const dialog = ref.current; if (!dialog) return; if (open && !dialog.open) { setAckError(false); setAcknowledged(false); dialog.showModal() } if (!open && dialog.open) dialog.close() }, [open])
  return <dialog ref={ref} className="approval-dialog" aria-labelledby="approval-title" aria-describedby="approval-description" onCancel={event => { event.preventDefault(); onCancel() }} onClose={onCancel}>
    <div className="dialog-top"><span className="dialog-icon"><Icon name="alert" size={19}/></span><button className="icon-button" onClick={onCancel} aria-label="Close confirmation" disabled={busy}>×</button></div><div className="eyebrow">SIMULATION APPROVAL</div><h2 id="approval-title">Approve this simulated mitigation?</h2><p id="approval-description" className="dialog-mitigation">{mitigation}</p><div className="dialog-boundary"><Icon name="check" size={17}/><div><b>No external action will happen.</b><span>{dataMode === 'fixtures' ? 'This development preview records a local-only confirmation.' : 'The backend records a simulation-only approval and does not contact a service, API, cloud account, or production system.'}</span></div></div><label className="acknowledge"><input type="checkbox" checked={acknowledged} aria-describedby={ackError ? 'ack-error' : undefined} onChange={event => { setAcknowledged(event.target.checked); setAckError(false) }}/> <span>I understand this is a simulation and no system will be changed.</span></label>{ackError && <p id="ack-error" className="ack-error" role="alert">Acknowledge the simulation boundary before confirming.</p>}{error && <Notice kind="error" title="Approval was not recorded">{error.message}{error instanceof ApiClientError ? ` Request ID: ${error.requestId}.` : ''}</Notice>}<div className="dialog-actions"><button className="button button-secondary" onClick={onCancel} disabled={busy}>Cancel</button><button className="button button-primary" disabled={busy} onClick={() => { if (!acknowledged) { setAckError(true); ref.current?.querySelector<HTMLInputElement>('input[type=checkbox]')?.focus(); return } void onApprove() }}>{busy ? 'Recording simulation…' : 'Confirm simulation'} {!busy && <Icon name="check" size={15}/>}</button></div><p className="dialog-foot">{dataMode === 'fixtures' ? 'DEV FIXTURE PREVIEW · LOCAL ONLY' : 'PERSISTED SIMULATION RECORD · NO EXTERNAL ACTION'}</p>
  </dialog>
}

function MitigationReview() {
  const { reportId = '' } = useParams()
  const [dialogOpen, setDialogOpen] = useState(false)
  const [approval, setApproval] = useState<ApprovalResponse | null>(null)
  const [approvalError, setApprovalError] = useState<Error | null>(null)
  const [saving, setSaving] = useState(false)
  const { reportResource, report, provenanceValid, incidentResource, incident } = useReplayBundle(reportId)
  if (reportResource.status === 'loading' || reportResource.status === 'ready' && incidentResource.status === 'loading') return <div className="page-wrap"><PageTitle eyebrow="SIMULATION REVIEW" title="Loading mitigation proposal" description="Resolving the stored report before presenting its proposed action."/><LoadingState label="Loading proposal"/></div>
  if (reportResource.status === 'error' || incidentResource.status === 'error') return <div className="page-wrap"><Notice kind="error" title="Mitigation proposal unavailable">The stored report could not be resolved. No approval was recorded.</Notice><Link to="/incidents" className="button button-secondary">Incident library</Link></div>
  if (report && !provenanceValid) return <div className="page-wrap"><Notice kind="error" title="Report provenance mismatch">This result does not match the requested source. No approval was submitted.</Notice><Link to="/incidents" className="button button-secondary">Incident library</Link></div>
  if (!report || !incident) return <div className="page-wrap"><EmptyState title="Mitigation proposal unavailable" body="Return to the incident library to choose a stored replay." action={<Link to="/incidents" className="button button-secondary">Incident library</Link>} /></div>
  const hypothesis = report.hypotheses.find(item => item.mitigation)
  const mitigation = hypothesis?.mitigation
  if (!mitigation) return <div className="page-wrap"><Notice kind="info" title="No mitigation proposal">This report does not include a simulation proposal.</Notice><Link to={`/investigations/${report.id}?source=${report.source}`} className="text-link">Back to report</Link></div>
  const reportPath = investigationPath(report.id, report.source)
  const recordApproval = async () => {
    setSaving(true)
    setApprovalError(null)
    try {
      const result = await dataClient.approve(report, { hypothesis_id: hypothesis.id, mitigation_id: mitigation.id, simulation_acknowledged: true })
      setApproval(result)
      setDialogOpen(false)
    } catch (reason) {
      setApprovalError(reason instanceof Error ? reason : new Error('The approval request failed.'))
    } finally {
      setSaving(false)
    }
  }
  return <div className="page-wrap mitigation-page"><div className="back-row"><Link to={reportPath}><span>←</span> Back to report</Link><span className="path-divider">/</span><code>MITIGATION REVIEW</code><div className="back-right"><SourceTag tone="amber">SIMULATION ONLY</SourceTag></div></div>
    <PageTitle eyebrow="HUMAN APPROVAL BOUNDARY" title="Review proposed mitigation" description="Inspect the proposed response and decide whether to record a simulation approval." />
    <div className="mitigation-review-layout"><div className="panel mitigation-review-card"><div className="proposal-top"><span className="proposal-symbol"><Icon name="check" size={21}/></span><SourceTag tone="amber">PROPOSAL · NOT EXECUTED</SourceTag></div><div className="eyebrow">PROPOSED RESPONSE</div><h2>{mitigation.summary}</h2><p className="proposal-copy">This proposal is attached to the top-ranked hypothesis for <b>{incident.title}</b>. The evidence is synthetic; review it before approving the simulation.</p><div className="proposal-context"><span>Related hypothesis</span><b>{hypothesis.statement}</b><Link to={reportPath} className="text-link">Review supporting evidence <Icon name="arrow" size={14}/></Link></div><div className="proposal-actions"><button className="button button-primary" onClick={() => { setApprovalError(null); setDialogOpen(true) }} disabled={Boolean(approval)}>{approval ? 'Simulation recorded' : 'Approve simulated mitigation'} {!approval && <Icon name="arrow" size={15}/>}</button><Link to={reportPath} className="button button-secondary">Return to report</Link></div></div>
      <aside className="mitigation-aside"><div className="boundary-panel"><div className="boundary-seal"><Icon name="check" size={21}/></div><div className="eyebrow">SIMULATION BOUNDARY</div><h3>This action cannot reach a live system</h3><ul><li><Icon name="check" size={14}/> No external mitigation call</li><li><Icon name="check" size={14}/> No credentials or connected accounts</li><li><Icon name="check" size={14}/> No infrastructure change</li></ul><div className="boundary-rule"/><div className="boundary-status"><span>External action performed</span><b>{approval?.external_action_performed === false ? 'NO' : 'NO'}</b></div><div className="boundary-status"><span>Approval persistence</span><b>{approval ? dataMode === 'fixtures' ? 'LOCAL PREVIEW' : 'PERSISTED' : 'NOT RECORDED'}</b></div></div></aside></div>
    {approval && <div className="approval-success" role="status"><span className="success-mark"><Icon name="check" size={20}/></span><div><div className="eyebrow">SIMULATION RECORDED</div><h3>{approval.message}</h3><p>simulation_only={String(approval.simulation_only)} · external_action_performed={String(approval.external_action_performed)} · record {approval.id} · {dateTime(approval.recorded_at)} UTC</p><small>{dataMode === 'fixtures' ? 'Development fixture preview: local-only confirmation.' : `Persisted backend approval · request ${approval.request_id}`}</small></div><SourceTag tone="green">{dataMode === 'fixtures' ? 'LOCAL ONLY' : 'PERSISTED'}</SourceTag></div>}
    <ApprovalDialog open={dialogOpen} onCancel={() => setDialogOpen(false)} onApprove={recordApproval} busy={saving} error={approvalError} mitigation={mitigation.summary}/>
  </div>
}

function StateExamples() {
  const [active, setActive] = useState('loading')
  const labels = [['loading', 'Loading'], ['empty', 'Empty'], ['timeout', 'Timed out'], ['invalid', 'Invalid result'], ['unavailable', 'Unavailable'], ['partial', 'Partial data']]
  return <section className="state-examples" aria-labelledby="states-title"><div className="state-examples-head"><div><div className="eyebrow">INTERFACE PATTERNS · ILLUSTRATIVE</div><h2 id="states-title">When a read or run fails</h2><p>These examples are illustrative patterns, not current API results.</p></div><SourceTag tone="neutral">NOT A LIVE REQUEST</SourceTag></div><div className="state-tabs" role="group" aria-label="Choose an illustrative response state">{labels.map(([key, label]) => <button key={key} type="button" aria-pressed={active === key} className={active === key ? 'state-tab active' : 'state-tab'} onClick={() => setActive(key)}>{label}</button>)}</div><div className="state-example-body" aria-live="polite">{active === 'loading' ? <LoadingState label="Loading telemetry panel" compact/> : active === 'empty' ? <EmptyState title="No telemetry in this window" body="This service and time range have no matching fixture records. Reset the filter or choose another signal."/> : active === 'timeout' ? <Notice kind="warning" title="Live investigation timed out">No report was returned. The incident remains available, and you can open its stored replay.</Notice> : active === 'invalid' ? <Notice kind="error" title="Live result failed validation">The response did not pass schema or evidence-reference checks. No diagnosis was presented.</Notice> : active === 'unavailable' ? <Notice kind="error" title="Telemetry service unavailable">A fresh read could not be loaded. Existing incident context remains visible; retry only after the API is reachable.</Notice> : <Notice kind="warning" title="Partial telemetry data">Metrics are available, while traces could not be loaded. The missing panel is named and the available data remains usable.</Notice>}</div></section>
}

function Methodology() {
  return <div className="page-wrap methodology-page"><PageTitle eyebrow="METHODOLOGY & EVALUATION" title="How to read this demo" description="Dataset provenance, replay behavior, and the approval boundary." actions={<SourceTag tone="blue">PRIVATE FIXTURE PREVIEW</SourceTag>} />
    <div className="method-hero"><div><div className="eyebrow eyebrow-light">INVESTIGATION LOOP</div><h2>Signals inform hypotheses.<br/><em>People review the action.</em></h2><p>This private preview uses synthetic incidents and stored reports. Live AI is off; mitigation approval remains a local simulation.</p></div><div className="method-loop"><div><span>01</span><b>Observe</b><small>Incident telemetry</small></div><i/><div><span>02</span><b>Hypothesize</b><small>Linked evidence</small></div><i/><div><span>03</span><b>Simulate</b><small>Human review</small></div></div></div>
    <div className="method-grid"><article className="method-card"><span className="method-number">01</span><div className="eyebrow">DATA SOURCES</div><h3>Three reproducible scenarios</h3><p>Cache collapse, inventory connection-pool saturation, and payment gateway latency. These versioned fixtures include changes, metrics, logs, and traces; evaluation labels stay separate from public data.</p><Link to="/incidents" className="text-link">Browse scenarios <Icon name="arrow" size={14}/></Link></article><article className="method-card"><span className="method-number">02</span><div className="eyebrow">RESULT PROVENANCE</div><h3>Stored replay, clearly labeled</h3><p>Each report shows its fixture version and evidence snapshot. A stored replay does not make a model call.</p><div className="mini-provenance"><SourceTag tone="blue">STORED REPLAY</SourceTag><span>0 tokens · no provider call</span></div></article><article className="method-card"><span className="method-number">03</span><div className="eyebrow">LIVE ANALYSIS</div><h3>Live AI is off here</h3><p>This Site makes no provider request. The separate API-backed product has a gated live path; it is not part of this fixture preview.</p><div className="mini-provenance live-mini"><SourceTag tone="amber">NOT ENABLED IN THIS PREVIEW</SourceTag></div></article><article className="method-card"><span className="method-number">04</span><div className="eyebrow">EVALUATION</div><h3>Regression checks, not accuracy claims</h3><p>Rules compare against fixture labels. Three authored cases are useful for regression, but they do not measure real-world incident accuracy.</p><Link to="/incidents" className="text-link">Browse the incident library <Icon name="arrow" size={14}/></Link></article></div>
    <StateExamples/>
    <div className="method-boundary"><div className="boundary-symbol"><Icon name="alert" size={20}/></div><div><div className="eyebrow">ROOT CAUSE AND ACTION BOUNDARY</div><h3>Root causes stay hypotheses.</h3><p>Evidence can support or weaken an explanation, but the report does not prove causality. Approval records a simulation only. It does not connect to production or change a service.</p></div></div>
    <div className="method-links"><span>PROJECT DOCUMENTS</span><a href="https://github.com/shaviJayasingha/incident-atlas" target="_blank" rel="noopener noreferrer" aria-label="Open the Incident Atlas GitHub repository">GitHub source code <Icon name="external" size={13}/></a><span>·</span><span>Scenario fixtures · v1.0.0</span></div>
  </div>
}

function NotFound() { return <div className="page-wrap"><PageTitle eyebrow="404" title="Page not found" description="The page may have moved or no longer exists."/><Link to="/" className="button button-primary">Return to overview <Icon name="arrow" size={15}/></Link></div> }

function App() {
  const capabilities = useResource('demo-capabilities', signal => dataClient.getCapabilities(signal))
  return <CapabilitiesContext.Provider value={capabilities}><ThemeProvider><AccountProvider><Routes>
    <Route path="/login" element={<LoginPage/>}/><Route path="/register" element={<RegisterPage/>}/>
    <Route path="/profile" element={<Navigate to="/" replace/>}/>
    <Route path="/" element={<Shell/>}>
      <Route index element={<Dashboard/>}/><Route path="incidents" element={<IncidentLibrary/>}/><Route path="incidents/:incidentId" element={<IncidentWorkspace/>}/><Route path="investigations/:reportId" element={<InvestigationReportPage/>}/><Route path="investigations/:reportId/mitigation" element={<MitigationReview/>}/><Route path="methodology" element={<Methodology/>}/><Route path="settings" element={<SettingsPage/>}/>
    </Route><Route path="*" element={<NotFound/>}/>
  </Routes></AccountProvider></ThemeProvider></CapabilitiesContext.Provider>
}

function time(value: string) { return new Intl.DateTimeFormat('en-GB', { hour: '2-digit', minute: '2-digit', timeZone: 'UTC', hourCycle: 'h23' }).format(new Date(value)) }
function date(value: string) { return new Intl.DateTimeFormat('en-GB', { day: '2-digit', month: 'short', year: 'numeric', timeZone: 'UTC' }).format(new Date(value)) }
function dateTime(value: string) { return `${date(value)} · ${time(value)}` }
function compact(value: number) { return Intl.NumberFormat('en', { notation: value >= 1000 ? 'compact' : 'standard', maximumFractionDigits: 1 }).format(value) }
function capitalize(value: Confidence) { return value.charAt(0).toUpperCase() + value.slice(1) }
function capitalizeTelemetry(value: TelemetryKind) { return value === 'traces' ? 'Traces' : value === 'logs' ? 'Logs' : 'Metrics' }

export default App
