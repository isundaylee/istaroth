import { Outlet, useParams } from 'react-router-dom'
import { HistoryRailProvider, useHistoryRail } from './contexts/HistoryRailContext'
import { HistoryRailContent } from './components/HistoryRail'
import PageShell from './components/PageShell'

function ConversationLayoutInner() {
  const { open, toggle } = useHistoryRail()
  const { id } = useParams()

  return (
    <PageShell
      flush
      sidebar={<HistoryRailContent activeConversationId={id} />}
      sidebarSizing="fit"
      sidebarLabel="历史记录"
      sidebarCloseable
      sidebarClosed={!open}
      onSidebarToggle={toggle}
    >
      <Outlet />
    </PageShell>
  )
}

export default function ConversationLayout() {
  return (
    <HistoryRailProvider>
      <ConversationLayoutInner />
    </HistoryRailProvider>
  )
}
