import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'

type Props = { tab: string; tenant: string; employee: string; request: (path: string, options?: RequestInit) => Promise<any> }
const money = (value: string | number) => 'JPY ' + Number(value).toLocaleString()

function Table({ columns, rows }: { columns: string[]; rows: ReactNode[][] }) {
  if (!rows.length) return <p className="empty">No records match this view.</p>
  return <div className="table-wrap"><table><thead><tr>{columns.map(name => <th key={name}>{name}</th>)}</tr></thead><tbody>{rows.map((row, index) => <tr key={index}>{row.map((cell, cellIndex) => <td key={cellIndex}>{cell}</td>)}</tr>)}</tbody></table></div>
}
function Panel({ title, note, columns, rows }: { title: string; note: string; columns: string[]; rows: ReactNode[][] }) {
  return <section className="section"><div className="section-heading"><h2>{title}</h2><span>{note}</span></div><Table columns={columns} rows={rows}/></section>
}

const nextState: Record<string, string> = { DRAFT: 'VALIDATED', VALIDATED: 'ACCEPTED', ACCEPTED: 'EFFECTIVE_NEXT_CONTRIBUTION' }

export default function PensionOperations({ tab, tenant, employee, request }: Props) {
  const [data, setData] = useState<any>(null)
  const [search, setSearch] = useState('')
  const [reason, setReason] = useState('Reviewed by pension operations')
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  useEffect(() => {
    setData(null); setError(''); setSearch('')
    request('/api/v2/admin/tenants/' + tenant + '/pension/operations').then(setData).catch(e => setError(e.message))
  }, [tenant, request])
  async function advance(id: string, state: string) {
    setBusy(id); setError('')
    try {
      await request('/api/v2/admin/tenants/' + tenant + '/pension/instructions/' + id,
        { method: 'PATCH', body: JSON.stringify({ state, reason }) })
      setData(await request('/api/v2/admin/tenants/' + tenant + '/pension/operations'))
    } catch (e) { setError((e as Error).message) } finally { setBusy('') }
  }
  if (error && !data) return <div className="error" role="alert">{error}</div>
  if (!data) return <div className="loading">Loading pension operations...</div>
  const query = search.toLowerCase().trim()
  const filtered = (rows: any[]) => rows.filter(row => JSON.stringify(row).toLowerCase().includes(query))
  const selected = data.accounts.find((row: any) => row.employee_id === employee)

  return <>
    <div className="operations-heading"><span>Plan: {data.plan.id}</span><span>As of {data.as_of}</span></div>
    {error && <div className="error" role="alert">{error}</div>}
    {tab === 'Plan operations' && <><div className="metrics"><div className="metric"><span>Participant accounts</span><strong>{data.accounts.length}</strong></div><div className="metric"><span>Investment funds</span><strong>{data.funds.length}</strong></div><div className="metric"><span>Open exceptions</span><strong>{data.exceptions.filter((row: any) => row.status === 'OPEN').length}</strong></div></div><section className="section"><div className="section-heading"><h2>Corporate pension plan</h2><span>{data.plan.status}</span></div><div className="detail-grid"><div><span>Plan name</span><strong>{data.plan.name}</strong></div><div><span>Effective from</span><strong>{data.plan.effective_on}</strong></div><div><span>External access</span><strong>Managed in MCP Access Management</strong></div></div></section></>}
    {['Participants', 'Investment funds', 'Exceptions'].includes(tab) && <div className="inline-filter"><label>Search records<input value={search} onChange={e => setSearch(e.target.value)} placeholder="Employee, fund or status"/></label></div>}
    {tab === 'Participants' && <Panel title="Pension participant accounts" note={filtered(data.accounts).length + ' shown'} columns={['Employee', 'Account balance', 'Funds']} rows={filtered(data.accounts).map((row: any) => [row.employee_id, money(row.balance_jpy), row.positions.length])}/>}
    {tab === 'Fund positions' && <Panel title={'Fund positions - ' + employee} note={selected ? money(selected.balance_jpy) + ' total' : 'No account'} columns={['Fund', 'Category', 'Units', 'NAV', 'NAV date', 'Value']} rows={(selected?.positions || []).map((row: any) => [row.fund_name, row.category, Number(row.units).toLocaleString(), money(row.nav_jpy), row.nav_date, money(row.value_jpy)])}/>}
    {tab === 'Investment funds' && <Panel title="Plan product catalog" note={filtered(data.funds).length + ' shown'} columns={['Fund ID', 'Fund', 'Category', 'NAV', 'Annual fee']} rows={filtered(data.funds).map((row: any) => [row.id, row.name, row.category, money(row.latest_nav_jpy), Number(row.annual_fee_percent) + '%'])}/>}
    {tab === 'Instruction queue' && <><div className="operations-review"><label>Review note<input value={reason} onChange={e => setReason(e.target.value)} minLength={3} maxLength={200}/></label></div><Panel title="Future contribution instructions" note={data.instructions.length + ' records'} columns={['Instruction', 'Employee', 'Allocation', 'State', 'Review']} rows={data.instructions.map((row: any) => [row.instruction_id, row.employee_id, row.allocations.map((line: any) => line.fund_id + ' ' + Number(line.percentage) + '%').join(', '), row.state, nextState[row.state] ? <button type="button" disabled={Boolean(busy) || reason.trim().length < 3} onClick={() => advance(row.instruction_id, nextState[row.state])}>{busy === row.instruction_id ? 'Saving...' : 'Advance to ' + nextState[row.state].replaceAll('_', ' ')}</button> : 'Effective'])}/></>}
    {tab === 'Switch drafts' && <Panel title="Current holding switch drafts" note="Drafts do not change fund positions" columns={['Draft', 'Employee', 'From fund', 'To fund', 'Units', 'State']} rows={data.switch_drafts.map((row: any) => [row.id, row.employee_id, row.from_fund_id, row.to_fund_id, Number(row.units).toLocaleString(), row.state])}/>}
    {tab === 'Exceptions' && <Panel title="Pension reconciliation cases" note={filtered(data.exceptions).length + ' shown'} columns={['Case', 'Employee', 'Source', 'Break type', 'Status']} rows={filtered(data.exceptions).map((row: any) => [row.id, row.employee_id, row.source_reference, row.break_type.replaceAll('_', ' '), row.status])}/>}
    {tab === 'Reports' && <Panel title="Pension statements" note={data.statements.length + ' records'} columns={['Statement', 'Employee', 'Period', 'As of']} rows={data.statements.map((row: any) => [row.id, row.employee_id, row.period, row.as_of])}/>}
  </>
}
