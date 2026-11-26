import { useEffect, useState } from 'react'

export default function ReportSources({ tenant, service, asOf, request }: {
  tenant: string; service: string; asOf: string;
  request: (path: string, options?: RequestInit) => Promise<any>
}) {
  const [offset, setOffset] = useState(0)
  const [data, setData] = useState<any>(null)
  const [error, setError] = useState('')
  useEffect(() => { setOffset(0) }, [tenant, service, asOf])
  useEffect(() => {
    setData(null); setError('')
    request(`/api/v2/admin/tenants/${tenant}/reports/service/${service}/sources?as_of=${asOf}&offset=${offset}&limit=10`)
      .then(setData).catch(e => setError(e.message))
  }, [tenant, service, asOf, offset])
  return <section className="section"><div className="section-heading"><h2>Source journal</h2><span>{data ? `${data.total} entries · page ${Math.floor(offset / 10) + 1}` : 'Loading entries'}</span></div>{error && <p className="error" role="alert">{error}</p>}{data && <><div className="table-wrap"><table><thead><tr>{['Event ID', 'Effective', 'Employee', 'Type', 'Amount JPY', 'Quantity', 'Source'].map(label => <th key={label}>{label}</th>)}</tr></thead><tbody>{data.items.map((item: any) => <tr key={item.id}><td>{item.id}</td><td>{item.effective_at?.slice(0, 10)}</td><td>{item.employee_id || 'Plan'}</td><td>{item.type}</td><td>{item.amount_jpy}</td><td>{item.quantity}</td><td>{item.source_reference}</td></tr>)}</tbody></table></div>{data.total === 0 && <p className="empty">No journal entries for this service and date.</p>}<div className="inline-filter"><button type="button" disabled={offset === 0} onClick={() => setOffset(value => Math.max(value - 10, 0))}>Previous</button><button type="button" disabled={offset + 10 >= data.total} onClick={() => setOffset(value => value + 10)}>Next</button></div></>}</section>
}
