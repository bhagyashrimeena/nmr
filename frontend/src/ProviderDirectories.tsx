import { useEffect, useState } from 'react'

type Employee = { id: string; display_name: string; active: boolean; allowed_services: string[];
  department?: string; cohort?: string; hired_on?: string }
type Agreement = { id: string; service: string; status: string; legal_entity: string;
  effective_on: string; source_reference: string }

export function ClientAgreements({ agreements, tenantName }: { agreements: Agreement[]; tenantName: string }) {
  return <section className="section"><div className="section-heading"><h2>Service agreements · {tenantName}</h2><span>Contract references and effective dates</span></div><div className="table-wrap"><table><thead><tr>{['Service', 'Legal entity', 'Effective', 'Status', 'Source reference'].map(label => <th key={label}>{label}</th>)}</tr></thead><tbody>{agreements.map(row => <tr key={row.id}><td>{row.service}</td><td>{row.legal_entity}</td><td>{row.effective_on}</td><td>{row.status}</td><td>{row.source_reference}</td></tr>)}</tbody></table></div>{agreements.length === 0 && <p className="empty">No service agreement records are available.</p>}</section>
}

export function ParticipantDirectory({ employees, tenantName, onOpen }: {
  employees: Employee[]; tenantName: string; onOpen: (employeeId: string) => void
}) {
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(0)
  useEffect(() => { setSearch(''); setPage(0) }, [tenantName])
  const matched = employees.filter(row => `${row.id} ${row.display_name} ${row.department || ''} ${row.cohort || ''}`
    .toLowerCase().includes(search.toLowerCase().trim()))
  const visible = matched.slice(page * 15, (page + 1) * 15)
  return <><div className="metrics"><div className="metric"><span>Participant records</span><strong>{employees.length}</strong></div><div className="metric"><span>Active</span><strong>{employees.filter(row => row.active).length}</strong></div><div className="metric"><span>Search results</span><strong>{matched.length}</strong></div></div><div className="inline-filter"><label>Search participants<input value={search} onChange={event => { setSearch(event.target.value); setPage(0) }} placeholder="Name, ID, department or cohort"/></label></div><section className="section"><div className="section-heading"><h2>Participant directory · {tenantName}</h2><span>Page {page + 1} of {Math.max(1, Math.ceil(matched.length / 15))}</span></div><div className="table-wrap"><table><thead><tr>{['ID', 'Name', 'Department', 'Cohort', 'Joined', 'Status', 'Record'].map(label => <th key={label}>{label}</th>)}</tr></thead><tbody>{visible.map(row => <tr key={row.id}><td>{row.id}</td><td>{row.display_name}</td><td>{row.department || '—'}</td><td>{row.cohort?.replaceAll('_', ' ') || '—'}</td><td>{row.hired_on || '—'}</td><td>{row.active ? 'Active' : 'Inactive'}</td><td><button type="button" onClick={() => onOpen(row.id)}>Open</button></td></tr>)}</tbody></table></div>{!matched.length && <p className="empty">No participants match this search.</p>}<div className="inline-filter"><button type="button" disabled={page === 0} onClick={() => setPage(value => value - 1)}>Previous</button><button type="button" disabled={(page + 1) * 15 >= matched.length} onClick={() => setPage(value => value + 1)}>Next</button></div></section></>
}
