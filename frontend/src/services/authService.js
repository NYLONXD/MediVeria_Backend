import { api } from './api'

export const authService = {
  register: (payload) => api('/auth/register', { method: 'POST', body: JSON.stringify(payload) }),
  login: (payload) => api('/auth/login', { method: 'POST', body: JSON.stringify(payload) }),
  me: () => api('/auth/me'),
  logout: () => api('/auth/logout', { method: 'POST' }),
  requestPasswordReset: (email) => api(`/auth/forget-password?email=${encodeURIComponent(email)}`, { method: 'POST' }),
}
