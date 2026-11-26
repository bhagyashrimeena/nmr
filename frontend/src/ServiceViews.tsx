import { useEffect, useState } from 'react'

export type ServiceKey = 'stock' | 'pension' | 'wellness' | 'custody' | 'equity'
type Request = (path: string, options?: RequestInit) => Promise<any>
type Props = { page: ServiceKey; summary: any; tenant: string; employee: string; request: Request; onRefresh: () => Promise<void> }

const money = (value: number | null | undefined) => value == null ? '—' : `¥${value.toLocaleString('en-US')}`
const day = (value: string | null | undefined) => value ? value.slice(0, 10) : '—'

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
  stock: ['Overview', 'Contributions', 'Purchases', 'Activity', 'Statements'],
  pension: ['Overview', 'Contributions', 'Valuations', 'Projection', 'Statements'],
  wellness: ['Resources', 'Progress', 'Savings calculator'],
  custody: ['Overview', 'Valuations', 'Dividends', 'Corporate actions', 'Settlements', 'Statements'],
  equity: ['Awards', 'Vesting', 'Statements'],
}

export default function ServiceViews({ page, summary, tenant, employee, request, onRefresh }: Props) {
  const [tab, setTab] = useState('')
  const [year, setYear] = useState('all')
  const [topic, setTopic] = useState('all')
  const [search, setSearch] = useState('')
  const [wellnessResults, setWellnessResults] = useState<any>(null)
  const [statusFilter, setStatusFilter] = useState('all')
  const [awardFilter, setAwardFilter] = useState('all')
  const [monthly, setMonthly] = useState(15000)
  const [years, setYears] = useState(10)
  const [rate, setRate] = useState(0)
  const [projection, setProjection] = useState<any>(null)
  const [working, setWorking] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => { setTab(tabs[page][0]); setYear('all'); setTopic('all'); setSearch(''); setWellnessResults(null); setProjection(null); setError('') }, [page, employee])
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
  if (!data) return <div className="empty service-empty">No {page} account is recorded for this employee. Other available services remain visible in their own tabs.</div>
  const yearsAvailable = page === 'stock' ? [...new Set(data.purchases.map((p: any) => String(p.purchase_date).slice(0, 4)))] as string[] : []
  return <>
    <div className="subtabs" role="tablist" aria-label={`${page} views`}>{tabs[page].map(name => <button type="button" role="tab" aria-selected={active === name} className={active === name ? 'selected' : ''} key={name} onClick={() => { setTab(name); setProjection(null); setError('') }}>{name}</button>)}</div>
    {error && <div className="error" role="alert">{error}</div>}

    {page === 'stock' && active === 'Overview' && <><Metrics entries={[
      { label: 'Shares held', value: `${data.shares_held} shares`, detail: data.plan_id },
      { label: 'Illustrative value', value: money(data.illustrative_portfolio_value_jpy), detail: `Price ${money(Number(data.illustrative_share_price_jpy))}` },
      { label: '2026 employee contributions', value: money(data.year_to_date_contributions_jpy) },
      { label: 'Employer incentives', value: money(data.employer_incentives_jpy) },
    ]}/><Panel title="Plan and participation"><div className="detail-grid"><div><span>Plan</span><strong>{data.plan_name}</strong></div><div><span>Enrolled</span><strong>{day(data.enrollment_date)}</strong></div><div><span>Status</span><strong>{data.participation_status}</strong></div><div><span>Average purchase cost</span><strong>{money(Number(data.average_purchase_cost_jpy))}</strong></div><div><span>Uninvested plan cash</span><strong>{money(data.uninvested_cash_jpy)}</strong></div><div><span>Dividends received</span><strong>{money(data.dividends_received_jpy)}</strong></div></div></Panel><Panel title="Latest purchases" note="Payroll purchases are distinct from employer equity awards."><Table columns={['Date', 'Shares', 'Price per share', 'Cost', 'Status']} rows={data.recent_purchases.map((p: any) => [day(p.purchase_date), p.shares, money(p.price_jpy), money(p.amount_jpy), p.status])}/></Panel><p className="disclaimer">{data.note}</p></>}
    {page === 'stock' && active === 'Contributions' && <><Metrics entries={[{ label: 'Employee total', value: money(data.total_contributions_jpy) }, { label: 'Employer incentive total', value: money(data.employer_incentives_jpy) }, { label: 'Current monthly deduction', value: money(data.monthly_contribution_jpy) }]}/><Panel title="Payroll contribution history"><Table columns={['Payroll month', 'Employee deduction', 'Employer incentive', 'Combined']} rows={data.contributions.map((c: any) => [day(c.month).slice(0, 7), money(c.amount_jpy), money(c.employer_incentive_jpy), money(c.amount_jpy + c.employer_incentive_jpy)])}/></Panel></>}
    {page === 'stock' && active === 'Purchases' && <><div className="inline-filter"><label>Purchase year<select value={year} onChange={e => setYear(e.target.value)}><option value="all">All years</option>{yearsAvailable.map(y => <option key={y}>{y}</option>)}</select></label></div><Metrics entries={[{ label: 'Shares acquired this quarter', value: `${data.current_quarter_purchased_shares}` }, { label: 'All recorded shares', value: `${data.shares_held}` }, { label: 'Illustrative unrealized change', value: money(data.illustrative_unrealized_change_jpy) }]}/><Panel title="Share purchase ledger"><Table columns={['Reference', 'Date', 'Units', 'Unit price', 'Amount', 'Status']} rows={data.purchases.filter((p: any) => year === 'all' || p.purchase_date.startsWith(year)).map((p: any) => [p.reference, day(p.purchase_date), p.shares, money(p.price_jpy), money(p.amount_jpy), p.status])}/></Panel></>}
    {page === 'stock' && active === 'Activity' && <Panel title="Share plan activity"><Table columns={['Date', 'Type', 'Amount', 'Shares']} rows={data.activity.map((a: any) => [day(a.date), a.type.replaceAll('_', ' '), money(a.amount_jpy), a.shares || '—'])}/></Panel>}
    {page === 'stock' && active === 'Statements' && <Panel title="Annual share plan statements"><Table columns={['Year', 'Employee contributions', 'Employer incentives', 'Shares bought', 'Purchase cost']} rows={data.statements.map((s: any) => [s.period, money(s.employee_contributions_jpy), money(s.employer_incentives_jpy), s.shares_purchased, money(s.purchase_cost_jpy)])}/></Panel>}

    {page === 'pension' && active === 'Overview' && <><Metrics entries={[{ label: 'Current balance', value: money(data.balance_jpy), detail: data.account_type }, { label: 'Employer contributions, 2026', value: money(data.employer_contributions_ytd_jpy) }, { label: 'Equity allocation', value: `${data.equity_allocation_percent}%` }, { label: 'Illustrative NAV change', value: `${data.illustrative_nav_change_percent}%`, detail: 'Opening to latest snapshot' }]}/><Panel title="Investment allocation"><div className="allocation">{data.allocations.map((a: any) => <div key={a.asset_class}><span>{a.asset_class}</span><div className="bar"><i style={{ width: `${a.percentage}%` }}/></div><strong>{a.percentage}%</strong><small>{money(a.illustrative_value_jpy)}</small></div>)}</div></Panel><Panel title="Account reconciliation"><div className="detail-grid"><div><span>Opening balance</span><strong>{money(data.opening_balance_jpy)}</strong></div><div><span>Employee contributions</span><strong>{money(data.employee_contributions_jpy)}</strong></div><div><span>Employer contributions</span><strong>{money(data.employer_contributions_jpy)}</strong></div><div><span>Investment change</span><strong>{money(data.investment_change_jpy)}</strong></div></div></Panel><p className="disclaimer">{data.note}</p></>}
    {page === 'pension' && active === 'Contributions' && <Panel title="Pension contribution history"><Table columns={['Date', 'Employee', 'Employer', 'Total']} rows={data.contribution_history.map((c: any) => [day(c.date), money(c.employee_amount_jpy), money(c.employer_amount_jpy), money(c.employee_amount_jpy + c.employer_amount_jpy)])}/></Panel>}
    {page === 'pension' && active === 'Valuations' && <Panel title="Synthetic valuation history" note="NAV and balances are illustrative snapshots."><Table columns={['Valuation date', 'Account balance', 'Illustrative NAV']} rows={data.valuation_history.map((v: any) => [day(v.date), money(v.balance_jpy), v.illustrative_nav])}/></Panel>}
    {page === 'pension' && active === 'Statements' && <Panel title="Annual pension statements"><Table columns={['Year', 'Employee contributions', 'Employer contributions']} rows={data.statements.map((s: any) => [s.period, money(s.employee_contributions_jpy), money(s.employer_contributions_jpy)])}/></Panel>}
    {page === 'pension' && active === 'Projection' && <><div className="notice">This is a fixed-rate simulation. It is not a forecast or guaranteed retirement balance.</div><div className="calculator"><label>Monthly contribution (JPY)<input type="number" min="0" max="1000000" value={monthly} onChange={e => setMonthly(Number(e.target.value))}/></label><label>Years<input type="number" min="1" max="40" value={years} onChange={e => setYears(Number(e.target.value))}/></label><label>Annual return assumption (%)<input type="number" min="0" max="12" step="0.1" value={rate} onChange={e => setRate(Number(e.target.value))}/></label><button className="primary" disabled={working} onClick={() => calculate('pension')}>{working ? 'Calculating…' : 'Calculate'}</button></div>{projection && <Metrics entries={[{ label: 'Starting balance', value: money(projection.projection.starting_balance_jpy) }, { label: 'Total contributed', value: money(projection.projection.total_contributed_jpy) }, { label: 'Illustrative future value', value: money(projection.projection.illustrative_future_value_jpy) }]}/>}</>}

    {page === 'wellness' && active === 'Resources' && <><div className="notice">Educational material only. Suggested resources use a synthetic topic preference, not financial advice.</div><div className="inline-filter"><label>Topic<select value={topic} onChange={e => setTopic(e.target.value)}><option value="all">All topics</option>{data.topics.map((t: string) => <option key={t} value={t}>{t}</option>)}</select></label><label>Search<input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search resources" onKeyDown={e => { if (e.key === 'Enter') filterWellness() }}/></label><button onClick={filterWellness} disabled={working}>{working ? 'Searching…' : 'Apply filters'}</button><button onClick={() => { setTopic('all'); setSearch(''); setWellnessResults(null) }}>Clear</button></div><div className="resource-grid">{(wellnessResults || data).resources.map((r: any) => <article className="resource" key={r.id}><span className="eyebrow">{r.topic} · {r.progress.replace('_', ' ')}</span><h3>{r.title}</h3><p>{r.description}</p><div>{r.content}</div><button className="progress-button" disabled={working} onClick={() => markProgress(r.id, r.progress)}>{r.progress === 'completed' ? 'Reset progress' : 'Mark completed'}</button></article>)}</div>{!(wellnessResults || data).resources.length && <p className="empty">No resources match the current search.</p>}<Panel title="Recommended reading" note={`Preference: ${data.preferred_topic || 'none'}`}><Table columns={['Resource', 'Topic', 'Progress']} rows={data.recommended_resources.map((r: any) => [r.title, r.topic, r.progress.replace('_', ' ')])}/></Panel></>}
    {page === 'wellness' && active === 'Progress' && <><Metrics entries={[{ label: 'Completed resources', value: `${data.progress.completed}` }, { label: 'In progress', value: `${data.progress.in_progress}` }, { label: 'Catalog resources', value: `${data.resources.length}` }]}/><Panel title="Learning progress"><Table columns={['Resource', 'Topic', 'Status']} rows={data.resources.map((r: any) => [r.title, r.topic, r.progress.replace('_', ' ')])}/></Panel></>}
    {page === 'wellness' && active === 'Savings calculator' && <><div className="notice">A deterministic educational calculator using end-of-month contributions. No recommendation or guaranteed return.</div><div className="calculator"><label>Monthly amount (JPY)<input type="number" min="0" max="1000000" value={monthly} onChange={e => setMonthly(Number(e.target.value))}/></label><label>Years<input type="number" min="1" max="40" value={years} onChange={e => setYears(Number(e.target.value))}/></label><label>Annual return assumption (%)<input type="number" min="0" max="12" step="0.1" value={rate} onChange={e => setRate(Number(e.target.value))}/></label><button className="primary" disabled={working} onClick={() => calculate('wellness')}>{working ? 'Calculating…' : 'Calculate'}</button></div>{projection && <Metrics entries={[{ label: 'Total contributions', value: money(projection.projection.total_contributed_jpy) }, { label: 'Illustrative growth', value: money(projection.projection.illustrative_growth_jpy) }, { label: 'Illustrative future value', value: money(projection.projection.illustrative_future_value_jpy) }]}/>}</>}

    {page === 'custody' && active === 'Overview' && <><Metrics entries={[{ label: 'Illustrative custody value', value: money(data.illustrative_portfolio_value_jpy), detail: data.account_id }, { label: '2026 credited dividends', value: money(data.dividends_received_ytd_jpy) }, { label: 'Announced actions', value: `${data.pending_corporate_actions}` }]}/><Panel title="Held positions"><Table columns={['Security ID', 'Instrument', 'Asset class', 'Quantity', 'Illustrative value']} rows={data.positions.map((p: any) => [p.security_id, p.instrument, p.asset_class, p.quantity, money(p.illustrative_value_jpy)])}/></Panel><p className="disclaimer">{data.note}</p></>}
    {page === 'custody' && active === 'Valuations' && <Panel title="Historical custody valuations" note="Illustrative snapshots; no live market prices."><Table columns={['Valuation date', 'Portfolio value']} rows={data.valuation_history.map((v: any) => [day(v.date), money(v.illustrative_value_jpy)])}/></Panel>}
    {page === 'custody' && active === 'Dividends' && <Panel title="Dividend ledger"><Table columns={['Instrument', 'Record date', 'Payment date', 'Amount', 'Status']} rows={data.dividends.map((d: any) => [d.instrument, day(d.record_date), day(d.payment_date), money(d.amount_jpy), d.status])}/></Panel>}
    {page === 'custody' && active === 'Corporate actions' && <Panel title="Corporate action notices" note="Announced events are not completed payments."><Table columns={['Notice', 'Instrument', 'Record date', 'Effective date', 'Status']} rows={data.corporate_actions.map((a: any) => [a.title, a.instrument, day(a.record_date), day(a.effective_date), a.status])}/></Panel>}
    {page === 'custody' && active === 'Settlements' && <><div className="inline-filter"><label>Status<select value={statusFilter} onChange={e => setStatusFilter(e.target.value)}><option value="all">All statuses</option><option value="settled">Settled</option><option value="pending">Pending</option></select></label></div><Panel title="Historical settlement status"><Table columns={['Reference', 'Instrument', 'Trade date', 'Settlement date', 'Quantity', 'Status']} rows={data.settlements.filter((s: any) => statusFilter === 'all' || s.status === statusFilter).map((s: any) => [s.id, s.instrument, day(s.trade_date), day(s.settlement_date), s.quantity, s.status])}/></Panel></>}
    {page === 'custody' && active === 'Statements' && <Panel title="Custody account statements"><Table columns={['Year', 'Dividends credited', 'Settled events']} rows={data.statements.map((s: any) => [s.period, money(s.dividends_credited_jpy), s.settled_events])}/></Panel>}

    {page === 'equity' && active === 'Awards' && <><Metrics entries={[{ label: 'Award grants', value: `${data.summary.grant_count}` }, { label: 'Vested units', value: `${data.summary.vested_units}` }, { label: 'Exercise eligible options', value: `${data.summary.exercise_eligible_options}` }]}/><div className="inline-filter"><label>Award type<select value={awardFilter} onChange={e => setAwardFilter(e.target.value)}><option value="all">All awards</option><option value="RSU">RSU</option><option value="Option">Option</option></select></label></div>{data.grants.filter((g: any) => awardFilter === 'all' || g.award_type === awardFilter).map((g: any) => <Panel key={g.id} title={`${g.award_type} · ${g.id}`} note={`Granted ${day(g.grant_date)}`}><div className="detail-grid"><div><span>Granted</span><strong>{g.granted_units} units</strong></div><div><span>Vested / unvested</span><strong>{g.vested_units} / {g.unvested_units}</strong></div><div><span>Released / exercised</span><strong>{g.released_units} / {g.exercised_units}</strong></div><div><span>Forfeited</span><strong>{g.forfeited_units}</strong></div><div><span>Exercise price</span><strong>{g.exercise_price_jpy ? money(Number(g.exercise_price_jpy)) : 'Not applicable'}</strong></div><div><span>Illustrative award value</span><strong>{money(g.illustrative_award_value_jpy)}</strong></div></div><div className="panel-note">{g.vesting_condition}. Vesting does not itself execute, release, or sell shares.</div></Panel>)}{!data.grants.length && <p className="empty">No equity awards have been granted to this employee.</p>}<p className="disclaimer">{data.note}</p></>}
    {page === 'equity' && active === 'Vesting' && <Panel title="Award vesting schedule" note={`Next: ${day(data.next_vesting?.vest_date)}`}><Table columns={['Grant', 'Award type', 'Vest date', 'Units', 'Status']} rows={data.grants.flatMap((g: any) => g.vesting_events.map((v: any) => [g.id, g.award_type, day(v.vest_date), v.units, v.status]))}/></Panel>}
    {page === 'equity' && active === 'Statements' && <Panel title="Equity award statements"><Table columns={['Grant ID', 'Date', 'Award', 'Granted units', 'Vested units']} rows={data.statements.map((s: any) => [s.grant_id, day(s.grant_date), s.award_type, s.granted_units, s.vested_units])}/></Panel>}
  </>
}
