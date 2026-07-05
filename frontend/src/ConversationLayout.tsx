import { Outlet, useParams } from 'react-router-dom'
import { HistoryRailProvider, useHistoryRail } from './contexts/HistoryRailContext'
import { HistoryRailContent } from './components/HistoryRail'
import PageShell from './components/PageShell'
import { useT } from './contexts/LanguageContext'

function ConversationLayoutInner() {
  const { open, toggle } = useHistoryRail()
  const { id } = useParams()
  const t = useT()

  return (
    <PageShell
      flush
      sidebar={<HistoryRailContent activeConversationId={id} />}
      sidebarSizing="fit"
      sidebarLabel={t('history.title')}
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
