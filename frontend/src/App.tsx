import { useEffect, useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import ServiceViews from './ServiceViews'
import type { ServiceKey } from './ServiceViews'

const API = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000'
type Tenant = { id: string; name: string; mcp_enabled: boolean }
type Employee = { id: string; display_name: string; active: boolean; allowed_services: string[] }
type ServiceSetting = { service: ServiceKey; title: string; description: string; route: string; enabled: boolean; effective_enabled: boolean; changed_by: string; changed_at: string; reason: string }
type Setting = { tenant_id: string; enabled: boolean; changed_by: string; changed_at: string; reason: string; services: ServiceSetting[]; effective_service_count: number }
type Event = { id: number; created_at: string; actor: string; employee_id: string | null; service: string; outcome: string; reason: string; request_id: string }
type AccessChange = { id: number; created_at: string; actor: string; service: string; previous_enabled: boolean; new_enabled: boolean; reason: string; request_id: string }
type Overview = { name: string; employee_count: number; mcp_enabled: boolean; as_of: string; operational_service_count: number; configured_enabled_services: number; effective_enabled_services: number; recent_activity: Event[] }
type Page = 'overview' | ServiceKey | 'clients' | 'access' | 'audit'

const serviceNav: [ServiceKey, string][] = [
  ['stock', 'Employee Stock Ownership'], ['pension', 'Corporate Pension'],
  ['wellness', 'Financial Wellness'], ['custody', 'Trust & Custody'], ['equity', 'Equity Compensation'],
]
const pageNames: Record<Page, string> = { overview: 'Overview', stock: 'Employee Stock Ownership', pension: 'Corporate Pension',
  wellness: 'Financial Wellness', custody: 'Trust & Custody', equity: 'Equity Compensation',
  clients: 'Corporate Clients', access: 'MCP Access Management', audit: 'Audit Logs' }
const stamp = (value: string | undefined) => value ? `${value.replace('T', ' ').slice(0, 19)} UTC` : '—'

function Table({ columns, rows }: { columns: string[]; rows: (string | number)[][] }) {
  if (!rows.length) return <p className="empty">No records to show.</p>
  return <div className="table-wrap"><table><thead><tr>{columns.map(c => <th key={c}>{c}</th>)}</tr></thead><tbody>{rows.map((row, i) => <tr key={i}>{row.map((cell, j) => <td key={j}>{cell}</td>)}</tr>)}</tbody></table></div>
}

function Section({ title, note, children }: { title: string; note?: string; children: ReactNode }) {
  return <section className="section"><div className="section-heading"><h2>{title}</h2>{note && <span>{note}</span>}</div>{children}</section>
}

async function api(path: string, token: string, options?: RequestInit) {
  const response = await fetch(`${API}${path}`, { ...options,
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json', ...options?.headers } })
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
  const [summary, setSummary] = useState<any>(null)
  const [setting, setSetting] = useState<Setting | null>(null)
  const [events, setEvents] = useState<Event[]>([])
  const [changes, setChanges] = useState<AccessChange[]>([])
  const [outcomeFilter, setOutcomeFilter] = useState('all')
  const [serviceFilter, setServiceFilter] = useState('all')
  const [reason, setReason] = useState('Provider demo access change')
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState('')
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  useEffect(() => {
    if (!token) return
    api('/api/v1/admin/tenants', token).then(setTenants).catch(e => setError(e.message))
  }, [token])

  useEffect(() => {
    if (!token) return
    setLoading(true); setError(''); setSuccess(''); setSummary(null)
    Promise.all([
      api(`/api/v1/admin/tenants/${tenant}/overview`, token),
      api(`/api/v1/admin/tenants/${tenant}/employees`, token),
      api(`/api/v1/admin/tenants/${tenant}/mcp-access`, token),
      api(`/api/v1/admin/audit-events?tenantId=${tenant}`, token),
      api(`/api/v1/admin/tenants/${tenant}/access-changes`, token),
    ]).then(([o, emps, s, ev, ch]) => {
      setOverview(o); setEmployees(emps); setSetting(s); setEvents(ev); setChanges(ch)
      if (!emps.some((e: Employee) => e.id === employee)) setEmployee(emps[0]?.id || '')
    }).catch(e => setError(e.message)).finally(() => setLoading(false))
  }, [token, tenant])

  useEffect(() => {
    if (!token || !employee) return
    setSummary(null)
    api(`/api/v1/admin/tenants/${tenant}/employees/${employee}/service-summary`, token)
      .then(setSummary).catch(e => setError(e.message))
  }, [token, tenant, employee])

  async function login(event: FormEvent) {
    event.preventDefault(); setLoading(true); setError('')
    try {
      const response = await fetch(`${API}/api/v1/auth/admin-token`, { method: 'POST',
        headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ username, password }) })
      const data = await response.json()
      if (!response.ok) throw new Error(data.error?.message || 'Sign in failed')
      sessionStorage.setItem('nmr_admin_token', data.access_token)
      setToken(data.access_token); setPassword('')
    } catch (e) { setError((e as Error).message) } finally { setLoading(false) }
  }

  function logout() {
    sessionStorage.removeItem('nmr_admin_token')
    setToken(''); setOverview(null); setSummary(null); setError('')
  }

  async function refreshActivity() {
    try {
      const [ev, ch] = await Promise.all([
        api(`/api/v1/admin/audit-events?tenantId=${tenant}`, token),
        api(`/api/v1/admin/tenants/${tenant}/access-changes`, token),
      ])
      setEvents(ev); setChanges(ch); setError('')
    } catch (e) { setError((e as Error).message) }
  }

  async function changeAccess(service: 'master' | ServiceKey) {
    if (!setting) return
    const entry = service === 'master' ? null : setting.services.find(s => s.service === service)
    const enabled = service === 'master' ? !setting.enabled : !entry?.enabled
    const path = service === 'master' ? `/api/v1/admin/tenants/${tenant}/mcp-access`
      : `/api/v1/admin/tenants/${tenant}/service-access/${service}`
    setSaving(service); setError(''); setSuccess('')
    try {
      const next: Setting = await api(path, token, { method: 'PATCH', body: JSON.stringify({ enabled, reason: reason.trim() }) })
      setSetting(next)
      setOverview(o => o ? { ...o, mcp_enabled: next.enabled, effective_enabled_services: next.effective_service_count,
        configured_enabled_services: next.services.filter(s => s.enabled).length } : o)
      setSuccess(`${service === 'master' ? 'Master MCP access' : entry?.title} ${enabled ? 'enabled' : 'disabled'} for ${tenants.find(t => t.id === tenant)?.name || tenant}.`)
      await refreshActivity()
      setOverview(await api(`/api/v1/admin/tenants/${tenant}/overview`, token))
    } catch (e) { setError((e as Error).message) } finally { setSaving('') }
  }

  if (!token) return <div className="login-shell"><div className="login-brand"><div className="brand-mark">NMR<span>/</span></div><p>WORKPLACE FINANCE</p><h1>Provider administration</h1><div className="login-line"/><span>Fictional internal demonstration · synthetic records</span></div><form className="login-panel" onSubmit={login}><span className="eyebrow">SECURE ACCESS</span><h2>Sign in to NMR</h2><p>Use the local demo administrator credentials configured in the backend.</p><label>Username<input value={username} onChange={e => setUsername(e.target.value)} autoComplete="username" required/></label><label>Password<input type="password" value={password} onChange={e => setPassword(e.target.value)} autoComplete="current-password" required/></label>{error && <div className="error" role="alert">{error}</div>}<button className="primary" disabled={loading}>{loading ? 'Signing in…' : 'Sign in'}</button></form></div>

  const servicePage = serviceNav.some(([key]) => key === page)
  const selected = employees.find(e => e.id === employee)
  const visibleEvents = events.filter(e => (outcomeFilter === 'all' || e.outcome === outcomeFilter) &&
    (serviceFilter === 'all' || e.service === serviceFilter))
  const tenantName = tenants.find(t => t.id === tenant)?.name || tenant

  return <div className="app-shell">
    <aside className="sidebar"><div className="brand"><div className="brand-mark">NMR<span>/</span></div><small>WORKPLACE FINANCE</small></div><div className="workspace-label">PROVIDER CONSOLE</div><nav aria-label="Main navigation"><div className="nav-group">WORKSPACE</div><NavButton id="overview" page={page} setPage={setPage}/>{serviceNav.map(([key]) => <NavButton key={key} id={key} page={page} setPage={setPage}/>)}<div className="nav-group admin-group">ADMINISTRATION</div><NavButton id="clients" page={page} setPage={setPage}/><NavButton id="access" page={page} setPage={setPage}/><NavButton id="audit" page={page} setPage={setPage}/></nav><div className="sidebar-bottom"><div className="demo-pill">DEMO ENVIRONMENT</div><span>100% synthetic financial data</span></div></aside>
    <div className="main-column"><header className="topbar"><div className="breadcrumb">NMR Provider <span>/</span> {pageNames[page]}</div><div className="top-actions"><span className="identity">NMR Administrator</span><button onClick={logout}>Sign out</button></div></header>
      <main><div className="page-head"><div><div className="eyebrow">PROVIDER WORKSPACE <span>·</span> {overview?.as_of || '2026-11-25'}</div><h1>{pageNames[page]}</h1><p>{page === 'access' ? 'Control which external services are available to this corporate client.' : page === 'audit' ? 'Trace external requests and provider policy changes.' : page === 'clients' ? 'Review fictional corporate clients and their service access.' : servicePage ? 'Read-only synthetic records from the NMR provider database.' : 'Workplace finance services and tenant access at a glance.'}</p></div><div className="head-controls"><label>Corporate client<select value={tenant} onChange={e => { setTenant(e.target.value); setEmployee('') }}>{tenants.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}</select></label></div></div>
        {error && <div className="error" role="alert">{error}</div>}{success && <div className="success" role="status">{success}</div>}{loading && <div className="loading">Loading tenant records…</div>}

        {page === 'overview' && overview && <><div className="overview-banner"><div><span className="eyebrow">CORPORATE CLIENT · HYPOTHETICAL</span><h2>{overview.name}</h2><p>Five operational provider services. External availability is controlled separately.</p></div><span className={`status ${overview.mcp_enabled ? 'on' : 'off'}`}>MCP ACCESS {overview.mcp_enabled ? 'ON' : 'OFF'}</span></div><div className="metrics"><Metric label="Employee records" value={`${overview.employee_count}`}/><Metric label="Provider services" value={`${overview.operational_service_count || 5}`} detail="Available to NMR administrators"/><Metric label="Externally accessible" value={`${overview.effective_enabled_services} of 5`} detail="Master and service settings applied"/></div><Section title="Service access" note="Configured permission and effective external result"><Table columns={['Service', 'Configured', 'Effective external access']} rows={(setting?.services || []).map(s => [s.title, s.enabled ? 'Enabled' : 'Disabled', s.effective_enabled ? 'Accessible' : 'Blocked'])}/></Section><Section title="Employee records"><Table columns={['Employee ID', 'Name', 'Status', 'Eligible services']} rows={employees.map(e => [e.id, e.display_name, e.active ? 'Active' : 'Inactive', `${e.allowed_services.length} of 5`])}/></Section><Section title="Recent activity"><Table columns={['Time', 'Actor', 'Service', 'Outcome']} rows={overview.recent_activity.map(e => [stamp(e.created_at), e.employee_id || e.actor, e.service, e.outcome])}/></Section></>}

        {page === 'clients' && <><div className="notice">These corporate clients and people are fictional demonstration records.</div><div className="client-grid">{tenants.map(t => <article className={`client-card ${tenant === t.id ? 'current' : ''}`} key={t.id}><span className="eyebrow">CORPORATE CLIENT</span><h2>{t.name}</h2><p>{t.id}</p><span className={`status ${t.id === tenant && setting?.enabled ? 'on' : t.mcp_enabled ? 'on' : 'off'}`}>MCP {t.id === tenant ? setting?.enabled ? 'ON' : 'OFF' : t.mcp_enabled ? 'ON' : 'OFF'}</span><button onClick={() => { setTenant(t.id); setEmployee('') }} disabled={tenant === t.id}>{tenant === t.id ? 'Current client' : 'View client'}</button></article>)}</div><Section title={`Employees · ${tenantName}`}><Table columns={['ID', 'Name', 'Status', 'Available employee services']} rows={employees.map(e => [e.id, e.display_name, e.active ? 'Active' : 'Inactive', e.allowed_services.join(', ')])}/></Section></>}

        {servicePage && <><div className="employee-toolbar"><div><span className="eyebrow">EMPLOYEE RECORD</span><strong>{selected?.display_name || 'Select employee'}</strong><span>{selected?.id || ''}</span></div><label>Employee<select value={employee} onChange={e => setEmployee(e.target.value)}>{employees.map(e => <option key={e.id} value={e.id}>{e.display_name} · {e.id}</option>)}</select></label></div>{summary ? <ServiceViews page={page as ServiceKey} summary={summary} tenant={tenant} employee={employee} request={(path, options) => api(path, token, options)} onRefresh={async () => setSummary(await api(`/api/v1/admin/tenants/${tenant}/employees/${employee}/service-summary`, token))}/> : <div className="loading">Loading employee record…</div>}</>}

        {page === 'access' && setting && <><div className="access-panel"><div><span className="eyebrow">TENANT POLICY · {tenantName}</span><h2>Master MCP access</h2><p>Every new external service request checks this database setting. NMR administrators can still browse internal records when it is off.</p><div className={`access-state ${setting.enabled ? 'on' : 'off'}`}><span className="state-light"/>{setting.enabled ? 'Enabled' : 'Disabled'}</div></div><div className="access-action"><label>Reason for change<input value={reason} onChange={e => setReason(e.target.value)} minLength={3} maxLength={200}/></label><button className={setting.enabled ? 'danger' : 'primary'} disabled={Boolean(saving) || reason.trim().length < 3} onClick={() => changeAccess('master')}>{saving === 'master' ? 'Saving…' : setting.enabled ? 'Disable master access' : 'Enable master access'}</button></div></div><div className="access-summary"><strong>{setting.effective_service_count} of 5 services externally accessible</strong><span>Provider services remain operational internally. Individual settings are preserved when the master switch changes.</span></div><div className="service-access-list">{setting.services.map(s => <article className="service-access-row" key={s.service}><div><span className="eyebrow">{s.service.toUpperCase()}</span><h3>{s.title}</h3><p>{s.description}</p><code>{s.route}</code><small>Changed {stamp(s.changed_at)} by {s.changed_by}</small></div><div className="service-access-action"><span className={`status ${s.effective_enabled ? 'on' : 'off'}`}>{s.effective_enabled ? 'EXTERNALLY ACCESSIBLE' : 'EXTERNALLY BLOCKED'}</span><button className={s.enabled ? 'danger' : 'primary'} disabled={Boolean(saving) || reason.trim().length < 3} onClick={() => changeAccess(s.service)}>{saving === s.service ? 'Saving…' : s.enabled ? 'Disable service' : 'Enable service'}</button></div></article>)}</div><Section title="Policy change history" note="Previous and new values are retained"><Table columns={['Time (UTC)', 'Admin', 'Control', 'Previous', 'New', 'Reason']} rows={changes.map(c => [stamp(c.created_at), c.actor, c.service, c.previous_enabled ? 'On' : 'Off', c.new_enabled ? 'On' : 'Off', c.reason])}/></Section><div className="notice">Changes block new protected API calls at invocation time. Previously returned chat content cannot be revoked.</div></>}

        {page === 'audit' && <><div className="audit-controls"><div className="audit-filter-group"><label>Outcome<select value={outcomeFilter} onChange={e => setOutcomeFilter(e.target.value)}><option value="all">All outcomes</option><option value="permitted">Permitted</option><option value="denied">Denied</option><option value="changed">Policy changes</option></select></label><label>Service<select value={serviceFilter} onChange={e => setServiceFilter(e.target.value)}><option value="all">All services</option>{setting?.services.map(s => <option key={s.service} value={s.service}>{s.title}</option>)}<option value="mcp-access">Master MCP access</option></select></label></div><button onClick={refreshActivity}>Refresh records</button></div><Section title="External calls and policy events" note={`${visibleEvents.length} shown`}><Table columns={['Timestamp (UTC)', 'Employee / actor', 'Service', 'Outcome', 'Reason', 'Request ID']} rows={visibleEvents.map(e => [stamp(e.created_at), e.employee_id || e.actor, e.service, e.outcome, e.reason, e.request_id])}/></Section></>}
      </main><footer>NMR Workplace Finance POC <span>·</span> Fictional provider demo <span>·</span> Read-only financial records</footer>
    </div>
  </div>
}

function NavButton({ id, page, setPage }: { id: Page; page: Page; setPage: (page: Page) => void }) {
  return <button className={page === id ? 'active' : ''} onClick={() => setPage(id)}><span className="nav-dot"/>{pageNames[id]}</button>
}

function Metric({ label, value, detail }: { label: string; value: string; detail?: string }) {
  return <div className="metric"><span>{label}</span><strong>{value}</strong>{detail && <small>{detail}</small>}</div>
}
