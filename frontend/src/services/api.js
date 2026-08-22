const API_URL = import.meta.env.VITE_API_URL || '/backend'

export class ApiError extends Error {
  constructor(message, status) { super(message); this.status = status }
}

export async function api(path, options = {}) {
  let response
  try {
    response = await fetch(`${API_URL}${path}`, {
      credentials: 'include',
      headers: { ...(options.body ? { 'Content-Type': 'application/json' } : {}), ...options.headers },
      ...options,
    })
  } catch {
    throw new ApiError('Unable to reach MediVeria. Check that the service is running.', 0)
  }
  const type = response.headers.get('content-type') || ''
  const body = type.includes('application/json') ? await response.json().catch(() => null) : null
  if (!response.ok) throw new ApiError(body?.detail || body?.message || 'Something went wrong. Please try again.', response.status)
  return body
}
