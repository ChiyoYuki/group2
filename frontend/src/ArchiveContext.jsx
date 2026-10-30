import { createContext, useContext, useEffect, useState } from 'react'
import { readProjects, request } from './api'

const ArchiveContext = createContext(null)

export function ArchiveProvider({ children }) {
  const [revision, setRevision] = useState(0)
  const [archive, setArchive] = useState({ projects: [], catalog: { themes: [], cohorts: [] }, overview: null, loading: true, error: '' })
  useEffect(() => {
    const controller = new AbortController()
    Promise.all([
      readProjects(controller.signal),
      request('/catalog', { signal: controller.signal }),
      request('/overview', { signal: controller.signal }),
    ]).then(([projects, catalog, overview]) => {
      setArchive({ projects, catalog, overview, loading: false, error: '' })
    }).catch(error => {
      if (!controller.signal.aborted) setArchive(previous => ({ ...previous, loading: false, error: error.message }))
    })
    return () => controller.abort()
  }, [revision])
  function reload() {
    setArchive(previous => ({ ...previous, loading: true, error: '' }))
    setRevision(value => value + 1)
  }
  return <ArchiveContext.Provider value={{ ...archive, reload }}>{children}</ArchiveContext.Provider>
}

export function useArchive() {
  return useContext(ArchiveContext)
}
