import { Outlet, useParams } from 'react-router-dom'
import { HistoryRailProvider, useHistoryRail } from './contexts/HistoryRailContext'
import { HistoryRailContent } from './components/HistoryRail'
import PageShell from './components/PageShell'

function ConsultationRailWrapper() {
  const { open, toggle } = useHistoryRail()
  const { id } = useParams()

  return (
    <PageShell
      flush
      consultationRail={{
        open,
        onToggle: toggle,
        label: '历史记录',
        content: <HistoryRailContent activeConversationId={id} />,
      }}
    >
      <Outlet />
    </PageShell>
  )
}

export default function ConsultationLayout() {
  return (
    <HistoryRailProvider>
      <ConsultationRailWrapper />
    </HistoryRailProvider>
  )
}
