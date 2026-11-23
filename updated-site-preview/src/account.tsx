import { createContext, useContext, useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { Link, useNavigate } from 'react-router-dom'

export type PreviewUser = { name: string; email: string }
type AccountContextValue = {
  user: PreviewUser | null
  authenticated: boolean
  startSession: (user: PreviewUser) => void
  signOut: () => void
}

const accountKey = 'incident-atlas.preview-session.v2'
const AccountContext = createContext<AccountContextValue>({ user: null, authenticated: false, startSession: () => undefined, signOut: () => undefined })
export const useAccount = () => useContext(AccountContext)

function readSession(): PreviewUser | null {
  try {
    const value = sessionStorage.getItem(accountKey)
    if (!value) return null
    const parsed = JSON.parse(value) as Partial<PreviewUser>
    return typeof parsed.name === 'string' && typeof parsed.email === 'string' ? { name: parsed.name, email: parsed.email } : null
  } catch { return null }
}

export function AccountProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<PreviewUser | null>(readSession)
  const startSession = (next: PreviewUser) => {
    const safe = { name: next.name.trim(), email: next.email.trim().toLowerCase() }
    setUser(safe)
    try { sessionStorage.setItem(accountKey, JSON.stringify(safe)) } catch { /* Keep the in-memory preview usable. */ }
  }
  const signOut = () => {
    setUser(null)
    try { sessionStorage.removeItem(accountKey) } catch { /* Ignore unavailable browser storage. */ }
  }
  return <AccountContext.Provider value={{ user, authenticated: user !== null, startSession, signOut }}>{children}</AccountContext.Provider>
}

export type ThemeMode = 'light' | 'dark'
const ThemeContext = createContext<{ theme: ThemeMode; setTheme: (theme: ThemeMode) => void; toggleTheme: () => void }>({ theme: 'light', setTheme: () => undefined, toggleTheme: () => undefined })
export const useTheme = () => useContext(ThemeContext)

function readTheme(): ThemeMode {
  try {
    const saved = localStorage.getItem('incident-atlas.theme')
    if (saved === 'light' || saved === 'dark') return saved
    return matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
  } catch { return 'light' }
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<ThemeMode>(readTheme)
  useEffect(() => {
    document.documentElement.dataset.theme = theme
    document.querySelector('meta[name="theme-color"]')?.setAttribute('content', theme === 'dark' ? '#141b20' : '#f4f6f5')
    try { localStorage.setItem('incident-atlas.theme', theme) } catch { /* Theme still applies for this session. */ }
  }, [theme])
  return <ThemeContext.Provider value={{ theme, setTheme, toggleTheme: () => setTheme(value => value === 'light' ? 'dark' : 'light') }}>{children}</ThemeContext.Provider>
}

function Brand() {
  return <Link className="account-brand brand-wordmark" to="/" aria-label="Incident Atlas home"><span>INCIDENT</span><strong>Atlas</strong></Link>
}

function AuthLayout({ children, title }: { children: ReactNode; title: string }) {
  const { theme, toggleTheme } = useTheme()
  return <main className="auth-screen">
    <header className="auth-topbar"><Brand/><div className="auth-top-actions"><button className="auth-theme-toggle" type="button" onClick={toggleTheme} aria-label={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`}>{theme === 'light' ? 'Dark mode' : 'Light mode'}</button><Link className="auth-back-link" to="/">Back to incidents</Link></div></header>
    <div className="auth-layout"><section className="auth-card">
      <span className="auth-overline">INCIDENT ATLAS · PREVIEW</span>
      <h1>{title}</h1>
      {children}
      <p className="auth-disclosure">Local demo only. This form does not create an account or send credentials. Passwords are discarded.</p>
      <Link className="auth-guest-link" to="/">Continue without signing in</Link>
    </section></div>
  </main>
}

export function LoginPage() {
  const { startSession } = useAccount()
  const navigate = useNavigate()
  const [error, setError] = useState('')
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const form = event.currentTarget
    const values = new FormData(form)
    const email = String(values.get('email') ?? '').trim().toLowerCase()
    const password = String(values.get('password') ?? '')
    if (!email.includes('@')) return setError('Enter a valid email address.')
    if (password.length < 8) return setError('Enter at least 8 characters to start the preview.')
    startSession({ email, name: email.split('@')[0].replace(/[._-]+/g, ' ').replace(/\b\w/g, letter => letter.toUpperCase()) })
    form.reset()
    navigate('/')
  }
  return <AuthLayout title="Sign in">
    <p className="auth-intro">Start a temporary workspace session on this device.</p>
    <form className="auth-form" onSubmit={submit} noValidate>
      <label htmlFor="login-email">Email</label><input id="login-email" name="email" type="email" autoComplete="email" placeholder="you@example.com" required/>
      <label htmlFor="login-password">Password</label><input id="login-password" name="password" type="password" autoComplete="off" placeholder="Any 8 characters" required/>
      {error && <p className="auth-error" role="alert">{error}</p>}
      <button className="saas-primary-button" type="submit">Continue</button>
    </form>
    <p className="auth-switch">New here? <Link to="/register">Create a preview account</Link></p>
  </AuthLayout>
}

export function RegisterPage() {
  const { startSession } = useAccount()
  const navigate = useNavigate()
  const [error, setError] = useState('')
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const form = event.currentTarget
    const values = new FormData(form)
    const name = String(values.get('name') ?? '').trim()
    const email = String(values.get('email') ?? '').trim().toLowerCase()
    const password = String(values.get('password') ?? '')
    if (name.length < 2) return setError('Enter your name.')
    if (!email.includes('@')) return setError('Enter a valid email address.')
    if (password.length < 8) return setError('Enter at least 8 characters to start the preview.')
    startSession({ name, email })
    form.reset()
    navigate('/')
  }
  return <AuthLayout title="Create preview access">
    <p className="auth-intro">Use a temporary display name to personalize this browser session.</p>
    <form className="auth-form" onSubmit={submit} noValidate>
      <label htmlFor="register-name">Name</label><input id="register-name" name="name" autoComplete="name" placeholder="Your name" required/>
      <label htmlFor="register-email">Email</label><input id="register-email" name="email" type="email" autoComplete="email" placeholder="you@example.com" required/>
      <label htmlFor="register-password">Password</label><input id="register-password" name="password" type="password" autoComplete="off" placeholder="Any 8 characters" required/>
      {error && <p className="auth-error" role="alert">{error}</p>}
      <button className="saas-primary-button" type="submit">Create preview session</button>
    </form>
    <p className="auth-switch">Already have a session? <Link to="/login">Sign in</Link></p>
  </AuthLayout>
}
