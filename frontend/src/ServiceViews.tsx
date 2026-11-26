import { useEffect, useState } from 'react'
import StockOperations from './StockOperations'
import DomainWorkbench from './DomainWorkbench'
import V2ParticipantRecord from './V2ParticipantRecord'
import PensionOperations from './PensionOperations'
import EquityOperations from './EquityOperations'
import CustodyOperations from './CustodyOperations'
import WellnessOperations from './WellnessOperations'

export type ServiceKey = 'stock' | 'pension' | 'wellness' | 'custody' | 'equity'
type Request = (path: string, options?: RequestInit) => Promise<any>
type Props = { page: ServiceKey; summary: any; tenant: string; employee: string; request: Request; onRefresh: () => Promise<void> }

const money = (value: number | null | undefined) => value == null ? '—' : `¥${value.toLocaleString('en-US')}`

function Metrics({ entries }: { entries: { label: string; value: string; detail?: string }[] }) {
  return <div className="metrics">{entries.map(e => <div className="metric" key={e.label}><span>{e.label}</span><strong>{e.value}</strong>{e.detail && <small>{e.detail}</small>}</div>)}</div>
}

function Table({ columns, rows }: { columns: string[]; rows: (string | number)[][] }) {
  if (!rows.length) return <p className="empty">No records match this view.</p>
  return <div className="table-wrap"><table><thead><tr>{columns.map(c => <th key={c}>{c}</th>)}</tr></thead><tbody>{rows.map((r, i) => <tr key={i}>{r.map((value, j) => <td key={j}>{value}</td>)}</tr>)}</tbody></table></div>
}

function Panel({ title, note, children }: { title: string; note?: string; children: React.ReactNode }) {
  return <section className="section"><div className="section-heading"><h2>{title}</h2>{note && <span>{note}</span>}</div>{children}</section>
}

const tabs: Record<ServiceKey, string[]> = {
  stock: ['Workbench', 'Overview', 'Contributions', 'Purchases', 'Activity', 'Statements',
          'Plan operations', 'Members', 'Payroll batches', 'Purchase cycles', 'Transfer requests', 'Exceptions'],
  pension: ['Workbench', 'Overview', 'Contributions', 'Valuations', 'Projection', 'Statements',
            'Plan operations', 'Participants', 'Fund positions', 'Investment funds',
            'Instruction queue', 'Switch drafts', 'Exceptions', 'Reports'],
  wellness: ['Workbench', 'Resources', 'Progress', 'Savings calculator', 'Program overview', 'Content library', 'Benefit rules', 'Seminars'],
  custody: ['Workbench', 'Overview', 'Valuations', 'Dividends', 'Corporate actions', 'Settlements', 'Statements', 'Account registry', 'Position detail', 'Dividend processing', 'Action register', 'Settlement monitor'],
  equity: ['Workbench', 'Awards', 'Vesting', 'Statements', 'Equity plan', 'Grant register', 'Vesting schedule', 'Release queue', 'Equity exceptions'],
}
const stockOperationsTabs = ['Plan operations', 'Members', 'Payroll batches', 'Purchase cycles', 'Transfer requests', 'Exceptions']
const pensionOperationsTabs = ['Plan operations', 'Participants', 'Fund positions', 'Investment funds', 'Instruction queue', 'Switch drafts', 'Exceptions', 'Reports']
const equityOperationsTabs = ['Equity plan', 'Grant register', 'Vesting schedule', 'Release queue', 'Equity exceptions']
const custodyOperationsTabs = ['Account registry', 'Position detail', 'Dividend processing', 'Action register', 'Settlement monitor']
const wellnessOperationsTabs = ['Program overview', 'Content library', 'Benefit rules', 'Seminars']

export default function ServiceViews({ page, summary, tenant, employee, request, onRefresh }: Props) {
  const [tab, setTab] = useState('')
  const [topic, setTopic] = useState('all')
  const [search, setSearch] = useState('')
  const [wellnessResults, setWellnessResults] = useState<any>(null)
  const [monthly, setMonthly] = useState(15000)
  const [years, setYears] = useState(10)
  const [rate, setRate] = useState(0)
  const [projection, setProjection] = useState<any>(null)
  const [working, setWorking] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => { setTab(tabs[page][0]); setTopic('all'); setSearch(''); setWellnessResults(null); setProjection(null); setError('') }, [page, employee])
  const active = tabs[page].includes(tab) ? tab : tabs[page][0]

  async function filterWellness() {
    setWorking(true); setError('')
    try {
      const params = new URLSearchParams()
      if (topic !== 'all') params.set('topic', topic)
      if (search.trim()) params.set('search', search.trim())
      setWellnessResults(await request(`/api/v1/admin/tenants/${tenant}/employees/${employee}/wellness/resources?${params}`))
    } catch (e) { setError((e as Error).message) } finally { setWorking(false) }
  }

  async function calculate(kind: 'wellness' | 'pension') {
    setWorking(true); setError('')
    try {
      const base = `/api/v1/admin/tenants/${tenant}/employees/${employee}`
      const path = kind === 'wellness'
        ? `${base}/wellness/savings-projection?monthly_jpy=${monthly}&years=${years}&annual_return_pct=${rate}`
        : `${base}/pension/projection?monthly_contribution_jpy=${monthly}&years=${years}&annual_return_pct=${rate}`
      setProjection(await request(path))
    } catch (e) { setError((e as Error).message) } finally { setWorking(false) }
  }

  async function markProgress(resourceId: string, status: string) {
    setWorking(true); setError('')
    try {
      await request(`/api/v1/admin/tenants/${tenant}/employees/${employee}/wellness/progress/${resourceId}`,
        { method: 'PATCH', body: JSON.stringify({ status: status === 'completed' ? 'not_started' : 'completed' }) })
      setWellnessResults(null)
      await onRefresh()
    } catch (e) { setError((e as Error).message) } finally { setWorking(false) }
  }

  const data = summary[page]
  if (!data && page === 'wellness' && active !== 'Workbench') return <div className="empty service-empty">No wellness account is recorded for this employee.</div>
  return <>
    <div className="domain-navigation">
      <div className="domain-navigation-group">
        <span>Provider workspace</span>
        <div className="subtabs" role="tablist" aria-label="Provider workspaces">
          {['Workbench', ...(
            page === 'stock' ? stockOperationsTabs : page === 'pension' ? pensionOperationsTabs :
            page === 'equity' ? equityOperationsTabs : page === 'custody' ? custodyOperationsTabs :
            wellnessOperationsTabs
          )].map(name => <button type="button" role="tab" aria-selected={active === name}
              className={active === name ? 'selected' : ''} key={name}
              onClick={() => {setTab(name);setProjection(null);setError('')}}>{name}</button>)}
        </div>
      </div>
      <div className="domain-navigation-group domain-navigation-employee">
        <span>Participant account</span>
        <div className="subtabs" role="tablist" aria-label="Participant account views">
          {tabs[page].filter(name => name !== 'Workbench' && !(
            page === 'stock' ? stockOperationsTabs : page === 'pension' ? pensionOperationsTabs :
            page === 'equity' ? equityOperationsTabs : page === 'custody' ? custodyOperationsTabs :
            wellnessOperationsTabs
          ).includes(name)).map(name => <button type="button" role="tab" aria-selected={active === name}
              className={active === name ? 'selected' : ''} key={name}
              onClick={() => {setTab(name);setProjection(null);setError('')}}>{name}</button>)}
        </div>
      </div>
    </div>
    {error && <div className="error" role="alert">{error}</div>}
    {active === 'Workbench' && <DomainWorkbench
      key={page + ':' + tenant} domain={page} tenant={tenant} employee={employee}
      request={request} onNavigate={next => {setTab(next);setError('');setProjection(null)}}
    />}
    {page === 'stock' && stockOperationsTabs.includes(active) && <StockOperations tab={active} tenant={tenant} request={request} onRefresh={onRefresh}/>}
    {page === 'pension' && pensionOperationsTabs.includes(active) && <PensionOperations tab={active} tenant={tenant} employee={employee} request={request}/>}
    {page === 'equity' && equityOperationsTabs.includes(active) && <EquityOperations tab={active} tenant={tenant} employee={employee} request={request}/>}
    {page === 'custody' && custodyOperationsTabs.includes(active) && <CustodyOperations tab={active} tenant={tenant} employee={employee} request={request}/>}
    {page === 'wellness' && wellnessOperationsTabs.includes(active) && <WellnessOperations tab={active} tenant={tenant} request={request}/>}

    {page !== 'wellness' &&
      !(page === 'stock' && stockOperationsTabs.includes(active)) &&
      !(page === 'pension' && pensionOperationsTabs.includes(active)) &&
      !(page === 'equity' && equityOperationsTabs.includes(active)) &&
      !(page === 'custody' && custodyOperationsTabs.includes(active)) &&
      <V2ParticipantRecord
        page={page as 'stock' | 'pension' | 'custody' | 'equity'}
        tab={active} tenant={tenant} employee={employee} request={request} refreshKey={summary}
      />
    }

    {page === 'wellness' && active === 'Resources' && <><div className="notice">Suggested resources reflect the employee's selected topics. Content is not personal financial advice.</div><div className="inline-filter"><label>Topic<select value={topic} onChange={e => setTopic(e.target.value)}><option value="all">All topics</option>{data.topics.map((t: string) => <option key={t} value={t}>{t}</option>)}</select></label><label>Search<input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search resources" onKeyDown={e => { if (e.key === 'Enter') filterWellness() }}/></label><button onClick={filterWellness} disabled={working}>{working ? 'Searching…' : 'Apply filters'}</button><button onClick={() => { setTopic('all'); setSearch(''); setWellnessResults(null) }}>Clear</button></div><div className="resource-grid">{(wellnessResults || data).resources.map((r: any) => <article className="resource" key={r.id}><span className="eyebrow">{r.topic} · {r.progress.replace('_', ' ')}</span><h3>{r.title}</h3><p>{r.description}</p><div>{r.content}</div><button className="progress-button" disabled={working} onClick={() => markProgress(r.id, r.progress)}>{r.progress === 'completed' ? 'Reset progress' : 'Mark completed'}</button></article>)}</div>{!(wellnessResults || data).resources.length && <p className="empty">No resources match the current search.</p>}<Panel title="Recommended reading" note={`Preference: ${data.preferred_topic || 'none'}`}><Table columns={['Resource', 'Topic', 'Progress']} rows={data.recommended_resources.map((r: any) => [r.title, r.topic, r.progress.replace('_', ' ')])}/></Panel></>}
    {page === 'wellness' && active === 'Progress' && <><Metrics entries={[{ label: 'Completed resources', value: `${data.progress.completed}` }, { label: 'In progress', value: `${data.progress.in_progress}` }, { label: 'Catalog resources', value: `${data.resources.length}` }]}/><Panel title="Learning progress"><Table columns={['Resource', 'Topic', 'Status']} rows={data.resources.map((r: any) => [r.title, r.topic, r.progress.replace('_', ' ')])}/></Panel></>}
    {page === 'wellness' && active === 'Savings calculator' && <><div className="notice">Projected savings assume contributions at the end of each month. Returns are not guaranteed.</div><div className="calculator"><label>Monthly amount (JPY)<input type="number" min="0" max="1000000" value={monthly} onChange={e => setMonthly(Number(e.target.value))}/></label><label>Years<input type="number" min="1" max="40" value={years} onChange={e => setYears(Number(e.target.value))}/></label><label>Annual return assumption (%)<input type="number" min="0" max="12" step="0.1" value={rate} onChange={e => setRate(Number(e.target.value))}/></label><button className="primary" disabled={working} onClick={() => calculate('wellness')}>{working ? 'Calculating…' : 'Calculate'}</button></div>{projection && <Metrics entries={[{ label: 'Total contributions', value: money(projection.projection.total_contributed_jpy) }, { label: 'Projected growth', value: money(projection.projection.illustrative_growth_jpy) }, { label: 'Projected future value', value: money(projection.projection.illustrative_future_value_jpy) }]}/>}</>}

  </>
}
