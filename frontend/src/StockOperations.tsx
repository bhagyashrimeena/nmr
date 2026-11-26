import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'

type Props = {
  tab: string
  tenant: string
  request: (path: string, options?: RequestInit) => Promise<any>
  onRefresh: () => Promise<void>
}

const nextState: Record<string, string> = {
  REQUESTED: 'ELIGIBILITY_CHECKED',
  ELIGIBILITY_CHECKED: 'CORPORATE_APPROVED',
  CORPORATE_APPROVED: 'PROVIDER_FORWARDED',
  PROVIDER_FORWARDED: 'COMPLETED',
}
const amount = (value: string | number) => 'JPY ' + Number(value).toLocaleString()

function Table({ columns, rows }: { columns: string[]; rows: ReactNode[][] }) {
  if (!rows.length) return <p className="empty">No records match this view.</p>
  return <div className="table-wrap"><table><thead><tr>{columns.map(name => <th key={name}>{name}</th>)}</tr></thead><tbody>{rows.map((row, index) => <tr key={index}>{row.map((cell, cellIndex) => <td key={cellIndex}>{cell}</td>)}</tr>)}</tbody></table></div>
}

function Panel({ title, note, columns, rows }: { title: string; note: string; columns: string[]; rows: ReactNode[][] }) {
  return <section className="section"><div className="section-heading"><h2>{title}</h2><span>{note}</span></div><Table columns={columns} rows={rows}/></section>
}

export default function StockOperations({ tab, tenant, request, onRefresh }: Props) {
  const [data, setData] = useState<any>(null)
  const [search, setSearch] = useState('')
  const [reason, setReason] = useState('Reviewed by plan operations')
  const [confirmationRef, setConfirmationRef] = useState('')
  const [selectedBatch, setSelectedBatch] = useState<any>(null)
  const [correctionCase, setCorrectionCase] = useState('')
  const [correctionEvidence, setCorrectionEvidence] = useState('')
  const [correctionReason, setCorrectionReason] = useState('Payroll remittance verified against the participant election')
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    setData(null); setError(''); setSearch('')
    request('/api/v2/admin/tenants/' + tenant + '/shareholding/operations').then(setData).catch(e => setError(e.message))
  }, [tenant, request])

  async function advance(requestId: string, state: string) {
    setBusy(requestId); setError('')
    try {
      await request('/api/v2/admin/tenants/' + tenant + '/shareholding/transfers/' + requestId,
        { method: 'PATCH', body: JSON.stringify({ state, reason, confirmation_reference: state === 'COMPLETED' ? confirmationRef : null }) })
      setData(await request('/api/v2/admin/tenants/' + tenant + '/shareholding/operations'))
      await onRefresh()
    } catch (e) { setError((e as Error).message) } finally { setBusy('') }
  }

  async function inspectBatch(batchId: string) {
    setBusy(batchId); setError('')
    try { setSelectedBatch(await request('/api/v2/admin/tenants/' + tenant + '/shareholding/payroll-batches/' + batchId)) }
    catch (e) { setError((e as Error).message) } finally { setBusy('') }
  }

  async function correctPayroll(caseId: string) {
    setBusy(caseId); setError('')
    try {
      await request('/api/v2/admin/tenants/' + tenant + '/shareholding/cases/' + caseId + '/correct-payroll',
        { method: 'POST', body: JSON.stringify({ evidence_reference: correctionEvidence.trim(), reason: correctionReason.trim() }) })
      setData(await request('/api/v2/admin/tenants/' + tenant + '/shareholding/operations'))
      await onRefresh()
      setCorrectionCase(''); setCorrectionEvidence('')
    } catch (e) { setError((e as Error).message) } finally { setBusy('') }
  }

  if (error && !data) return <div className="error" role="alert">{error}</div>
  if (!data) return <div className="loading">Loading shareholding operations...</div>
  const query = search.toLowerCase().trim()
  const filtered = (rows: any[]) => rows.filter(row => JSON.stringify(row).toLowerCase().includes(query))

  return <>
    <div className="operations-heading"><span>Plan: {data.plan.id}</span><span>As of {data.as_of}</span></div>
    {error && <div className="error" role="alert">{error}</div>}
    {tab === 'Plan operations' && <>
      <div className="metrics">
        <div className="metric"><span>Members</span><strong>{data.members.length}</strong></div>
        <div className="metric"><span>Payroll batches</span><strong>{data.payroll_batches.length}</strong></div>
        <div className="metric"><span>Open exceptions</span><strong>{data.exceptions.filter((row: any) => row.status === 'OPEN').length}</strong></div>
      </div>
      <section className="section"><div className="section-heading"><h2>Shareholding plan</h2><span>{data.plan.status}</span></div><div className="detail-grid">
        <div><span>Plan</span><strong>{data.plan.name}</strong></div>
        <div><span>Issuer</span><strong>{data.plan.issuer}</strong></div>
        <div><span>Next purchase date</span><strong>{data.plan.next_purchase_date}</strong></div>
        <div><span>Monthly contribution range</span><strong>{amount(data.plan.minimum_monthly_jpy)} - {amount(data.plan.maximum_monthly_jpy)}</strong></div>
        <div><span>Employer incentive</span><strong>{Number(data.plan.incentive_percent)}%</strong></div>
        <div><span>Rule reference</span><strong>{data.plan.rule_source_reference}</strong></div>
        <div><span>Rule effective</span><strong>{data.plan.rule_effective_on}</strong></div>
        <div><span>Beneficial units</span><strong>{data.plan.fractional_beneficial_units ? 'Fractional permitted' : 'Whole units'}</strong></div>
        <div><span>External access</span><strong>Managed in MCP Access Management</strong></div>
      </div></section>
    </>}
    {['Members', 'Payroll batches', 'Purchase cycles', 'Exceptions'].includes(tab) && <div className="inline-filter"><label>Search records<input value={search} onChange={e => setSearch(e.target.value)} placeholder="Reference, employee or status"/></label></div>}
    {tab === 'Members' && <Panel title="Member directory" note={filtered(data.members).length + ' shown'} columns={['Employee', 'Name', 'Joined', 'Status', 'Share units', 'Plan cash']} rows={filtered(data.members).map((row: any) => [row.employee_id, row.display_name, row.joined_on, row.status, Number(row.shares_held).toLocaleString(), amount(row.cash_jpy)])}/>}
    {tab === 'Payroll batches' && <><Panel title="Payroll collection" note={filtered(data.payroll_batches).length + ' shown'} columns={['Reference', 'Period', 'Expected', 'Received', 'Rejected lines', 'State']} rows={filtered(data.payroll_batches).map((row: any) => [<button type="button" onClick={() => inspectBatch(row.id)} disabled={Boolean(busy)}>{row.source_reference}</button>, row.period, amount(row.expected_jpy), amount(row.received_jpy), row.failed_lines, row.state])}/>{selectedBatch && <section className="section"><div className="section-heading"><h2>Batch {selectedBatch.id}</h2><span>{selectedBatch.state} · {selectedBatch.rule_source_reference || 'Earlier plan rule'}</span></div><div className="detail-grid"><div><span>Expected</span><strong>{amount(selectedBatch.expected_jpy)}</strong></div><div><span>Received</span><strong>{amount(selectedBatch.received_jpy)}</strong></div><div><span>Period</span><strong>{selectedBatch.period}</strong></div><div><span>Source reference</span><strong>{selectedBatch.source_reference}</strong></div></div><Table columns={['Employee', 'Contribution', 'Incentive', 'State', 'Reason']} rows={selectedBatch.lines.map((line: any) => [line.employee_id, amount(line.amount_jpy), amount(line.incentive_jpy), line.state, line.rejection_reason || '—'])}/><p className="panel-note">{selectedBatch.events.length} posted journal events · {selectedBatch.case_ids.length} reconciliation cases</p></section>}</>}
    {tab === 'Purchase cycles' && <Panel title="Purchase and allocation cycles" note={filtered(data.purchase_cycles).length + ' shown'} columns={['Reference', 'Trade date', 'Settlement', 'Unit price', 'Units', 'State']} rows={filtered(data.purchase_cycles).map((row: any) => [row.id, row.trade_date, row.settlement_date || 'Pending', amount(row.unit_price_jpy), Number(row.acquired_units).toLocaleString(), row.state])}/>}
    {tab === 'Transfer requests' && <><div className="operations-review"><label>Review note<input value={reason} onChange={e => setReason(e.target.value)} minLength={3} maxLength={200}/></label><label>Settlement confirmation<input value={confirmationRef} onChange={e => setConfirmationRef(e.target.value)} placeholder="Required to complete transfer" minLength={8} maxLength={80}/></label></div><Panel title="Transfer request queue" note={data.transfers.length + ' requests'} columns={['Request', 'Employee', 'Units', 'Recipient account', 'State', 'Review']} rows={data.transfers.map((row: any) => [row.request_id, row.employee_id, Number(row.units).toLocaleString(), row.recipient_account_reference, row.state, nextState[row.state] ? <button type="button" disabled={Boolean(busy) || reason.trim().length < 3 || (nextState[row.state] === 'COMPLETED' && confirmationRef.trim().length < 8)} onClick={() => advance(row.request_id, nextState[row.state])}>{busy === row.request_id ? 'Saving...' : 'Advance to ' + nextState[row.state].replaceAll('_', ' ')}</button> : 'Complete'])}/></>}
    {tab === 'Exceptions' && <><Panel title="Reconciliation cases" note={filtered(data.exceptions).length + ' shown'} columns={['Case', 'Employee', 'Source', 'Break type', 'Expected', 'Actual', 'Status', 'Action']} rows={filtered(data.exceptions).map((row: any) => [row.id, row.employee_id || 'Plan', row.source_reference, row.break_type.replaceAll('_', ' '), amount(row.expected_jpy), amount(row.actual_jpy), row.status, row.status === 'OPEN' && row.break_type === 'UNMATCHED_PAYROLL' ? <button type="button" onClick={() => { setCorrectionCase(row.id); const batch = data.payroll_batches.find((item: any) => item.source_reference === row.source_reference); if (batch) inspectBatch(batch.id) }}>Investigate</button> : row.resolution_evidence || row.owner])}/>{correctionCase && <section className="section"><div className="section-heading"><h2>Correct {correctionCase}</h2><span>Original rejected batch remains on record</span></div><div className="operations-review"><label>Remittance evidence reference<input value={correctionEvidence} onChange={e => setCorrectionEvidence(e.target.value)} minLength={8} maxLength={80} placeholder="Verified payroll reference"/></label><label>Resolution note<input value={correctionReason} onChange={e => setCorrectionReason(e.target.value)} minLength={8} maxLength={200}/></label><button type="button" disabled={Boolean(busy) || correctionEvidence.trim().length < 8 || correctionReason.trim().length < 8} onClick={() => correctPayroll(correctionCase)}>{busy === correctionCase ? 'Posting…' : 'Post corrected cash'}</button></div><p className="panel-note">A correction posts payroll cash and the rule-based incentive. It does not create shares.</p></section>}</>}
  </>
}
