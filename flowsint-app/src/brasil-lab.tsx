import { createRoot } from 'react-dom/client'
import { BrazilWorkbench } from './components/brasil/workbench'
async function api(path: string, options: RequestInit = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...options.headers }
  })
  const data = await response.json()
  if (!response.ok)
    throw new Error(typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail))
  return data
}
createRoot(document.getElementById('root')!).render(<BrazilWorkbench api={api} lab />)
