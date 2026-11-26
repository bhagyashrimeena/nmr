import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'

type Props = { tab: string; tenant: string; request: (path: string, options?: RequestInit) => Promise<any> }
function Panel({ title, columns, rows }: { title: string; columns: string[]; rows: ReactNode[][] }) {
  return <section className="section"><div className="section-heading"><h2>{title}</h2><span>{rows.length} records</span></div>{rows.length ? <div className="table-wrap"><table><thead><tr>{columns.map(x => <th key={x}>{x}</th>)}</tr></thead><tbody>{rows.map((r, i) => <tr key={i}>{r.map((x, j) => <td key={j}>{x}</td>)}</tr>)}</tbody></table></div> : <p className="empty">No records match this view.</p>}</section>
}
const nextState: Record<string, string> = { DRAFT: 'IN_REVIEW', IN_REVIEW: 'APPROVED', APPROVED: 'PUBLISHED', PUBLISHED: 'ARCHIVED' }
const label = (value: string) => value.replaceAll('_', ' ')

export default function WellnessOperations({ tab, tenant, request }: Props) {
  const [data, setData] = useState<any>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState('')
  const [reason, setReason] = useState('Reviewed by wellness editorial')
  const base = '/api/v2/admin/tenants/' + tenant + '/wellness'
  useEffect(() => { setData(null); setError(''); request(base + '/operations').then(setData).catch(e => setError(e.message)) }, [base, request])
  async function advance(id: string, state: string) {
    setBusy(id); setError('')
    try {
      await request(base + '/content/' + id, { method: 'PATCH', body: JSON.stringify({ state, reason }) })
      setData(await request(base + '/operations'))
    } catch (e) { setError((e as Error).message) } finally { setBusy('') }
  }
  if (error && !data) return <div className="error" role="alert">{error}</div>
  if (!data) return <div className="loading">Loading wellness operations...</div>
  return <>
    <div className="operations-heading"><span>Financial wellness</span><span>As of {data.as_of}</span></div>
    {error && <div className="error" role="alert">{error}</div>}
    {tab === 'Program overview' && <div className="metrics"><div className="metric"><span>Published content</span><strong>{data.content.filter((x: any) => x.state === 'PUBLISHED' && x.review_expires_on >= data.as_of).length}</strong></div><div className="metric"><span>Current benefit rules</span><strong>{data.benefit_rules.length}</strong></div><div className="metric"><span>Scheduled seminars</span><strong>{data.seminars.length}</strong></div></div>}
    {tab === 'Content library' && <><div className="operations-review"><label>Editorial note<input value={reason} onChange={e => setReason(e.target.value)} minLength={3} maxLength={200}/></label></div><Panel title="Education content" columns={['Content', 'Title', 'Category', 'Revision', 'Review expiry', 'State', 'Review']} rows={data.content.map((x: any) => [x.id, x.title, x.category, x.revision, x.review_expires_on, label(x.state), nextState[x.state] ? <button disabled={Boolean(busy) || reason.trim().length < 3 || (nextState[x.state] === 'PUBLISHED' && x.review_expires_on < data.as_of)} onClick={() => advance(x.id, nextState[x.state])}>{busy === x.id ? 'Saving...' : 'Advance to ' + label(nextState[x.state])}</button> : 'Archived'])}/></>}
    {tab === 'Benefit rules' && <Panel title="Employer benefit rules" columns={['Rule', 'Benefit', 'Source', 'Effective', 'Review expiry', 'Explanation']} rows={data.benefit_rules.map((x: any) => [x.id, label(x.benefit_key), x.source_reference, x.effective_date, x.review_expires_on, x.rule_text])}/>}
    {tab === 'Seminars' && <Panel title="Seminar schedule" columns={['Seminar', 'Title', 'Starts', 'Registered', 'Capacity', 'State']} rows={data.seminars.map((x: any) => [x.id, x.title, String(x.starts_at).slice(0, 16), x.registrations, x.capacity, x.status])}/>}
  </>
}
