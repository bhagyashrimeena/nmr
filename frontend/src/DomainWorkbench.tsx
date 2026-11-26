import { useEffect, useMemo, useState } from 'react'

type Domain = 'stock' | 'pension' | 'wellness' | 'custody' | 'equity'
type Request = (path: string, options?: RequestInit) => Promise<any>
type Props = {
  domain: Domain
  tenant: string
  employee: string
  request: Request
  onNavigate: (tab: string) => void
}

const paths: Record<Domain, string> = {
  stock: 'shareholding', pension: 'pension', wellness: 'wellness', custody: 'custody', equity: 'equity',
}
const titles: Record<Domain, string> = {
  stock: 'Shareholding operations',
  pension: 'Pension investment administration',
  wellness: 'Financial education programmes',
  custody: 'Asset servicing and settlement',
  equity: 'Equity award administration',
}
const purposes: Record<Domain, string> = {
  stock: 'Reconcile payroll, close purchase cycles and manage association holdings.',
  pension: 'Monitor plan funds, participant positions and investment instructions.',
  wellness: 'Govern employer content, published benefits and learning sessions.',
  custody: 'Track securities accounts, pending transfers and corporate actions.',
  equity: 'Manage plan reserves, grant approvals and release eligibility.',
}

function nice(value: unknown): string {
  return String(value ?? '—').replaceAll('_', ' ')
}
function money(value: unknown): string {
  return value == null ? '—' : '¥' + Number(value).toLocaleString('en-US', { maximumFractionDigits: 2 })
}
function numeric(value: unknown): string {
  return value == null ? '—' : Number(value).toLocaleString('en-US', { maximumFractionDigits: 6 })
}
function day(value: unknown): string {
  return value ? String(value).slice(0, 10) : '—'
}
function stateClass(status: string): string {
  const s = status.toUpperCase()
  if (['OPEN', 'FAILED', 'REJECTED', 'SUSPENDED', 'EXPIRED'].includes(s)) return 'dw-critical'
  if (['PENDING', 'DRAFT', 'PREPARED', 'ANNOUNCED', 'RECEIVED', 'CREATED', 'VALIDATED', 'IN_REVIEW'].includes(s)) return 'dw-pending'
  return 'dw-neutral'
}
function Status({value}: {value: string}) {
  return <span className={'dw-status ' + stateClass(value)}>{nice(value)}</span>
}
function Kpis({items}: {items: Array<{label: string;value: string;detail?: string}>}) {
  return <div className="dw-metrics">{items.map(item =>
    <div key={item.label} className="dw-metric"><span>{item.label}</span><strong>{item.value}</strong>
      {item.detail && <small>{item.detail}</small>}</div>)}</div>
}
function Panel({title,meta,children}: {title: string;meta?: string;children: React.ReactNode}) {
  return <section className="dw-panel"><div className="dw-panel-title"><h3>{title}</h3><span>{meta}</span></div>{children}</section>
}
function Empty({label = 'No records for the current view.'}: {label?: string}) {
  return <p className="dw-empty">{label}</p>
}
function GridTable({headers,rows}: {headers: string[];rows: React.ReactNode[][]}) {
  if (!rows.length) return <Empty/>
  return <div className="table-wrap dw-table-wrap"><table><thead><tr>{headers.map(h=><th key={h}>{h}</th>)}</tr></thead>
    <tbody>{rows.map((row,i)=><tr key={i}>{row.map((v,j)=><td key={j}>{v}</td>)}</tr>)}</tbody></table></div>
}
function Detail({title,subtitle,entries,children}: {
  title: string;subtitle?: string;entries: Array<[string,string]>;children?:React.ReactNode
}) {
  return <aside className="dw-detail"><span className="dw-kicker">Selected record</span><h3>{title}</h3>
    {subtitle && <p className="dw-detail-subtitle">{subtitle}</p>}
    <dl>{entries.map(([k,v])=><div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl>{children}</aside>
}
function Action({children,to,onNavigate}: {children:React.ReactNode;to:string;onNavigate:(tab:string)=>void}) {
  return <button type="button" className="dw-action" onClick={()=>onNavigate(to)}>{children}</button>
}
function Workflow({items}: {items:Array<{label:string;value:number}>}) {
  return <div className="dw-workflow" aria-label="Workflow stage counts">{items.map((item,i)=>
    <div className="dw-step" key={item.label}>
      <span className="dw-step-index">{String(i+1).padStart(2,'0')}</span>
      <strong>{numeric(item.value)}</strong><span>{item.label}</span>
    </div>)}</div>
}

function Stock({data,onNavigate,query}: {data:any;onNavigate:Props['onNavigate'];query:string}) {
  const batches:any[] = data.payroll_batches || []
  const purchases:any[] = data.purchase_cycles || []
  const exceptions:any[] = data.exceptions || []
  const rows = batches.filter(x=>JSON.stringify(x).toLowerCase().includes(query))
  const [selected,setSelected] = useState('')
  const chosen = rows.find(x=>x.id===selected) || rows[0]
  const flagged = exceptions.filter(x=>x.status==='OPEN' || x.status==='INVESTIGATING')
  return <>
    <Kpis items={[
      {label:'Plan members',value:numeric(data.members?.length),detail: data.plan?.id},
      {label:'Unresolved payroll / reconciliation cases',value:numeric(flagged.length)},
      {label:'Purchase batches awaiting allocation',value:numeric(purchases.filter(x=>x.state!=='ALLOCATED' && x.state!=='FAILED').length)}
    ]}/>
    <Workflow items={[
      {label:'Payroll received',value:batches.filter(x=>x.state==='RECEIVED').length},
      {label:'Validated',value:batches.filter(x=>x.state==='VALIDATED').length},
      {label:'Posted',value:batches.filter(x=>x.state==='POSTED').length},
      {label:'Purchase allocations settled',value:purchases.filter(x=>x.state==='ALLOCATED').length}
    ]}/>
    <div className="dw-columns">
      <div>
        <Panel title="Payroll batch processing" meta="Select a batch to inspect its source">
          <GridTable headers={['Source / period','Expected','Received','State','Exceptions']} rows={rows.slice(0,12).map(x=>[
            <button type="button" className={'dw-link'+(chosen?.id===x.id?' current':'')} onClick={()=>setSelected(x.id)}>
              {x.source_reference}<small>{day(x.period)}</small></button>,
            money(x.expected_jpy),money(x.received_jpy),<Status value={x.state}/>,numeric(x.failed_lines)
          ])}/>
          <div className="dw-panel-footer"><Action to="Payroll batches" onNavigate={onNavigate}>Receive / review payroll</Action></div>
        </Panel>
        <Panel title="Purchase and share allocation" meta="No shares created until confirmed allocation">
          <GridTable headers={['Cycle','Trade date','Acquired units','State']} rows={purchases.slice(0,7).map(x=>[
            x.id,day(x.trade_date),numeric(x.acquired_units),<Status value={x.state}/>
          ])}/>
          <div className="dw-panel-footer"><Action to="Purchase cycles" onNavigate={onNavigate}>Open purchase cycles</Action></div>
        </Panel>
      </div>
      <div>
        {chosen ? <Detail title={chosen.source_reference} subtitle={'Payroll period '+day(chosen.period)} entries={[
          ['Processing state',nice(chosen.state)],['Expected payroll',money(chosen.expected_jpy)],
          ['Received payroll',money(chosen.received_jpy)],['Rejected lines',numeric(chosen.failed_lines)],
          ['Difference',money(Number(chosen.expected_jpy)-Number(chosen.received_jpy))]
        ]}><Action to="Payroll batches" onNavigate={onNavigate}>Investigate batch</Action></Detail> :
        <Detail title="No payroll batch" entries={[]}/>}
        <Panel title="Exceptions requiring attention" meta={flagged.length+' active'}>
          {flagged.length ? flagged.slice(0,5).map(x=><div className="dw-case" key={x.id}>
            <div><strong>{x.id}</strong><small>{nice(x.break_type)} · {x.source_reference}</small></div><Status value={x.status}/></div>):<Empty label="No active reconciliation cases."/>}
          <div className="dw-panel-footer"><Action to="Exceptions" onNavigate={onNavigate}>Review exceptions</Action></div>
        </Panel>
      </div>
    </div>
  </>
}

function Pension({data,employee,onNavigate,query}: {data:any;employee:string;onNavigate:Props['onNavigate'];query:string}) {
  const accounts:any[] = data.accounts || []
  const selected = accounts.find(a=>a.employee_id===employee) || accounts[0]
  const funds:any[] = data.funds || []
  const instructions:any[] = data.instructions || []
  const active = instructions.filter(x=>!['EFFECTIVE_NEXT_CONTRIBUTION','REJECTED','CANCELLED'].includes(x.state))
  const total = selected ? Number(selected.balance_jpy) : 0
  const rows = funds.filter(x=>JSON.stringify(x).toLowerCase().includes(query))
  return <>
    <Kpis items={[
      {label:'Retirement accounts',value:numeric(accounts.length),detail:data.plan?.id},
      {label:'Dated plan fund products',value:numeric(funds.length),detail:'Recorded NAV only'},
      {label:'Pending contribution instructions',value:numeric(active.length)}
    ]}/>
    <div className="dw-pension-summary">
      <div><span className="dw-kicker">Participant valuation · {selected?.employee_id || 'No account'}</span>
        <strong>{money(total)}</strong><p>Based on dated fund units and NAV. Future-contribution changes do not alter existing holdings.</p></div>
      <Action to="Fund positions" onNavigate={onNavigate}>Inspect fund positions</Action>
    </div>
    <div className="dw-columns">
      <div>
        <Panel title="Investment funds and dated NAV" meta="Plan product register">
          <GridTable headers={['Fund','Asset category','NAV','Fee']} rows={rows.slice(0,12).map(x=>[
            <span className="dw-fund-name"><strong>{x.name}</strong><small>{x.id}</small></span>,
            nice(x.category),money(x.latest_nav_jpy),String(x.annual_fee_percent)+'%'
          ])}/>
          <div className="dw-panel-footer"><Action to="Investment funds" onNavigate={onNavigate}>Open product catalog</Action></div>
        </Panel>
        <Panel title="Future-contribution instructions" meta="Different from switching current holdings">
          <GridTable headers={['Instruction','Participant','Allocation state']} rows={active.slice(0,6).map(x=>[
            x.instruction_id,x.employee_id,<Status value={x.state}/>
          ])}/>
          <div className="dw-panel-footer"><Action to="Instruction queue" onNavigate={onNavigate}>Review instructions</Action></div>
        </Panel>
      </div>
      <div>
        <Panel title="Selected account · fund allocation" meta={selected?.employee_id || '—'}>
          {selected?.positions?.length ? selected.positions.map((x:any)=>{
            const percentage=total?100*Number(x.value_jpy)/total:0
            return <div className="dw-allocation" key={x.fund_id}><div><strong>{x.fund_name}</strong><span>{percentage.toFixed(1)}% · {money(x.value_jpy)}</span></div>
              <div className="dw-track"><div style={{width:Math.max(0,Math.min(100,percentage))+'%'}}/></div></div>
          }):<Empty label="No fund positions available."/>}
          <div className="dw-panel-footer"><Action to="Projection" onNavigate={onNavigate}>Run retirement projection</Action></div>
        </Panel>
        <Panel title="Pension exceptions" meta={(data.exceptions||[]).length+' recorded'}>
          {(data.exceptions||[]).slice(0,4).map((x:any)=><div className="dw-case" key={x.id}>
            <div><strong>{x.id}</strong><small>{nice(x.break_type)} · {x.employee_id || 'Plan'}</small></div><Status value={x.status}/></div>)}
          {!data.exceptions?.length&&<Empty/>}
          <div className="dw-panel-footer"><Action to="Exceptions" onNavigate={onNavigate}>Investigate pension cases</Action></div>
        </Panel>
      </div>
    </div>
  </>
}

function Wellness({data,onNavigate,query}: {data:any;onNavigate:Props['onNavigate'];query:string}) {
  const content:any[]=data.content||[], seminars:any[]=data.seminars||[]
  const current=content.filter(x=>x.state==='PUBLISHED' && x.review_expires_on>=data.as_of && x.effective_date<=data.as_of)
  const review=content.filter(x=>x.state==='DRAFT'||x.state==='IN_REVIEW'||x.state==='APPROVED'||(x.state==='PUBLISHED'&&x.review_expires_on<data.as_of))
  const [selected,setSelected]=useState('')
  const visible=content.filter(x=>JSON.stringify(x).toLowerCase().includes(query))
  const chosen=visible.find(x=>x.id===selected)||visible[0]
  return <>
    <div className="dw-editorial-head">
      <div><span className="dw-kicker">Employer learning programme</span>
        <h3>Content, benefits & education</h3><p>Manage editorial approval, current plan explanations and employee learning sessions.</p></div>
      <div><strong>{current.length}</strong><span>Published & current resources</span></div>
    </div>
    <Kpis items={[
      {label:'Items requiring editorial review',value:numeric(review.length)},
      {label:'Source-backed benefit rules',value:numeric(data.benefit_rules?.length)},
      {label:'Scheduled workshops',value:numeric(seminars.length)}
    ]}/>
    <div className="dw-columns">
      <div>
        <Panel title="Editorial pipeline" meta="Content must be reviewed before publication">
          <GridTable headers={['Resource','Category','Revision','State','Review deadline']} rows={visible.slice(0,12).map(x=>[
            <button type="button" className={'dw-link'+(chosen?.id===x.id?' current':'')} onClick={()=>setSelected(x.id)}>
              {x.title}<small>{x.id}</small></button>,
            nice(x.category),'v'+x.revision,<Status value={x.state}/>,day(x.review_expires_on)
          ])}/>
          <div className="dw-panel-footer"><Action to="Content library" onNavigate={onNavigate}>Open editorial reviews</Action></div>
        </Panel>
        <Panel title="Upcoming seminars" meta="Programme scheduling">
          <GridTable headers={['Session','Date','Enrolled','State']} rows={seminars.slice(0,6).map(x=>[
            x.title,day(x.starts_at),numeric(x.registrations)+' / '+numeric(x.capacity),<Status value={x.status}/>
          ])}/>
          <div className="dw-panel-footer"><Action to="Seminars" onNavigate={onNavigate}>View seminar programme</Action></div>
        </Panel>
      </div>
      <div>
        {chosen?<Detail title={chosen.title} subtitle={chosen.category+' · '+chosen.language} entries={[
          ['Editorial state',nice(chosen.state)],['Revision','v'+chosen.revision],
          ['Effective',day(chosen.effective_date)],['Review expires',day(chosen.review_expires_on)],
          ['Approved source',chosen.source_reference]
        ]}><p className="dw-excerpt">{String(chosen.body||'').slice(0,400)}</p><Action to="Content library" onNavigate={onNavigate}>Review this content</Action></Detail>:
        <Detail title="No content selected" entries={[]}/>}
        <Panel title="Employer benefit rules" meta="Source-controlled disclosures">
          {(data.benefit_rules||[]).slice(0,4).map((x:any)=><div className="dw-case" key={x.id}><div><strong>{nice(x.benefit_key)}</strong><small>{x.source_reference}</small></div><span className="dw-muted">{day(x.effective_date)}</span></div>)}
          <div className="dw-panel-footer"><Action to="Benefit rules" onNavigate={onNavigate}>Inspect benefit rules</Action></div>
        </Panel>
      </div>
    </div>
  </>
}

function Custody({data,onNavigate,query}: {data:any;onNavigate:Props['onNavigate'];query:string}) {
  const transfers:any[]=data.transfers||[], actions:any[]=data.actions||[], accounts:any[]=data.accounts||[]
  const pending=transfers.filter(x=>x.settlement_state!=='SETTLED_CONFIRMED')
  const [selected,setSelected]=useState('')
  const visible=transfers.filter(x=>JSON.stringify(x).toLowerCase().includes(query))
  const chosen=visible.find(x=>x.id===selected)||visible[0]
  const openActions=actions.filter(x=>x.state!=='RECONCILED'&&x.state!=='CANCELLED')
  return <>
    <div className="dw-custody-strip" aria-label="Settlement status overview">
      <div><span>Custody accounts</span><strong>{numeric(accounts.length)}</strong></div>
      <div><span>Transfer confirmations outstanding</span><strong>{numeric(pending.length)}</strong></div>
      <div><span>Open corporate actions</span><strong>{numeric(openActions.length)}</strong></div>
      <div><span>Dividend entries</span><strong>{numeric(data.dividends?.length)}</strong></div>
    </div>
    <div className="dw-columns dw-custody-columns">
      <div>
        <Panel title="Settlement and transfer monitor" meta="Account-level instruction state">
          <GridTable headers={['Transfer ID','Employee','Units','Processing state','Settlement']} rows={visible.slice(0,16).map(x=>[
            <button type="button" className={'dw-link'+(chosen?.id===x.id?' current':'')} onClick={()=>setSelected(x.id)}>
              {x.id}<small>{x.correlation_id}</small></button>,
            x.employee_id,numeric(x.units),<Status value={x.state}/>,<Status value={x.settlement_state}/>
          ])}/>
          <div className="dw-panel-footer"><Action to="Settlement monitor" onNavigate={onNavigate}>Open settlement monitor</Action></div>
        </Panel>
        <Panel title="Corporate-action register" meta="Entitlement and posting states">
          <GridTable headers={['Action','Account','Type','Effective','State']} rows={actions.slice(0,9).map(x=>[
            x.id,x.account_id,nice(x.action_type),day(x.effective_date),<Status value={x.state}/>
          ])}/>
          <div className="dw-panel-footer"><Action to="Action register" onNavigate={onNavigate}>Review corporate actions</Action></div>
        </Panel>
      </div>
      <div>
        {chosen?<Detail title={chosen.id} subtitle={'Instruction for '+chosen.employee_id} entries={[
          ['State',nice(chosen.state)],['Settlement',nice(chosen.settlement_state)],
          ['Share quantity',numeric(chosen.units)],
          ['Correlation reference',chosen.correlation_id || '—'],
          ['Confirmation',chosen.confirmation_reference || 'Not yet provided']
        ]}><Action to="Settlement monitor" onNavigate={onNavigate}>Investigate settlement</Action></Detail>:
        <Detail title="No transfer selected" entries={[]}/>}
        <Panel title="Cash income / dividend processing" meta="Scheduled is not paid">
          {(data.dividends||[]).slice(0,5).map((x:any)=><div className="dw-case" key={x.id}>
            <div><strong>{x.id}</strong><small>{money(x.amount_jpy)} · {day(x.payment_date)}</small></div><Status value={x.state}/></div>)}
          <div className="dw-panel-footer"><Action to="Dividend processing" onNavigate={onNavigate}>Review dividend ledger</Action></div>
        </Panel>
      </div>
    </div>
  </>
}

function Equity({data,onNavigate,query}: {data:any;onNavigate:Props['onNavigate'];query:string}) {
  const grants:any[]=data.grants||[], releases:any[]=data.releases||[]
  const [selected,setSelected]=useState('')
  const [kind,setKind]=useState('all')
  const visible=grants.filter(x=>(kind==='all'||x.award_type===kind)&&JSON.stringify(x).toLowerCase().includes(query))
  const chosen=visible.find(x=>x.id===selected)||visible[0]
  const reserve=Number(data.plan?.authorized_units||0),issued=Number(data.plan?.issued_units||0)
  const utilization=reserve?Math.min(100,100*issued/reserve):0
  const releaseQueue=releases.filter(x=>x.state!=='SIMULATED_RELEASED')
  return <>
    <div className="dw-equity-reserve">
      <div><span className="dw-kicker">Share reserve utilisation</span><h3>{data.plan?.name}</h3>
        <div className="dw-track"><div style={{width:utilization+'%'}}/></div>
        <p>{numeric(issued)} issued / {numeric(reserve)} authorised units</p></div>
      <div><strong>{numeric(data.plan?.remaining_units)}</strong><span>Units remaining</span></div>
    </div>
    <Kpis items={[
      {label:'Grant records',value:numeric(grants.length)},
      {label:'Grant proposals awaiting approval',value:numeric(grants.filter(x=>x.state==='PROPOSED').length)},
      {label:'Releases pending review',value:numeric(releaseQueue.length)}
    ]}/>
    <div className="dw-columns">
      <div>
        <Panel title="Award grant register" meta="Grant state is distinct from vesting and release">
          <div className="dw-inline-filter"><label>Award type <select value={kind} onChange={e=>{setKind(e.target.value);setSelected('')}}><option value="all">All awards</option>
            {[...new Set(grants.map(x=>x.award_type))].map(k=><option key={k} value={k}>{k}</option>)}</select></label></div>
          <GridTable headers={['Grant','Participant','Type','Units','State']} rows={visible.slice(0,14).map(x=>[
            <button type="button" className={'dw-link'+(chosen?.id===x.id?' current':'')} onClick={()=>setSelected(x.id)}>{x.id}</button>,
            x.employee_id,x.award_type,numeric(x.granted_units),<Status value={x.state}/>
          ])}/>
          <div className="dw-panel-footer"><Action to="Grant register" onNavigate={onNavigate}>Open grant approvals</Action></div>
        </Panel>
        <Panel title="Release processing" meta="Release does not itself confirm custody credit">
          <GridTable headers={['Release','Grant','Units','State']} rows={releaseQueue.slice(0,7).map(x=>[
            x.id,x.grant_id,numeric(x.units),<Status value={x.state}/>
          ])}/>
          <div className="dw-panel-footer"><Action to="Release queue" onNavigate={onNavigate}>Review releases</Action></div>
        </Panel>
      </div>
      <div>
        {chosen?<Detail title={chosen.id} subtitle={chosen.award_type+' · '+chosen.employee_id} entries={[
          ['Grant state',nice(chosen.state)],['Units granted',numeric(chosen.granted_units)],
          ['Vested, not released',numeric(chosen.vested_unreleased_units)],
          ['Scheduled, unvested',numeric(chosen.scheduled_unvested_units)],
          ['Forfeited',numeric(chosen.forfeited_units)],['Plan reconciliation',chosen.reconciled?'Reconciled':'Review required']
        ]}>
          <div className="dw-tranches"><h4>Vesting timeline</h4>{(chosen.tranches||[]).map((x:any)=><div className="dw-tranche" key={x.id}>
            <span>{day(x.vest_date)}</span><span>{numeric(x.units)} units</span><Status value={x.state}/></div>)}</div>
          <Action to="Vesting schedule" onNavigate={onNavigate}>Open vesting schedule</Action>
        </Detail>:<Detail title="No grant selected" entries={[]}/>}
        <Panel title="Equity exceptions" meta={(data.exceptions||[]).length+' recorded'}>
          {(data.exceptions||[]).slice(0,5).map((x:any)=><div className="dw-case" key={x.id}>
            <div><strong>{x.id}</strong><small>{nice(x.break_type)} · {x.employee_id || 'Plan'}</small></div><Status value={x.status}/></div>)}
          <div className="dw-panel-footer"><Action to="Equity exceptions" onNavigate={onNavigate}>Investigate exceptions</Action></div>
        </Panel>
      </div>
    </div>
  </>
}

export default function DomainWorkbench({domain,tenant,employee,request,onNavigate}:Props) {
  const [data,setData]=useState<any>(null)
  const [error,setError]=useState('')
  const [filter,setFilter]=useState('')
  const [refresh,setRefresh]=useState(0)
  const path='/api/v2/admin/tenants/'+encodeURIComponent(tenant)+'/'+paths[domain]+'/operations'
  useEffect(()=>{
    let cancelled=false
    setData(null);setError('');setFilter('')
    request(path).then(value=>{if(!cancelled)setData(value)})
      .catch(e=>{if(!cancelled)setError((e as Error).message)})
    return ()=>{cancelled=true}
  },[path,request,refresh])
  const dateLabel=useMemo(()=>day(data?.as_of),[data?.as_of])
  return <div className={'domain-workbench dw-'+domain}>
    <header className="dw-heading"><div><span className="dw-kicker">Provider operations / {titles[domain]}</span>
      <h2>{titles[domain]}</h2><p>{purposes[domain]}</p></div>
      <div className="dw-heading-actions"><span>Record date {dateLabel}</span>
        <button type="button" onClick={()=>setRefresh(x=>x+1)}>Refresh</button></div>
    </header>
    <div className="dw-search"><label>Find operational records
      <input type="search" value={filter} onChange={e=>setFilter(e.target.value)}
        placeholder={domain==='stock'?'Source, payroll or status':domain==='pension'?'Fund, instruction or participant':domain==='wellness'?'Content title or category':domain==='custody'?'Transfer or settlement reference':'Grant, employee or award type'}/></label>
      <span>Searches the current service's operational records</span></div>
    {error && <div className="error" role="alert">{error}</div>}
    {!data && !error && <div className="loading">Retrieving {titles[domain].toLowerCase()}…</div>}
    {data && domain==='stock' && <Stock data={data} query={filter.toLowerCase()} onNavigate={onNavigate}/>}
    {data && domain==='pension' && <Pension data={data} employee={employee} query={filter.toLowerCase()} onNavigate={onNavigate}/>}
    {data && domain==='wellness' && <Wellness data={data} query={filter.toLowerCase()} onNavigate={onNavigate}/>}
    {data && domain==='custody' && <Custody data={data} query={filter.toLowerCase()} onNavigate={onNavigate}/>}
    {data && domain==='equity' && <Equity data={data} query={filter.toLowerCase()} onNavigate={onNavigate}/>}
  </div>
}
