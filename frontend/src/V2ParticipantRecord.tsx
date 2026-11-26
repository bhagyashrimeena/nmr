import { useEffect, useState } from 'react'

type Service = 'stock' | 'pension' | 'custody' | 'equity'
type SourceRow = {
  id: string
  type: string
  effective_at: string
  source_reference: string
  correlation_id?: string | null
  amount_jpy: string
  quantity: string
}
type SourceRecord = {
  source_version: string
  as_of: string
  employee_name: string
  available: boolean
  summary: any
  journal: SourceRow[]
  details: any
}

type Props = {
  page: Service
  tab: string
  tenant: string
  employee: string
  request: (path: string, options?: RequestInit) => Promise<any>
  refreshKey?: unknown
}

const currency = (value: unknown) => value == null ? '—' :
  '¥' + Number(value).toLocaleString('en-US', {minimumFractionDigits: 0, maximumFractionDigits: 2})
const quantity = (value: unknown) => value == null ? '—' : Number(value).toLocaleString('en-US', {maximumFractionDigits: 6})
const day = (value: unknown) => value == null ? '—' : String(value).slice(0, 10)

function RecordsTable({columns,rows}: {columns: string[];rows: string[][]}) {
  if (!rows.length) return <p className="empty">No applicable events recorded for this employee.</p>
  return <div className="table-wrap"><table><thead><tr>{columns.map(x => <th key={x}>{x}</th>)}</tr></thead>
    <tbody>{rows.map((row, i) => <tr key={i}>{row.map((cell,j) => <td key={j}>{cell}</td>)}</tr>)}</tbody></table></div>
}
function Indicator({label,value}: {label:string;value:string}) {
  return <div className="metric"><span>{label}</span><strong>{value}</strong></div>
}

export default function V2ParticipantRecord({page, tab, tenant, employee, request, refreshKey}: Props) {
  const [record,setRecord] = useState<SourceRecord | null>(null)
  const [error,setError] = useState('')
  const [loading,setLoading] = useState(true)
  const [tick,setTick] = useState(0)
  const [pensionYears,setPensionYears] = useState(20)
  const [pensionMonthly,setPensionMonthly] = useState(35000)
  const [pensionReturn,setPensionReturn] = useState(4)
  const [forecast,setForecast] = useState<any>(null)
  const [forecastError,setForecastError] = useState('')
  const [forecastBusy,setForecastBusy] = useState(false)

  useEffect(() => {
    let cancelled = false
    setLoading(true); setError(''); setRecord(null)
    request('/api/v2/admin/tenants/' + encodeURIComponent(tenant) + '/employees/' +
      encodeURIComponent(employee) + '/source-record/' + page)
      .then(data => {if (!cancelled) setRecord(data)})
      .catch(e => {if (!cancelled) setError((e as Error).message)})
      .finally(() => {if (!cancelled) setLoading(false)})
    return () => {cancelled = true}
  }, [page, tenant, employee, request, refreshKey, tick])

  async function calculatePensionProjection() {
    setForecastBusy(true); setForecastError(''); setForecast(null)
    try {
      const params = new URLSearchParams({
        years: String(pensionYears), monthly_jpy: String(pensionMonthly),
        annual_return_pct: String(pensionReturn),
      })
      setForecast(await request('/api/v2/admin/tenants/' + encodeURIComponent(tenant) +
        '/employees/' + encodeURIComponent(employee) + '/pension/retirement-projection?' + params))
    } catch (e) { setForecastError((e as Error).message) } finally { setForecastBusy(false) }
  }

  if (loading) return <div className="loading">Loading reconciled V2 financial records…</div>
  if (error) return <div className="error" role="alert">{error}</div>
  if (!record || !record.available) return <p className="empty">No V2 {page} financial record is available for this participant.</p>

  const s = record.summary || {}
  const events = record.journal || []
  const journalRows = (subset: SourceRow[]) => subset.map(e => [
    day(e.effective_at), e.type.replaceAll('_',' '), currency(e.amount_jpy),
    quantity(e.quantity), e.source_reference || e.id,
  ])
  const journalTable = (subset: SourceRow[], title: string) => (
    <section className="section"><div className="section-heading"><h2>{title}</h2><span>{subset.length} dated source events</span></div>
      <RecordsTable columns={['Effective date','Event','Cash movement','Units','Source reference']} rows={journalRows(subset)}/>
    </section>
  )

  return <div className={"v2-record v2-record--" + page}>
    <div className="v2-source-bar">
      <div className="v2-source-ident">
        <span className="v2-source-eyebrow">Financial source record</span>
        <strong>Account activity & reconciliation</strong>
        <span>{record.employee_name} · V2 journal · Record date {day(record.as_of)}</span>
      </div>
      <button className="v2-source-refresh" type="button" onClick={() => setTick(x => x + 1)}>Refresh records</button>
    </div>
    {page === 'stock' && <>
      {tab === 'Overview' && <>
        <div className="metrics v2-stock-metrics">
          <Indicator label="Beneficial shares held" value={quantity(s.shares_held)}/>
          <Indicator label="Uninvested association cash" value={currency(s.uninvested_cash_jpy)}/>
          <Indicator label="Posted employee cash" value={currency(s.posted_employee_cash_jpy)}/>
          <Indicator label="Employer incentives" value={currency(s.posted_incentive_cash_jpy)}/>
        </div>
        <section className="section"><div className="section-heading"><h2>Participation and reconciliation</h2><span>{s.reconciled ? 'Reconciled' : 'Review required'}</span></div>
          <div className="detail-grid">
            <div><span>Plan</span><strong>{s.plan?.name}</strong></div>
            <div><span>Membership</span><strong>{s.membership?.status}</strong></div>
            <div><span>Transferable whole units</span><strong>{quantity(s.available_transfer_units)}</strong></div>
            <div><span>Settled purchase cost</span><strong>{currency(s.settled_purchase_cost_jpy)}</strong></div>
            <div><span>Rule source</span><strong>{s.plan?.rule_source_reference}</strong></div>
            <div><span>Ownership basis</span><strong>Shareholding association interest</strong></div>
          </div>
        </section>
      </>}
      {tab === 'Contributions' && journalTable(events.filter(e => e.type.includes('PAYROLL') || e.type.includes('INCENTIVE')), 'Posted contribution and incentive history')}
      {tab === 'Purchases' && journalTable(events.filter(e => e.type.includes('PURCHASE') || e.type.includes('ALLOCATION')), 'Settled purchase allocations')}
      {tab === 'Activity' && journalTable(events, 'Complete shareholding activity journal')}
      {tab === 'Statements' && journalTable(events, 'Dated financial statement source records')}
    </>}
    {page === 'pension' && <>
      {tab === 'Overview' && <div className="metrics">
        <Indicator label="Current fund valuation" value={currency(s.balance_jpy)}/>
        <Indicator label="Fund positions" value={String(s.positions?.length || 0)}/>
        <Indicator label="Financial reconciliation" value={s.reconciled ? 'Reconciled' : 'Review required'}/>
      </div>}
      {['Overview','Valuations','Statements'].includes(tab) && <section className="section"><div className="section-heading"><h2>Investment positions at dated NAV</h2><span>{day(record.as_of)} · not live pricing</span></div>
        <RecordsTable columns={['Fund','Units','NAV','NAV date','Valuation','Annual fee']} rows={(s.positions || []).map((p: any) =>
          [p.fund_name,quantity(p.units),currency(p.nav_jpy),day(p.nav_date),currency(p.value_jpy),String(p.annual_fee_percent) + '%']
        )}/>
      </section>}
      {tab === 'Contributions' && journalTable(events.filter(e => e.type.includes('CONTRIBUTION') || e.type.includes('EMPLOYER')), 'Pension contribution and remittance events')}
      {tab === 'Statements' && journalTable(events, 'Pension valuation and cash-flow source journal')}
      {tab === 'Projection' && <section className="section">
        <div className="section-heading"><h2>Retirement projection</h2><span>Uses reconciled V2 current holdings</span></div>
        <p className="panel-note">Starting balance: {currency(s.balance_jpy)} · Dated financial snapshot {day(record.as_of)}. Constant hypothetical returns are not guaranteed.</p>
        <div className="workflow-form">
          <label>Additional monthly contribution (JPY)
            <input type="number" min="0" max="1000000" step="1" value={pensionMonthly} onChange={e => setPensionMonthly(Number(e.target.value))} />
          </label>
          <label>Projection period (years)
            <input type="number" min="1" max="40" step="1" value={pensionYears} onChange={e => setPensionYears(Number(e.target.value))}/>
          </label>
          <label>Assumed annual return (%)
            <input type="number" min="0" max="12" step="0.1" value={pensionReturn} onChange={e => setPensionReturn(Number(e.target.value))}/>
          </label>
          <button type="button" className="primary" onClick={calculatePensionProjection} disabled={forecastBusy}>{forecastBusy ? 'Calculating…' : 'Calculate projection'}</button>
        </div>
        {forecastError && <div className="error" role="alert">{forecastError}</div>}
        {forecast && <div className="metrics">
          <Indicator label="Current account" value={currency(forecast.projection.starting_balance_jpy)}/>
          <Indicator label="Current + future contributions" value={currency(forecast.projection.total_contributed_jpy)}/>
          <Indicator label="Illustrative future value" value={currency(forecast.projection.illustrative_future_value_jpy)}/>
        </div>}
        {forecast && <p className="panel-note">{forecast.projection.disclaimer} Formula: {forecast.assumptions.formula_id}.</p>}
      </section>}
    </>}
    {page === 'custody' && <>
      {tab === 'Overview' && <div className="metrics">
        <Indicator label="Custody securities held" value={quantity(s.available_units)}/>
        <Indicator label="Credited custody cash" value={currency(s.cash_jpy)}/>
        <Indicator label="Pending transfer units" value={quantity(s.pending_transfer_units)}/>
      </div>}
      {['Overview','Valuations','Statements'].includes(tab) && <section className="section"><div className="section-heading"><h2>Custody record</h2><span>Individual securities account only</span></div>
        <div className="detail-grid"><div><span>Account</span><strong>{s.account_id}</strong></div><div><span>Instrument</span><strong>{s.instrument}</strong></div>
          <div><span>Security reference</span><strong>{s.security_id}</strong></div><div><span>Ownership basis</span><strong>{s.ownership_basis}</strong></div></div>
      </section>}
      {tab === 'Dividends' && <section className="section"><h2>Dividend entitlements and payments</h2>
        <RecordsTable columns={['Reference','Record date','Payment date','Amount','State']} rows={(record.details?.dividends || []).map((d: any) =>
          [d.id,day(d.record_date),day(d.payment_date),currency(d.amount_jpy),d.state])}/></section>}
      {tab === 'Corporate actions' && <section className="section"><h2>Corporate-action processing</h2>
        <RecordsTable columns={['Event','Record date','Effective date','Added units','State']} rows={(record.details?.actions || []).map((a: any) =>
          [a.id,day(a.record_date),day(a.effective_date),quantity(a.added_units),a.state])}/></section>}
      {['Settlements','Statements'].includes(tab) && journalTable(events, 'Confirmed custody settlement and position history')}
    </>}
    {page === 'equity' && <>
      {tab === 'Awards' && <>
        <div className="metrics">
          <Indicator label="Total grants" value={String(s.grant_count)}/>
          <Indicator label="Granted units" value={quantity(s.granted_units)}/>
          <Indicator label="Grant reconciliation" value={s.reconciled ? 'Reconciled' : 'Review required'}/>
        </div>
        <section className="section"><div className="section-heading"><h2>Issued and proposed awards</h2><span>All states clearly distinguished</span></div>
          <RecordsTable columns={['Grant','Type','State','Granted','Vested unreleased','Released / exercised','Forfeited']} rows={(record.details || []).map((a: any) =>
            [a.id,a.award_type,a.state,quantity(a.granted_units),quantity(a.vested_unreleased_units),
              quantity(a.award_type === 'Option' ? a.exercised_units : a.released_units),quantity(a.forfeited_units)])}/>
        </section>
      </>}
      {tab === 'Vesting' && <section className="section"><h2>Vesting tranches</h2>
        <RecordsTable columns={['Grant','Vesting date','Scheduled units','Status','Source']} rows={(record.details || []).flatMap((a: any) =>
          a.tranches.map((t: any) => [a.id,day(t.vest_date),quantity(t.units),t.state,t.id]))}/></section>}
      {tab === 'Statements' && <section className="section"><h2>Equity award source register</h2>
        <RecordsTable columns={['Grant','Grant date','Type','Granted','Released','Forfeited','State']} rows={(record.details || []).map((a: any) =>
          [a.id,day(a.grant_date),a.award_type,quantity(a.granted_units),quantity(a.released_units),quantity(a.forfeited_units),a.state])}/>
        <p className="panel-note">These are auditable award records, not an executed trade or a broker statement.</p>
      </section>}
    </>}
    <p className="panel-note">Source register: V2 operations · Record date {day(record.as_of)} · Financial values are not live market prices.</p>
  </div>
}
