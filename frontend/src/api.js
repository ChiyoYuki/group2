// The frontend consumes the public API; it has no dataset registry or sample records.
export const API_ORIGIN = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')

export async function request(path, options = {}) {
  const response = await fetch(`${API_ORIGIN}/api/v1${path}`, options)
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    const error = new Error(data.error || `请求失败（${response.status}）`)
    error.status = response.status
    throw error
  }
  return data
}

export async function readProjects(signal) {
  const first = await request('/projects?page_size=100', { signal })
  const items = [...first.items]
  for (let page = 2; items.length < first.total; page += 1) {
    const next = await request(`/projects?page_size=100&page=${page}`, { signal })
    if (!next.items.length) break
    items.push(...next.items)
  }
  return items
}

export function mediaUrl(path) {
  if (!path) return undefined
  try {
    const url = new URL(path, API_ORIGIN || window.location.origin)
    return ['http:', 'https:'].includes(url.protocol) ? url.href : undefined
  } catch {
    return undefined
  }
}

export function projectName(project) {
  return project.short_title || project.title
}

export function cohortName(project) {
  return project.cohort?.name || '届次待补充'
}

export function projectPlace(project) {
  return project.location || '地点待补充'
}
