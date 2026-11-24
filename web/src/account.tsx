import { createContext, useContext, useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Brand } from './Brand'

export type PreviewProfile = { name: string; email: string }
type AccountValue = {
  profile: PreviewProfile | null
  saveProfile: (profile: PreviewProfile) => void
  signOut: () => void
}

const accountStorageKey = 'incident-atlas.preview-profile.v1'
const AccountContext = createContext<AccountValue>({ profile: null, saveProfile: () => undefined, signOut: () => undefined })
export const useAccount = () => useContext(AccountContext)

function readProfile(): PreviewProfile | null {
  try {
    const value = sessionStorage.getItem(accountStorageKey)
    if (!value) return null
    const profile = JSON.parse(value) as Partial<PreviewProfile>
    return typeof profile.name === 'string' && typeof profile.email === 'string' ? { name: profile.name, email: profile.email } : null
  } catch { return null }
}

export function AccountProvider({ children }: { children: ReactNode }) {
  const [profile, setProfile] = useState<PreviewProfile | null>(readProfile)
  const saveProfile = (value: PreviewProfile) => {
    const next = { name: value.name.trim(), email: value.email.trim().toLowerCase() }
    setProfile(next)
    try { sessionStorage.setItem(accountStorageKey, JSON.stringify(next)) } catch { /* Keep the preview session usable in memory. */ }
  }
  const signOut = () => {
    setProfile(null)
    try { sessionStorage.removeItem(accountStorageKey) } catch { /* Ignore unavailable browser storage. */ }
  }
  return <AccountContext.Provider value={{ profile, saveProfile, signOut }}>{children}</AccountContext.Provider>
}

export type ThemeMode = 'light' | 'dark'
const ThemeContext = createContext<{ theme: ThemeMode; toggleTheme: () => void }>({ theme: 'light', toggleTheme: () => undefined })
export const useTheme = () => useContext(ThemeContext)

function initialTheme(): ThemeMode {
  try {
    const saved = localStorage.getItem('incident-atlas.theme')
    if (saved === 'light' || saved === 'dark') return saved
    return 'light'
  } catch { return 'light' }
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<ThemeMode>(initialTheme)
  useEffect(() => {
    document.documentElement.dataset.theme = theme
    document.querySelector('meta[name="theme-color"]')?.setAttribute('content', theme === 'dark' ? '#111a1b' : '#f3f6f3')
    try { localStorage.setItem('incident-atlas.theme', theme) } catch { /* Theme still applies in memory. */ }
  }, [theme])
  const toggleTheme = () => setTheme(value => value === 'light' ? 'dark' : 'light')
  return <ThemeContext.Provider value={{ theme, toggleTheme }}>{children}</ThemeContext.Provider>
}

function ThemeGlyph({ theme }: { theme: ThemeMode }) {
  return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    {theme === 'light' ? <path d="M20.4 15.2A8.5 8.5 0 0 1 8.8 3.6a8.6 8.6 0 1 0 11.6 11.6Z"/> : <><circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M4.93 4.93l1.41 1.41m11.32 11.32 1.41 1.41M2 12h2m16 0h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"/></>}
  </svg>
}

function AuthStory() {
  return <aside className="auth-story" aria-label="How the Incident Atlas demo works">
    <div className="auth-story-label"><span>EVIDENCE-LED INCIDENT REVIEW</span></div>
    <div className="auth-story-copy"><h2>Find the first signal.<br/><em>Keep every claim traceable.</em></h2><p>Explore a clear path from service telemetry to ranked hypotheses, with a person reviewing every simulated action.</p></div>
    <div className="auth-story-board">
      <div className="auth-board-header"><span>SCENARIO · CATALOG LATENCY</span><span className="auth-board-badge">SYNTHETIC</span></div>
      <div className="auth-board-timeline">
        <div className="auth-board-event"><span className="auth-board-time">10:05</span><span className="auth-board-point point-change"/><span className="auth-board-event-copy"><strong>Change marker</strong><small>Catalog configuration updated</small></span></div>
        <div className="auth-board-event"><span className="auth-board-time">10:07</span><span className="auth-board-point point-signal"/><span className="auth-board-event-copy"><strong>Latency rises</strong><small>Checkout signal needs context</small></span></div>
        <div className="auth-board-event"><span className="auth-board-time">10:09</span><span className="auth-board-point point-review"/><span className="auth-board-event-copy"><strong>Replay reviewed</strong><small>Evidence stays one click away</small></span></div>
      </div>
      <div className="auth-board-foot"><span className="auth-board-foot-icon">✓</span><span>Hypothesis, not a confirmed cause</span></div>
    </div>
    <div className="auth-story-foot"><span>BUILT FOR CLEAR INCIDENT REVIEWS</span><span>01 <i/> 03</span></div>
  </aside>
}

function AuthLayout({ title, subtitle, eyebrow, children }: { title: string; subtitle: string; eyebrow: string; children: ReactNode }) {
  const { theme, toggleTheme } = useTheme()
  return <main className="auth-screen">
    <header className="auth-topbar"><Brand/><div className="auth-top-actions"><button className="theme-toggle" type="button" onClick={toggleTheme} aria-pressed={theme === 'dark'} aria-label={`Switch to ${theme === 'light' ? 'dark' : 'light'} appearance`}><ThemeGlyph theme={theme}/><span>{theme === 'light' ? 'Dark mode' : 'Light mode'}</span></button><Link className="auth-back-link" to="/">Explore as guest</Link></div></header>
    <div className="auth-layout"><AuthStory/><section className="auth-card">
      <div className="auth-kicker"><span className="auth-kicker-dot"/> {eyebrow}</div>
      <h1>{title}</h1>
      <p className="auth-intro">{subtitle}</p>
      {children}
      <div className="auth-disclosure"><strong>Preview access only</strong><span>This demo has no account service. Your email and display name stay in this browser session. Passwords are checked in the form, then discarded; never enter a real password.</span></div>
    </section></div>
    <footer className="auth-page-footer"><span>INCIDENT ATLAS</span><span className="developer-credit">Developed by <strong>Abishek</strong></span></footer>
  </main>
}

export function SignInPage() {
  const { saveProfile } = useAccount()
  const navigate = useNavigate()
  const [error, setError] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const form = event.currentTarget
    const data = new FormData(form)
    const email = String(data.get('email') ?? '').trim().toLowerCase()
    const password = String(data.get('password') ?? '')
    if (!/^\S+@\S+\.\S+$/.test(email)) return setError('Enter a valid email address.')
    if (password.length < 8) return setError('Use at least 8 characters for this preview-only check.')
    saveProfile({ email, name: email.split('@')[0].replace(/[._-]+/g, ' ').replace(/\b\w/g, letter => letter.toUpperCase()) })
    form.reset()
    navigate('/settings/profile')
  }
  return <AuthLayout eyebrow="SIGN IN · BROWSER PREVIEW" title="Welcome back" subtitle="Use a temporary profile for this browser. You can also explore the incident replays as a guest." >
    <form className="auth-form" onSubmit={submit} noValidate>
      <label htmlFor="signin-email">Work email</label><input id="signin-email" name="email" type="email" autoComplete="email" placeholder="name@company.com" required aria-invalid={Boolean(error)} aria-describedby={error ? 'signin-error' : undefined}/>
      <div className="auth-label-row"><label htmlFor="signin-password">Demo password</label><span>discarded after submit</span></div>
      <div className="auth-password-wrap"><input id="signin-password" name="password" type={showPassword ? 'text' : 'password'} autoComplete="current-password" placeholder="Enter a throwaway value" required aria-invalid={Boolean(error)} aria-describedby={error ? 'signin-error' : undefined}/><button className="password-visibility" type="button" aria-pressed={showPassword} onClick={() => setShowPassword(value => !value)}>{showPassword ? 'Hide' : 'Show'}</button></div>
      {error && <p className="auth-error" id="signin-error" role="alert">{error}</p>}
      <button className="button button-primary auth-submit" type="submit">Sign in to preview</button>
    </form>
    <p className="auth-switch">New to Incident Atlas? <Link to="/register">Create a preview profile</Link></p>
  </AuthLayout>
}

export function RegisterPage() {
  const { saveProfile } = useAccount()
  const navigate = useNavigate()
  const [error, setError] = useState('')
  const [showPasswords, setShowPasswords] = useState(false)
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const form = event.currentTarget
    const data = new FormData(form)
    const name = String(data.get('name') ?? '').trim()
    const email = String(data.get('email') ?? '').trim().toLowerCase()
    const password = String(data.get('password') ?? '')
    const confirmation = String(data.get('confirmation') ?? '')
    if (name.length < 2) return setError('Enter a name with at least two characters.')
    if (!/^\S+@\S+\.\S+$/.test(email)) return setError('Enter a valid email address.')
    if (password.length < 8) return setError('Use at least 8 characters for this preview-only check.')
    if (password !== confirmation) return setError('The preview password fields do not match.')
    saveProfile({ name, email })
    form.reset()
    navigate('/settings/profile')
  }
  return <AuthLayout eyebrow="CREATE PROFILE · BROWSER PREVIEW" title="Make this workspace yours" subtitle="Set up a local preview profile. No account is created and nothing is sent to a server.">
    <form className="auth-form" onSubmit={submit} noValidate>
      <label htmlFor="register-name">Your name</label><input id="register-name" name="name" autoComplete="name" placeholder="How should we address you?" required aria-invalid={Boolean(error)} aria-describedby={error ? 'register-error' : undefined}/>
      <label htmlFor="register-email">Work email</label><input id="register-email" name="email" type="email" autoComplete="email" placeholder="name@company.com" required aria-invalid={Boolean(error)} aria-describedby={error ? 'register-error' : undefined}/>
      <div className="auth-label-row"><label htmlFor="register-password">Demo password</label><span>never stored</span></div>
      <div className="auth-password-wrap"><input id="register-password" name="password" type={showPasswords ? 'text' : 'password'} autoComplete="new-password" placeholder="Use a throwaway value" required aria-invalid={Boolean(error)} aria-describedby={error ? 'register-error' : undefined}/><button className="password-visibility" type="button" aria-pressed={showPasswords} onClick={() => setShowPasswords(value => !value)}>{showPasswords ? 'Hide' : 'Show'}</button></div>
      <label htmlFor="register-confirmation">Confirm demo password</label><input id="register-confirmation" name="confirmation" type={showPasswords ? 'text' : 'password'} autoComplete="new-password" placeholder="Enter the same throwaway value" required aria-invalid={Boolean(error)} aria-describedby={error ? 'register-error' : undefined}/>
      {error && <p className="auth-error" id="register-error" role="alert">{error}</p>}
      <button className="button button-primary auth-submit" type="submit">Create preview profile</button>
    </form>
    <p className="auth-switch">Already have a preview profile? <Link to="/login">Sign in</Link></p>
  </AuthLayout>
}
