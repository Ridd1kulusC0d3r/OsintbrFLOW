import { createRoot } from 'react-dom/client'
import { BrazilWorkbench } from './components/brasil/workbench'
// The fragment is never sent to the server or included in HTTP access logs.
const fragmentToken = new URLSearchParams(window.location.hash.slice(1)).get('token')
let sessionToken = fragmentToken || ''
try {
  if (fragmentToken) sessionStorage.setItem('osintbr-session', fragmentToken)
  sessionToken = sessionStorage.getItem('osintbr-session') || sessionToken
  if (fragmentToken) history.replaceState(null, '', window.location.pathname + window.location.search)
} catch {
  // Some embedded browsers deny storage. Keep the fragment for a reload.
}
async function api(path: string, options: RequestInit = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(sessionToken ? { Authorization: `Bearer ${sessionToken}` } : {}),
      ...options.headers
    }
  })
  const data = await response.json()
  if (!response.ok)
    throw new Error(typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail))
  return data
}
createRoot(document.getElementById('root')!).render(<BrazilWorkbench api={api} lab />)
