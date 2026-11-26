import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'

type Props = { tab: string; tenant: string; employee: string; request: (path: string, options?: RequestInit) => Promise<any> }
function Panel({ title, columns, rows }: { title: string; columns: string[]; rows: ReactNode[][] }) {
  return <section className="section"><div className="section-heading"><h2>{title}</h2><span>{rows.length} records</span></div>{rows.length ? <div className="table-wrap"><table><thead><tr>{columns.map(x => <th key={x}>{x}</th>)}</tr></thead><tbody>{rows.map((r, i) => <tr key={i}>{r.map((x, j) => <td key={j}>{x}</td>)}</tr>)}</tbody></table></div> : <p className="empty">No records match this view.</p>}</section>
}
const actionNext: Record<string, string> = { ANNOUNCED: 'ENTITLEMENT_CAPTURED', ENTITLEMENT_CAPTURED: 'EFFECTIVE', EFFECTIVE: 'POSTED', POSTED: 'RECONCILED' }
const label = (value: string) => value.replaceAll('_', ' ')

export default function CustodyOperations({ tab, tenant, employee, request }: Props) {
  const [data, setData] = useState<any>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState('')
  const [reason, setReason] = useState('Reviewed by custody operations')
  const base = '/api/v2/admin/tenants/' + tenant + '/custody'
  useEffect(() => { setData(null); setError(''); request(base + '/operations').then(setData).catch(e => setError(e.message)) }, [base, request])
  async function advance(kind: 'actions' | 'dividends', id: string, state: string) {
    setBusy(id); setError('')
    try {
      await request(base + '/' + kind + '/' + id, { method: 'PATCH', body: JSON.stringify({ state, reason }) })
      setData(await request(base + '/operations'))
    } catch (e) { setError((e as Error).message) } finally { setBusy('') }
  }
  if (error && !data) return <div className="error" role="alert">{error}</div>
  if (!data) return <div className="loading">Loading custody operations...</div>
  const account = data.accounts.find((x: any) => x.employee_id === employee)
  return <>
    <div className="operations-heading"><span>Custody operations</span><span>As of {data.as_of}</span></div>
    {error && <div className="error" role="alert">{error}</div>}
    {tab === 'Account registry' && <><div className="metrics"><div className="metric"><span>Custody accounts</span><strong>{data.accounts.length}</strong></div><div className="metric"><span>Pending transfers</span><strong>{data.transfers.filter((x: any) => x.settlement_state === 'PENDING').length}</strong></div><div className="metric"><span>Open actions</span><strong>{data.actions.filter((x: any) => x.state !== 'RECONCILED').length}</strong></div></div><Panel title="Account registry" columns={['Account', 'Employee', 'Security', 'Available units', 'Cash']} rows={data.accounts.map((x: any) => [x.account_id, x.employee_id, x.security_id, Number(x.available_units).toLocaleString(), 'JPY ' + Number(x.cash_jpy).toLocaleString()])}/></>}
    {tab === 'Position detail' && <Panel title={'Position - ' + employee} columns={['Account', 'Instrument', 'Opening source', 'Available units', 'Pending transfer units', 'Cash']} rows={account ? [[account.account_id, account.instrument, account.opening_source_reference, account.available_units, account.pending_transfer_units, 'JPY ' + Number(account.cash_jpy).toLocaleString()]] : []}/>}
    {['Dividend processing', 'Action register'].includes(tab) && <div className="operations-review"><label>Review note<input value={reason} onChange={e => setReason(e.target.value)} minLength={3} maxLength={200}/></label></div>}
    {tab === 'Dividend processing' && <Panel title="Dividend entitlements" columns={['Dividend', 'Account', 'Record date', 'Payment date', 'Entitlement units', 'Amount', 'State', 'Review']} rows={data.dividends.map((x: any) => [x.id, x.account_id, x.record_date, x.payment_date, x.entitlement_units, 'JPY ' + Number(x.amount_jpy).toLocaleString(), x.state, x.state === 'SCHEDULED' ? <button disabled={Boolean(busy) || reason.trim().length < 3 || x.payment_date > data.as_of} onClick={() => advance('dividends', x.id, 'PAID')}>{busy === x.id ? 'Saving...' : 'Mark paid'}</button> : 'Recorded'])}/>}
    {tab === 'Action register' && <Panel title="Corporate actions" columns={['Action', 'Account', 'Type', 'Eligible units', 'Added units', 'State', 'Review']} rows={data.actions.map((x: any) => [x.id, x.account_id, label(x.action_type), x.eligible_units || 'Pending', x.added_units || 'Pending', label(x.state), actionNext[x.state] ? <button disabled={Boolean(busy) || reason.trim().length < 3} onClick={() => advance('actions', x.id, actionNext[x.state])}>{busy === x.id ? 'Saving...' : 'Advance to ' + label(actionNext[x.state])}</button> : 'Complete'])}/>}
    {tab === 'Settlement monitor' && <Panel title="Transfer settlement" columns={['Request', 'Employee', 'Units', 'State', 'Settlement', 'Correlation']} rows={data.transfers.map((x: any) => [x.id, x.employee_id, x.units, label(x.state), x.settlement_state, x.correlation_id])}/>}
  </>
}
