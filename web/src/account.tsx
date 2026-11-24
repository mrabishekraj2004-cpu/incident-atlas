import { createContext, useContext, useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { Link, useNavigate } from 'react-router-dom'

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
    return matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
  } catch { return 'light' }
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<ThemeMode>(initialTheme)
  useEffect(() => {
    document.documentElement.dataset.theme = theme
    document.querySelector('meta[name="theme-color"]')?.setAttribute('content', theme === 'dark' ? '#151a20' : '#f4f6f8')
    try { localStorage.setItem('incident-atlas.theme', theme) } catch { /* Theme still applies in memory. */ }
  }, [theme])
  const toggleTheme = () => setTheme(value => value === 'light' ? 'dark' : 'light')
  return <ThemeContext.Provider value={{ theme, toggleTheme }}>{children}</ThemeContext.Provider>
}

function Brand() {
  return <Link className="account-brand" to="/" aria-label="Incident Atlas home"><span>Incident</span><strong>Atlas</strong></Link>
}

function AuthLayout({ title, children }: { title: string; children: ReactNode }) {
  const { theme, toggleTheme } = useTheme()
  return <main className="auth-screen">
    <header className="auth-topbar"><Brand/><div className="auth-top-actions"><button className="theme-toggle" type="button" onClick={toggleTheme}>{theme === 'light' ? 'Dark appearance' : 'Light appearance'}</button><Link className="auth-back-link" to="/">Continue as guest</Link></div></header>
    <div className="auth-layout"><section className="auth-card">
      <div className="auth-kicker"><span className="auth-kicker-dot"/> INCIDENT ATLAS · LOCAL PREVIEW</div>
      <h1>{title}</h1>
      <p className="auth-intro">Use a temporary profile to personalize this browser preview. You can explore every incident without signing in.</p>
      {children}
      <div className="auth-disclosure"><strong>Preview access only</strong><span>This demo has no account service. Your email and display name stay in this browser session. Passwords are checked in the form, then discarded; never enter a real password.</span></div>
    </section></div>
  </main>
}

export function SignInPage() {
  const { saveProfile } = useAccount()
  const navigate = useNavigate()
  const [error, setError] = useState('')
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
  return <AuthLayout title="Welcome back">
    <form className="auth-form" onSubmit={submit} noValidate>
      <label htmlFor="signin-email">Email address</label><input id="signin-email" name="email" type="email" autoComplete="email" placeholder="you@company.com" required/>
      <div className="auth-label-row"><label htmlFor="signin-password">Preview password</label><span>not stored</span></div><input id="signin-password" name="password" type="password" autoComplete="new-password" placeholder="Use a throwaway value" required/>
      {error && <p className="auth-error" role="alert">{error}</p>}
      <button className="button button-primary auth-submit" type="submit">Open preview workspace <span aria-hidden="true">→</span></button>
    </form>
    <p className="auth-switch">New to Incident Atlas? <Link to="/register">Create preview access</Link></p>
  </AuthLayout>
}

export function RegisterPage() {
  const { saveProfile } = useAccount()
  const navigate = useNavigate()
  const [error, setError] = useState('')
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
  return <AuthLayout title="Create your workspace profile">
    <form className="auth-form" onSubmit={submit} noValidate>
      <label htmlFor="register-name">Display name</label><input id="register-name" name="name" autoComplete="name" placeholder="Your name" required/>
      <label htmlFor="register-email">Email address</label><input id="register-email" name="email" type="email" autoComplete="email" placeholder="you@company.com" required/>
      <div className="auth-label-row"><label htmlFor="register-password">Preview password</label><span>discarded after submit</span></div><input id="register-password" name="password" type="password" autoComplete="new-password" placeholder="Use a throwaway value" required/>
      <label htmlFor="register-confirmation">Confirm preview password</label><input id="register-confirmation" name="confirmation" type="password" autoComplete="new-password" placeholder="Repeat the throwaway value" required/>
      {error && <p className="auth-error" role="alert">{error}</p>}
      <button className="button button-primary auth-submit" type="submit">Create preview profile <span aria-hidden="true">→</span></button>
    </form>
    <p className="auth-switch">Already have preview access? <Link to="/login">Sign in</Link></p>
  </AuthLayout>
}
