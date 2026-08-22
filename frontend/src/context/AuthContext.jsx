import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { authService } from '../services/authService'

const AuthContext = createContext(null)
export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)
  const refreshUser = useCallback(async () => {
    try { const current = await authService.me(); setUser(current); return current }
    catch { setUser(null); return null }
    finally { setLoading(false) }
  }, [])
  useEffect(() => { refreshUser() }, [refreshUser])
  const login = async (credentials) => { await authService.login(credentials); return refreshUser() }
  const register = (data) => authService.register(data)
  const logout = async () => { try { await authService.logout() } finally { setUser(null) } }
  return <AuthContext.Provider value={{ user, loading, login, register, logout, refreshUser, isAuthenticated: !!user }}>{children}</AuthContext.Provider>
}
export const useAuth = () => useContext(AuthContext)
