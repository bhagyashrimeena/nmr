import { useEffect, useState } from 'react'

const API = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000'
type Tenant = { id: string; name: string }
type Employee = { id: string; display_name: string; active: boolean; allowed_services: string[] }
type Setting = { tenant_id: string; enabled: boolean; changed_by: string; changed_at: string; reason: string }
type Event = { id: number; created_at: string; actor: string; employee_id: string | null; service: string; outcome: string; reason: string; request_id: string }
type Summary = { display_name: string; stock: any; pension: any; wellness: any; custody: any; equity: any }
type Overview = { name: string; employee_count: number; mcp_enabled: boolean; as_of: string; recent_activity: Event[] }

const nav = [
  ['overview', 'Overview'], ['stock', 'Employee Stock Ownership'], ['pension', 'Corporate Pension'],
  ['wellness', 'Financial Wellness'], ['custody', 'Trust & Custody'], ['equity', 'Equity Compensation'],
  ['access', 'MCP Access'], ['audit', 'Audit Records']
] as const
type Page = typeof nav[number][0]

function formatMoney(value: number | undefined) { return value === undefined ? '—' : `¥${value.toLocaleString('en-US')}` }
function date(value: string | undefined) { return value ? value.slice(0, 10) : '—' }

function Table({ headers, rows }: { headers: string[]; rows: (string | number)[][] }) {
  if (!rows.length) return <p className="empty">No records for this employee.</p>
  return <div className="table-wrap"><table><thead><tr>{headers.map(h => <th key={h}>{h}</th>)}</tr></thead><tbody>{rows.map((row, i) => <tr key={i}>{row.map((cell, j) => <td key={j}>{cell}</td>)}</tr>)}</tbody></table></div>
}

function Card({ label, value, detail }: { label: string; value: string; detail?: string }) {
  return <div className="metric"><span>{label}</span><strong>{value}</strong>{detail && <small>{detail}</small>}</div>
}

function ServiceContent({ page, summary }: { page: Page; summary: Summary }) {
  if (page === 'stock') {
    const s = summary.stock
    if (!s) return <p className="empty">No shareholding account is recorded for this employee.</p>
    return <><div className="metrics"><Card label="Shares held" value={`${s.shares_held} shares`} detail={s.plan_id}/><Card label="Monthly contribution" value={formatMoney(s.monthly_contribution_jpy)}/><Card label="Recorded contributions" value={formatMoney(s.total_contributions_jpy)}/></div><Section title="Recent share purchases" note="Payroll purchases are separate from awarded equity."><Table headers={['Purchase date', 'Shares', 'Price per share', 'Amount']} rows={s.recent_purchases.map((p: any) => [date(p.purchase_date), p.shares, formatMoney(p.price_jpy), formatMoney(p.amount_jpy)])}/></Section><Section title="Contribution history"><Table headers={['Payroll month', 'Amount']} rows={s.contributions.map((c: any) => [date(c.month).slice(0, 7), formatMoney(c.amount_jpy)])}/></Section></>
  }
  if (page === 'pension') {
    const p = summary.pension
    if (!p) return <p className="empty">No pension account is recorded for this employee.</p>
    return <><div className="metrics"><Card label="Account balance" value={formatMoney(p.balance_jpy)} detail={p.account_type}/><Card label="Employee contributions" value={formatMoney(p.employee_contributions_jpy)}/><Card label="Employer contributions" value={formatMoney(p.employer_contributions_jpy)}/></div><Section title="Investment allocation"><div className="allocation">{p.allocations.map((a: any) => <div key={a.asset_class}><span>{a.asset_class}</span><div className="bar"><i style={{width: `${a.percentage}%`}}/></div><strong>{a.percentage}%</strong></div>)}</div></Section><Section title="Recent contributions"><Table headers={['Date', 'Employee', 'Employer']} rows={p.recent_contributions.map((c: any) => [date(c.date), formatMoney(c.employee_amount_jpy), formatMoney(c.employer_amount_jpy)])}/></Section><p className="disclaimer">{p.note}</p></>
  }
  if (page === 'wellness') return <><div className="notice">Educational resources only. The catalog does not provide individual investment advice.</div><div className="resource-grid">{summary.wellness.resources.map((r: any) => <article className="resource" key={r.id}><span className="eyebrow">{r.topic}</span><h3>{r.title}</h3><p>{r.description}</p><div>{r.content}</div></article>)}</div></>
  if (page === 'custody') {
    const c = summary.custody
    return <><div className="metrics"><Card label="Held positions" value={`${c.positions.length}`}/><Card label="Latest dividend" value={formatMoney(c.dividends[0]?.amount_jpy)} detail={c.dividends[0]?.status || 'No dividend'}/></div><Section title="Custody positions"><Table headers={['Instrument', 'Quantity']} rows={c.positions.map((p: any) => [p.instrument, p.quantity])}/></Section><Section title="Dividend ledger"><Table headers={['Payment date', 'Instrument', 'Amount', 'Status']} rows={c.dividends.map((d: any) => [date(d.payment_date), d.instrument, formatMoney(d.amount_jpy), d.status])}/></Section><Section title="Corporate action notices"><Table headers={['Effective date', 'Instrument', 'Notice']} rows={c.corporate_actions.map((a: any) => [date(a.effective_date), a.instrument, a.title])}/></Section></>
  }
  const e = summary.equity
  return <><div className="metrics"><Card label="Award grants" value={`${e.grants.length}`}/><Card label="Next scheduled vesting" value={date(e.next_vesting?.vest_date)} detail={e.next_vesting ? `${e.next_vesting.units} units` : 'None scheduled'}/></div>{e.grants.length ? e.grants.map((g: any) => <Section title={`${g.award_type} · ${g.id}`} key={g.id} note={`Granted ${date(g.grant_date)} · ${g.granted_units} units`}><div className="grant-counts"><span>Vested <strong>{g.vested_units}</strong></span><span>Unvested <strong>{g.unvested_units}</strong></span></div><Table headers={['Vest date', 'Units', 'Status']} rows={g.vesting_events.map((v: any) => [date(v.vest_date), v.units, v.status])}/></Section>) : <p className="empty">No equity awards have been granted to this employee.</p>}</>
}

function Section({ title, note, children }: { title: string; note?: string; children: React.ReactNode }) {
  return <section className="section"><div className="section-heading"><h2>{title}</h2>{note && <span>{note}</span>}</div>{children}</section>
}

async function api(path: string, token: string, options?: RequestInit) {
  const response = await fetch(`${API}${path}`, { ...options, headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json', ...options?.headers } })
  const data = await response.json()
  if (!response.ok) throw new Error(data.error?.message || `Request failed (${response.status})`)
  return data
}

export default function App() {
  const [token, setToken] = useState(() => sessionStorage.getItem('nmr_admin_token') || '')
  const [username, setUsername] = useState('nmr-admin')
  const [password, setPassword] = useState('')
  const [page, setPage] = useState<Page>('overview')
  const [tenants, setTenants] = useState<Tenant[]>([])
  const [tenant, setTenant] = useState('toyota-demo')
  const [employees, setEmployees] = useState<Employee[]>([])
  const [employee, setEmployee] = useState('EMP-001')
  const [overview, setOverview] = useState<Overview | null>(null)
  const [summary, setSummary] = useState<Summary | null>(null)
  const [setting, setSetting] = useState<Setting | null>(null)
  const [events, setEvents] = useState<Event[]>([])
  const [filter, setFilter] = useState('all')
  const [reason, setReason] = useState('Provider demo access change')
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => { if (token) api('/api/v1/admin/tenants', token).then(setTenants).catch(e => setError(e.message)) }, [token])
  useEffect(() => {
    if (!token) return
    setLoading(true); setError(''); setSummary(null)
    Promise.all([
      api(`/api/v1/admin/tenants/${tenant}/overview`, token),
      api(`/api/v1/admin/tenants/${tenant}/employees`, token),
      api(`/api/v1/admin/tenants/${tenant}/mcp-access`, token),
      api(`/api/v1/admin/audit-events?tenantId=${tenant}`, token)
    ]).then(([o, emps, s, ev]) => { setOverview(o); setEmployees(emps); setSetting(s); setEvents(ev); if (!emps.some((e: Employee) => e.id === employee)) setEmployee(emps[0]?.id || '') })
      .catch(e => setError(e.message)).finally(() => setLoading(false))
  }, [token, tenant])
  useEffect(() => {
    if (!token || !employee) return
    setSummary(null)
    api(`/api/v1/admin/tenants/${tenant}/employees/${employee}/service-summary`, token)
      .then(setSummary).catch(e => setError(e.message))
  }, [token, tenant, employee])

  async function login(event: React.FormEvent) {
    event.preventDefault(); setError(''); setLoading(true)
    try {
      const response = await fetch(`${API}/api/v1/auth/admin-token`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ username, password }) })
      const data = await response.json()
      if (!response.ok) throw new Error(data.error?.message || 'Sign in failed')
      sessionStorage.setItem('nmr_admin_token', data.access_token); setToken(data.access_token); setPassword('')
    } catch (e) { setError((e as Error).message) } finally { setLoading(false) }
  }
  function logout() { sessionStorage.removeItem('nmr_admin_token'); setToken(''); setOverview(null); setSummary(null); setError('') }
  async function changeAccess() {
    if (!setting) return
    setSaving(true); setError('')
    try {
      const next = await api(`/api/v1/admin/tenants/${tenant}/mcp-access`, token, { method: 'PATCH', body: JSON.stringify({ enabled: !setting.enabled, reason }) })
      setSetting(next); setOverview(o => o ? { ...o, mcp_enabled: next.enabled } : o)
      setEvents(await api(`/api/v1/admin/audit-events?tenantId=${tenant}`, token))
    } catch (e) { setError((e as Error).message) } finally { setSaving(false) }
  }
  async function refreshAudit() { try { setEvents(await api(`/api/v1/admin/audit-events?tenantId=${tenant}`, token)); setError('') } catch (e) { setError((e as Error).message) } }

  if (!token) return <div className="login-shell"><div className="login-brand"><div className="brand-mark">NMR<span>/</span></div><p>WORKPLACE FINANCE</p><h1>Provider administration</h1><div className="login-line"/><span>Fictional internal demonstration · synthetic records</span></div><form className="login-panel" onSubmit={login}><span className="eyebrow">SECURE ACCESS</span><h2>Sign in to NMR</h2><p>Use the local demo administrator credentials configured in the backend.</p><label>Username<input value={username} onChange={e => setUsername(e.target.value)} autoComplete="username" required/></label><label>Password<input type="password" value={password} onChange={e => setPassword(e.target.value)} autoComplete="current-password" required/></label>{error && <div className="error" role="alert">{error}</div>}<button className="primary" disabled={loading}>{loading ? 'Signing in…' : 'Sign in'}</button></form></div>

  const title = nav.find(n => n[0] === page)?.[1] || ''
  const selected = employees.find(e => e.id === employee)
  const servicePage = ['stock', 'pension', 'wellness', 'custody', 'equity'].includes(page)
  const visibleEvents = filter === 'all' ? events : events.filter(e => e.outcome === filter)
  return <div className="app-shell"><aside className="sidebar"><div className="brand"><div className="brand-mark">NMR<span>/</span></div><small>WORKPLACE FINANCE</small></div><div className="workspace-label">PROVIDER CONSOLE</div><nav aria-label="Main navigation"><div className="nav-group">WORKSPACE</div>{nav.slice(0, 6).map(([key, label]) => <button key={key} className={page === key ? 'active' : ''} onClick={() => setPage(key)}><span className="nav-dot"/>{label}</button>)}<div className="nav-group admin-group">ADMINISTRATION</div>{nav.slice(6).map(([key, label]) => <button key={key} className={page === key ? 'active' : ''} onClick={() => setPage(key)}><span className="nav-dot"/>{label}</button>)}</nav><div className="sidebar-bottom"><div className="demo-pill">DEMO ENVIRONMENT</div><span>100% synthetic financial data</span></div></aside><div className="main-column"><header className="topbar"><div className="breadcrumb">NMR Provider <span>/</span> {title}</div><div className="top-actions"><span className="identity">NMR Administrator</span><button onClick={logout}>Sign out</button></div></header><main><div className="page-head"><div><div className="eyebrow">PROVIDER WORKSPACE <span>·</span> {overview?.as_of || '2026-11-25'}</div><h1>{title}</h1><p>{page === 'overview' ? 'Corporate client services and external access at a glance.' : page === 'access' ? 'Control new external API requests for this client.' : page === 'audit' ? 'Review permitted and denied provider API activity.' : 'Read-only financial records from the synthetic provider database.'}</p></div><div className="head-controls"><label>Client tenant<select value={tenant} onChange={e => { setTenant(e.target.value); setEmployee('') }}>{tenants.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}</select></label></div></div>{error && <div className="error" role="alert">{error}</div>}{loading && <div className="loading">Loading tenant records…</div>}{page === 'overview' && overview && <><div className="overview-banner"><div><span className="eyebrow">CORPORATE CLIENT · HYPOTHETICAL</span><h2>{overview.name}</h2><p>Provider-side view of five workplace finance services. All balances and people are fictional.</p></div><span className={`status ${overview.mcp_enabled ? 'on' : 'off'}`}>MCP ACCESS {overview.mcp_enabled ? 'ON' : 'OFF'}</span></div><div className="metrics"><Card label="Employee records" value={`${overview.employee_count}`}/><Card label="Service categories" value="5"/><Card label="Recent API events" value={`${events.length}`}/></div><Section title="Employees" note="Select a record to inspect the five services."><Table headers={['Employee ID', 'Name', 'Status', 'Service access']} rows={employees.map(e => [e.id, e.display_name, e.active ? 'Active' : 'Inactive', `${e.allowed_services.length} services`])}/></Section><Section title="Recent external activity"><Table headers={['Time', 'Employee', 'Service', 'Outcome']} rows={overview.recent_activity.map(e => [date(e.created_at), e.employee_id || e.actor, e.service, e.outcome])}/></Section></>}{servicePage && <><div className="employee-toolbar"><div><span className="eyebrow">EMPLOYEE RECORD</span><strong>{selected?.display_name || 'Select employee'}</strong><span>{selected?.id || ''}</span></div><label>Employee<select value={employee} onChange={e => setEmployee(e.target.value)}>{employees.map(e => <option key={e.id} value={e.id}>{e.display_name} · {e.id}</option>)}</select></label></div>{summary ? <ServiceContent page={page} summary={summary}/> : <div className="loading">Loading employee record…</div>}</>}{page === 'access' && setting && <><div className="access-panel"><div><span className="eyebrow">TENANT ACCESS POLICY</span><h2>External MCP access</h2><p>New requests from the MCP adapter are checked against this stored setting on every protected API call.</p><div className={`access-state ${setting.enabled ? 'on' : 'off'}`}><span className="state-light"/>{setting.enabled ? 'Enabled' : 'Disabled'}</div></div><div className="access-action"><label>Reason for change<input value={reason} onChange={e => setReason(e.target.value)} maxLength={200} minLength={3}/></label><button className={setting.enabled ? 'danger' : 'primary'} disabled={saving || reason.trim().length < 3} onClick={changeAccess}>{saving ? 'Saving…' : setting.enabled ? 'Disable access' : 'Enable access'}</button></div></div><Section title="Last policy change"><div className="detail-grid"><div><span>Changed by</span><strong>{setting.changed_by}</strong></div><div><span>Changed at</span><strong>{setting.changed_at.replace('T', ' ').slice(0, 19)} UTC</strong></div><div><span>Reason</span><strong>{setting.reason}</strong></div></div></Section><div className="notice">This switch rejects new protected API requests. It cannot remove information already returned in a prior conversation.</div></>}{page === 'audit' && <><div className="audit-controls"><label>Outcome<select value={filter} onChange={e => setFilter(e.target.value)}><option value="all">All outcomes</option><option value="permitted">Permitted</option><option value="denied">Denied</option><option value="changed">Policy changes</option></select></label><button onClick={refreshAudit}>Refresh records</button></div><Section title="API and policy events" note={`${visibleEvents.length} shown`}><Table headers={['Timestamp (UTC)', 'Employee / actor', 'Service', 'Outcome', 'Reason', 'Request ID']} rows={visibleEvents.map(e => [e.created_at.replace('T', ' ').slice(0, 19), e.employee_id || e.actor, e.service, e.outcome, e.reason, e.request_id])}/></Section></>}</main><footer>NMR Workplace Finance POC <span>·</span> Fictional provider demo <span>·</span> Read-only records</footer></div></div>
}
