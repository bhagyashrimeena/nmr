import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'

type Props = { tab: string; tenant: string; employee: string; request: (path: string, options?: RequestInit) => Promise<any> }
function Table({ columns, rows }: { columns: string[]; rows: ReactNode[][] }) {
  if (!rows.length) return <p className="empty">No records match this view.</p>
  return <div className="table-wrap"><table><thead><tr>{columns.map(x => <th key={x}>{x}</th>)}</tr></thead><tbody>{rows.map((row, i) => <tr key={i}>{row.map((cell, j) => <td key={j}>{cell}</td>)}</tr>)}</tbody></table></div>
}
function Panel({ title, rows, columns }: { title: string; rows: ReactNode[][]; columns: string[] }) {
  return <section className="section"><div className="section-heading"><h2>{title}</h2><span>{rows.length} records</span></div><Table columns={columns} rows={rows}/></section>
}
const grantNext: Record<string, string> = { PROPOSED: 'APPROVED', APPROVED: 'ISSUED', ISSUED: 'ACTIVE' }
const releaseNext: Record<string, string> = { PREPARED: 'VERIFIED', VERIFIED: 'APPROVED', APPROVED: 'SIMULATED_RELEASED' }
const stateLabel = (state: string) => state === 'SIMULATED_RELEASED' ? 'Released' : state.replaceAll('_', ' ')

export default function EquityOperations({ tab, tenant, employee, request }: Props) {
  const [data, setData] = useState<any>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState('')
  const [reason, setReason] = useState('Reviewed by equity operations')
  const [search, setSearch] = useState('')
  const base = '/api/v2/admin/tenants/' + tenant + '/equity'
  useEffect(() => { setData(null); setError(''); request(base + '/operations').then(setData).catch(e => setError(e.message)) }, [base, request])
  async function advance(kind: 'grants' | 'releases', id: string, state: string) {
    setBusy(id); setError('')
    try {
      await request(base + '/' + kind + '/' + id, { method: 'PATCH', body: JSON.stringify({ state, reason }) })
      setData(await request(base + '/operations'))
    } catch (e) { setError((e as Error).message) } finally { setBusy('') }
  }
  if (error && !data) return <div className="error" role="alert">{error}</div>
  if (!data) return <div className="loading">Loading equity operations...</div>
  const visible = (rows: any[]) => rows.filter(row => JSON.stringify(row).toLowerCase().includes(search.toLowerCase()))
  return <>
    <div className="operations-heading"><span>Plan: {data.plan.id}</span><span>As of {data.as_of}</span></div>
    {error && <div className="error" role="alert">{error}</div>}
    {tab === 'Equity plan' && <><div className="metrics"><div className="metric"><span>Authorized units</span><strong>{data.plan.authorized_units.toLocaleString()}</strong></div><div className="metric"><span>Issued units</span><strong>{data.plan.issued_units.toLocaleString()}</strong></div><div className="metric"><span>Remaining reserve</span><strong>{data.plan.remaining_units.toLocaleString()}</strong></div></div><section className="section"><div className="section-heading"><h2>{data.plan.name}</h2><span>{data.plan.status}</span></div><p>Proposed awards are excluded from issued units. Release review does not confirm custody delivery.</p></section></>}
    {['Grant register', 'Vesting schedule', 'Release queue', 'Equity exceptions'].includes(tab) && <div className="inline-filter"><label>Search records<input value={search} onChange={e => setSearch(e.target.value)} placeholder="Grant, employee or state"/></label></div>}
    {['Grant register', 'Release queue'].includes(tab) && <div className="operations-review"><label>Review note<input value={reason} onChange={e => setReason(e.target.value)} minLength={3} maxLength={200}/></label></div>}
    {tab === 'Grant register' && <Panel title="Award grants" columns={['Grant', 'Employee', 'Type', 'Granted', 'Vested', 'State', 'Review']} rows={visible(data.grants).map((x: any) => [x.id, x.employee_id, x.award_type, x.granted_units, x.vested_unreleased_units + x.released_units + x.exercised_units, stateLabel(x.state), grantNext[x.state] ? <button disabled={Boolean(busy) || reason.trim().length < 3} onClick={() => advance('grants', x.id, grantNext[x.state])}>{busy === x.id ? 'Saving...' : 'Advance to ' + stateLabel(grantNext[x.state])}</button> : 'Current'])}/>}
    {tab === 'Vesting schedule' && <Panel title={'Vesting tranches - ' + employee} columns={['Grant', 'Vest date', 'Units', 'State']} rows={visible(data.grants.filter((x: any) => x.employee_id === employee).flatMap((x: any) => x.tranches.map((t: any) => ({ ...t, grant_id: x.id })))).map((x: any) => [x.grant_id, x.vest_date, x.units, stateLabel(x.state)])}/>}
    {tab === 'Release queue' && <Panel title="Release review" columns={['Release', 'Grant', 'Units', 'Withholding units', 'State', 'Custody reference', 'Review']} rows={visible(data.releases).map((x: any) => [x.id, x.grant_id, x.units, x.withholding_units, stateLabel(x.state), x.custody_confirmation || 'Pending', releaseNext[x.state] ? <button disabled={Boolean(busy) || reason.trim().length < 3} onClick={() => advance('releases', x.id, releaseNext[x.state])}>{busy === x.id ? 'Saving...' : 'Advance to ' + stateLabel(releaseNext[x.state])}</button> : 'Complete'])}/>}
    {tab === 'Equity exceptions' && <Panel title="Equity exceptions" columns={['Case', 'Employee', 'Type', 'Status']} rows={visible(data.exceptions).map((x: any) => [x.id, x.employee_id, stateLabel(x.break_type), x.status])}/>}
  </>
}
