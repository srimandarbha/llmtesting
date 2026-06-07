/**
 * useAuth — SSO-Ready Authentication Hook
 *
 * CURRENT BEHAVIOUR (localStorage stub):
 *   Reads/writes a JSON user object from localStorage under the key `sre_auth_user`.
 *   Any component can call `useAuth()` to get the current user and update identity.
 *
 * TO INTEGRATE SSO (OIDC — Keycloak / Azure AD / Okta / Google):
 *   1. Install your OIDC client library (e.g. `oidc-client-ts` or `@azure/msal-react`).
 *   2. Replace the body of this hook with the OIDC provider's hook/context call.
 *   3. Map the OIDC profile to the `AuthUser` shape below.
 *   4. NOTHING else in the app needs to change — all pages consume this hook.
 *
 * OIDC stub (commented) shows where to plug in:
 *   const { user, isAuthenticated } = useOidcUser()   // ← swap here
 */

import { useState, useCallback, createContext, useContext, ReactNode } from 'react'
import React from 'react'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface AuthUser {
  /** Full display name, e.g. "Jane Smith" */
  displayName: string
  /** Email or UPN — comes from OIDC claim `email` or `upn` */
  email: string
  /** Role — e.g. "SRE", "SRE Lead", "On-Call". Comes from OIDC `roles` claim */
  role: string
  /** Optional: shift label, e.g. "Morning", "Night", "APAC" */
  shift?: string
}

export interface AuthContextValue {
  user: AuthUser
  isAuthenticated: boolean
  /** Update the local identity (localStorage stub only — no-op when real SSO is active) */
  updateUser: (partial: Partial<AuthUser>) => void
  /** Returns a formatted shift identifier string for handover forms */
  shiftIdentifier: string
}

// ---------------------------------------------------------------------------
// Defaults
// ---------------------------------------------------------------------------

const DEFAULT_USER: AuthUser = {
  displayName: '',
  email: '',
  role: 'SRE',
  shift: '',
}

const STORAGE_KEY = 'sre_auth_user'

function loadUser(): AuthUser {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) return { ...DEFAULT_USER, ...JSON.parse(raw) }
  } catch {
    // ignore parse errors
  }
  return DEFAULT_USER
}

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------

const AuthContext = createContext<AuthContextValue | null>(null)

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser>(loadUser)

  const isAuthenticated = Boolean(user.displayName)

  const updateUser = useCallback((partial: Partial<AuthUser>) => {
    setUser(prev => {
      const next = { ...prev, ...partial }
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
      return next
    })
  }, [])

  const shiftIdentifier = [
    user.displayName,
    user.shift ? `· ${user.shift} Shift` : '',
  ].filter(Boolean).join(' ').trim()

  return React.createElement(
    AuthContext.Provider,
    { value: { user, isAuthenticated, updateUser, shiftIdentifier } },
    children
  )
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within <AuthProvider>')
  return ctx
}
