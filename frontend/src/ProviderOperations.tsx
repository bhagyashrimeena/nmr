import { useEffect, useState } from 'react'
import ReportSources from './ReportSources'

type Props = { page: 'work' | 'reports'; tenant: string; employee: string;
  request: (path: string, options?: RequestInit) => Promise<any>; onOpenStock: () => void }
const services = ['stock', 'pension', 'wellness', 'custody', 'equity']
const serviceNames: Record<string, string> = { stock: 'Employee Stock Ownership', pension: 'Corporate Pension', wellness: 'Financial Wellness', custody: 'Trust & Custody', equity: 'Equity Compensation' }
const reportLabels: Record<string, string> = { event_count: 'Journal events', journal_amount_jpy: 'Journal amount · JPY', journal_quantity: 'Journal quantity', open_case_count: 'Open cases', award_count: 'Awards', published_content_count: 'Published resources' }

export default function ProviderOperations({ page, tenant, employee, request, onOpenStock }: Props) {
  const [queue, setQueue] = useState<any>(null)
  const [selected, setSelected] = useState<string>('')
  const [service, setService] = useState('stock')
  const [asOf, setAsOf] = useState('2026-11-26')
  const [report, setReport] = useState<any>(null)
  const [participant, setParticipant] = useState<any>(null)
  const [search, setSearch] = useState('')
  const [reason, setReason] = useState('')
  const [evidence, setEvidence] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const base = `/api/v2/admin/tenants/${tenant}`

  useEffect(() => {
    setQueue(null); setReport(null); setParticipant(null); setSelected(''); setError('')
    const path = page === 'work' ? `${base}/work-queue` : `${base}/reports/service/${service}?as_of=${asOf}`
    request(path).then(page === 'work' ? setQueue : setReport).catch(e => setError(e.message))
  }, [page, tenant])

  async function reviewCase(action: 'INVESTIGATE' | 'WAIVE') {
    setBusy(true); setError('')
    try {
      await request(`${base}/cases/${selected}`, { method: 'PATCH',
        body: JSON.stringify({ action, reason: reason.trim(), evidence_reference: action === 'WAIVE' ? evidence.trim() : null }) })
      setQueue(await request(`${base}/work-queue`)); setReason(''); setEvidence('')
    } catch (e) { setError((e as Error).message) } finally { setBusy(false) }
  }

  async function generateReport() {
    setBusy(true); setError(''); setParticipant(null)
    try { setReport(await request(`${base}/reports/service/${service}?as_of=${asOf}`)) }
    catch (e) { setError((e as Error).message) } finally { setBusy(false) }
  }

  async function openParticipantReport() {
    setBusy(true); setError('')
    try { setParticipant(await request(`${base}/reports/participants/${employee}?service=${service}&as_of=${asOf}`)) }
    catch (e) { setError((e as Error).message) } finally { setBusy(false) }
  }

  if (page === 'work') {
    const cases = queue?.cases || []
    const visible = cases.filter((row: any) => `${row.id} ${row.service} ${row.employee_id || ''} ${row.break_type} ${row.status}`.toLowerCase().includes(search.toLowerCase().trim()))
    const current = cases.find((row: any) => row.id === selected)
    return <>{error && <div className="error" role="alert">{error}</div>}{!queue && !error && <div className="loading">Loading operational cases…</div>}{queue && <><div className="metrics"><div className="metric"><span>Cases</span><strong>{cases.length}</strong></div><div className="metric"><span>Open or investigating</span><strong>{cases.filter((row: any) => ['OPEN', 'INVESTIGATING'].includes(row.status)).length}</strong></div><div className="metric"><span>Workflow tasks</span><strong>{queue.tasks.length}</strong></div></div><div className="inline-filter"><label>Search cases<input value={search} onChange={e => setSearch(e.target.value)} placeholder="Case, service, employee or state"/></label></div><section className="section"><div className="section-heading"><h2>Reconciliation work queue</h2><span>{visible.length} shown · as of {queue.as_of}</span></div><div className="table-wrap"><table><thead><tr>{['Case', 'Service', 'Employee', 'Issue', 'Owner', 'Status', 'Record'].map(label => <th key={label}>{label}</th>)}</tr></thead><tbody>{visible.map((row: any) => <tr key={row.id}><td>{row.id}</td><td>{row.service}</td><td>{row.employee_id || 'Plan'}</td><td>{row.break_type.replaceAll('_', ' ')}</td><td>{row.owner}</td><td>{row.status}</td><td><button type="button" onClick={() => setSelected(row.id)}>Inspect</button></td></tr>)}</tbody></table></div>{!visible.length && <p className="empty">No cases match this search.</p>}</section>{current && <section className="section"><div className="section-heading"><h2>Case {current.id}</h2><span>{current.status}</span></div><div className="detail-grid"><div><span>Source</span><strong>{current.source_reference}</strong></div><div><span>Expected</span><strong>{current.expected_jpy == null ? 'Not monetary' : `JPY ${current.expected_jpy}`}</strong></div><div><span>Actual</span><strong>{current.actual_jpy == null ? 'Not monetary' : `JPY ${current.actual_jpy}`}</strong></div><div><span>Owner</span><strong>{current.owner}</strong></div><div><span>Resolution evidence</span><strong>{current.resolution?.evidence_reference || 'Pending'}</strong></div><div><span>Task</span><strong>{current.task_id || 'Pending assignment'}</strong></div></div>{current.resolution_note && <p className="panel-note">{current.resolution_note}</p>}<div className="table-wrap"><table><thead><tr><th>Transition</th><th>Actor</th><th>Reason</th><th>Time</th></tr></thead><tbody>{current.history.map((item: any, index: number) => <tr key={index}><td>{item.from_state || '—'} → {item.to_state}</td><td>{item.actor}</td><td>{item.reason}</td><td>{item.occurred_at?.slice(0, 19)}</td></tr>)}</tbody></table></div>{['OPEN', 'INVESTIGATING'].includes(current.status) && <div className="operations-review"><label>Review note<input value={reason} onChange={e => setReason(e.target.value)} minLength={8} maxLength={200}/></label><label>Waiver evidence reference<input value={evidence} onChange={e => setEvidence(e.target.value)} minLength={8} maxLength={80} placeholder="Required for waiver"/></label>{current.status === 'OPEN' && <button disabled={busy || reason.trim().length < 8} onClick={() => reviewCase('INVESTIGATE')}>Start investigation</button>}<button disabled={busy || reason.trim().length < 8 || evidence.trim().length < 8} onClick={() => reviewCase('WAIVE')}>Waive with evidence</button>{current.service === 'stock' && current.break_type === 'UNMATCHED_PAYROLL' && <button type="button" onClick={onOpenStock}>Open stock correction</button>}</div>}</section>}</>}</>
  }

  return <>{error && <div className="error" role="alert">{error}</div>}<div className="operations-review"><label>Service<select value={service} onChange={e => { setService(e.target.value); setReport(null); setParticipant(null) }}>{services.map(item => <option key={item} value={item}>{serviceNames[item]}</option>)}</select></label><label>Record date<input type="date" value={asOf} max="2026-11-26" onChange={e => { setAsOf(e.target.value); setReport(null); setParticipant(null) }}/></label><button type="button" disabled={busy} onClick={generateReport}>{busy ? 'Loading…' : 'Generate service report'}</button><button type="button" disabled={busy || !employee} onClick={openParticipantReport}>Trace selected participant</button></div>{report && <><div className="operations-heading"><span>{serviceNames[report.service]} · report version {report.report_version}</span><span>As of {report.as_of}</span></div><div className="metrics">{Object.entries(report.totals).map(([key, value]) => <div className="metric" key={key}><span>{reportLabels[key] || key.replaceAll('_', ' ')}</span><strong>{String(value)}</strong></div>)}</div><ReportSources tenant={tenant} service={report.service} asOf={report.as_of} request={request}/></>}{participant && <section className="section"><div className="section-heading"><h2>{participant.employee_id} · {serviceNames[participant.service]} ledger</h2><span>{participant.events.length} events · {participant.statement_references.length} statements</span></div><div className="detail-grid"><div><span>Journal amount</span><strong>JPY {participant.journal_amount_jpy}</strong></div><div><span>Journal quantity</span><strong>{participant.journal_quantity}</strong></div><div><span>Record date</span><strong>{participant.as_of}</strong></div></div><div className="table-wrap"><table><thead><tr>{['Effective', 'Event', 'Amount JPY', 'Quantity', 'Source', 'Correlation'].map(label => <th key={label}>{label}</th>)}</tr></thead><tbody>{participant.events.map((row: any) => <tr key={row.id}><td>{row.effective_at?.slice(0, 10)}</td><td>{row.type}</td><td>{row.amount_jpy}</td><td>{row.quantity}</td><td>{row.source_reference}</td><td>{row.correlation_id || '—'}</td></tr>)}</tbody></table></div></section>}</>
}
