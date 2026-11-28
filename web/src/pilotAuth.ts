import { UserManager, WebStorageStateStore } from 'oidc-client-ts'

const authority = import.meta.env.VITE_OIDC_AUTHORITY ?? ''
const clientId = import.meta.env.VITE_OIDC_CLIENT_ID ?? ''
const redirectUri = import.meta.env.VITE_OIDC_REDIRECT_URI || `${window.location.origin}/pilot/callback`

export const oidcConfigured = Boolean(authority && clientId)

let userManager: UserManager | null = null

function manager() {
  if (!oidcConfigured) return null
  userManager ??= new UserManager({
    authority,
    client_id: clientId,
    redirect_uri: redirectUri,
    post_logout_redirect_uri: `${window.location.origin}/pilot`,
    response_type: 'code',
    scope: 'openid profile email',
    userStore: new WebStorageStateStore({ store: window.sessionStorage }),
    stateStore: new WebStorageStateStore({ store: window.sessionStorage }),
    automaticSilentRenew: false,
    loadUserInfo: false,
  })
  return userManager
}

export async function readOidcUser() {
  const instance = manager()
  if (!instance) return null
  return instance.getUser()
}

export async function beginOidcSignIn() {
  const instance = manager()
  if (!instance) throw new Error('Configure VITE_OIDC_AUTHORITY and VITE_OIDC_CLIENT_ID to enable sign-in.')
  await instance.signinRedirect()
}

export async function completeOidcSignIn() {
  const instance = manager()
  if (!instance) throw new Error('OIDC is not configured for this deployment.')
  return instance.signinRedirectCallback()
}

export async function endOidcSession() {
  const instance = manager()
  if (instance) await instance.removeUser()
}
