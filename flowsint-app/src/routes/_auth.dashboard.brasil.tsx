import { createFileRoute } from '@tanstack/react-router'
import { BrazilWorkbench } from '@/components/brasil/workbench'
import { fetchWithAuth } from '@/api/api'
export const Route = createFileRoute('/_auth/dashboard/brasil')({ component: BrazilPage })
function BrazilPage() {
  return <BrazilWorkbench api={fetchWithAuth} />
}
