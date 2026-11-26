import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'

type Member = { employee_id: string; display_name: string; status: string; cash_jpy: string | number }
type Batch = { id: string; source_reference: string; state: string }
type Cycle = { id: string; state: string }
type Props = {
  tab: string
  tenant: string
  asOf: string
  plan: { minimum_monthly_jpy: string | number; maximum_monthly_jpy: string | number }
  members: Member[]
  payrollBatches: Batch[]
  purchaseCycles: Cycle[]
  request: (path: string, options?: RequestInit) => Promise<any>
  onSaved: () => Promise<void>
}

export default function StockWorkflowForms({
  tab, tenant, asOf, plan, members, payrollBatches, purchaseCycles, request, onSaved,
}: Props) {
  const [period, setPeriod] = useState('2026-10-01')
  const [payrollSource, setPayrollSource] = useState('')
  const [payrollEmployee, setPayrollEmployee] = useState('')
  const [payrollAmount, setPayrollAmount] = useState('20000')
  const [tradeDate, setTradeDate] = useState('2026-11-20')
  const [purchaseSource, setPurchaseSource] = useState('')
  const [purchaseEmployee, setPurchaseEmployee] = useState('')
  const [unitPrice, setUnitPrice] = useState('3000')
  const [units, setUnits] = useState('1')
  const [reviewReason, setReviewReason] = useState('Reviewed by NMR stock operations')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  useEffect(() => { setError(''); setSuccess(''); setPayrollSource(''); setPurchaseSource('') }, [tenant])
  const activeMembers = members.filter(m => m.status === 'ACTIVE')
  const employee = payrollEmployee || activeMembers[0]?.employee_id || ''
  const purchaseMember = purchaseEmployee || activeMembers[0]?.employee_id || ''
  const base = '/api/v2/admin/tenants/' + encodeURIComponent(tenant) + '/shareholding'

  async function perform(action: () => Promise<unknown>, message: string) {
    setBusy(true); setError(''); setSuccess('')
    try {
      await action()
      await onSaved()
      setSuccess(message)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function receivePayroll(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    await perform(async () => {
      if (!/^\d{4}-\d{2}-01$/.test(period)) throw new Error('Payroll periods must start on day 01.')
      if (!employee) throw new Error('Choose an active plan member.')
      await request(base + '/payroll-batches', {
        method: 'POST',
        body: JSON.stringify({
          period, source_reference: payrollSource.trim(), expected_jpy: payrollAmount,
          lines: [{ employee_id: employee, amount_jpy: payrollAmount }],
        }),
      })
      setPayrollSource('')
    }, 'Payroll batch received. Validate the batch separately before posting cash.')
  }

  async function receivePurchase(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    await perform(async () => {
      if (!purchaseMember) throw new Error('Choose an active plan member.')
      await request(base + '/purchase-cycles', {
        method: 'POST',
        body: JSON.stringify({
          source_reference: purchaseSource.trim(), trade_date: tradeDate,
          unit_price_jpy: unitPrice, acquired_units: units,
          allocations: [{ employee_id: purchaseMember, units }],
        }),
      })
      setPurchaseSource('')
    }, 'Purchase created. Price, settlement and share allocation require separate reviews.')
  }

  async function changeState(kind: 'payroll-batches' | 'purchase-cycles', id: string, state: string) {
    await perform(
      () => request(base + '/' + kind + '/' + encodeURIComponent(id), {
        method: 'PATCH', body: JSON.stringify({ state, reason: reviewReason.trim() }),
      }),
      id + ' advanced to ' + state + '.',
    )
  }

  if (tab !== 'Payroll batches' && tab !== 'Purchase cycles') return null
  return (
    <section className="section stock-workflow">
      <div className="section-heading">
        <h2>{tab === 'Payroll batches' ? 'Receive payroll batch' : 'Open share purchase cycle'}</h2>
        <span>Financial posting occurs only after a valid review state transition</span>
      </div>
      {error && <div className="error" role="alert">{error}</div>}
      {success && <div className="notice" role="status">{success}</div>}
      {tab === 'Payroll batches' ? (
        <form className="workflow-form" onSubmit={receivePayroll}>
          <label>Payroll period
            <input type="date" value={period} max={asOf} onChange={e => setPeriod(e.target.value)} required />
          </label>
          <label>Source reference
            <input value={payrollSource} minLength={5} maxLength={80} placeholder="PAY-2026-10-EXTRA" onChange={e => setPayrollSource(e.target.value)} required />
          </label>
          <label>Participant
            <select value={employee} onChange={e => setPayrollEmployee(e.target.value)} required>
              {activeMembers.map(m => <option key={m.employee_id} value={m.employee_id}>{m.display_name} ({m.employee_id})</option>)}
            </select>
          </label>
          <label>Employee payroll deduction (JPY)
            <input type="number" min={Number(plan.minimum_monthly_jpy)} max={Number(plan.maximum_monthly_jpy)} step="0.01" value={payrollAmount} onChange={e => setPayrollAmount(e.target.value)} required />
          </label>
          <button className="primary" type="submit" disabled={busy || !employee}>{busy ? 'Saving…' : 'Receive batch'}</button>
          <p className="panel-note">Employer incentives and election checks are computed by the NMR backend using the dated plan rules. Duplicate payroll periods are rejected.</p>
        </form>
      ) : (
        <form className="workflow-form" onSubmit={receivePurchase}>
          <label>Trade date
            <input type="date" max={asOf} value={tradeDate} onChange={e => setTradeDate(e.target.value)} required />
          </label>
          <label>Source reference
            <input value={purchaseSource} minLength={5} maxLength={80} placeholder="BUY-2026-11-EXTRA" onChange={e => setPurchaseSource(e.target.value)} required />
          </label>
          <label>Participant
            <select value={purchaseMember} onChange={e => setPurchaseEmployee(e.target.value)} required>
              {activeMembers.map(m => <option key={m.employee_id} value={m.employee_id}>{m.display_name} ({m.employee_id}) · available cash JPY {Number(m.cash_jpy).toLocaleString()}</option>)}
            </select>
          </label>
          <label>Unit price (JPY)
            <input type="number" min="0.01" step="0.01" value={unitPrice} onChange={e => setUnitPrice(e.target.value)} required />
          </label>
          <label>Units allocated
            <input type="number" min="0.000001" step="0.000001" value={units} onChange={e => setUnits(e.target.value)} required />
          </label>
          <div className="workflow-estimate"><span>Estimated purchase cost</span><strong>JPY {(Number(unitPrice) * Number(units)).toLocaleString('en-US')}</strong></div>
          <button className="primary" type="submit" disabled={busy || !purchaseMember}>{busy ? 'Saving…' : 'Create purchase cycle'}</button>
          <p className="panel-note">Unsettled purchases never change share balances. Cash and unit reconciliations are validated before allocation.</p>
        </form>
      )}
      <div className="workflow-reviews">
        <h3>Review and post</h3>
        <label>Review reason
          <input value={reviewReason} onChange={e => setReviewReason(e.target.value)} minLength={3} maxLength={200} />
        </label>
        {tab === 'Payroll batches' ? payrollBatches.filter(b => b.state === 'RECEIVED' || b.state === 'VALIDATED').map(batch => (
          <div className="workflow-review-row" key={batch.id}>
            <span><strong>{batch.source_reference}</strong><small>{batch.state}</small></span>
            <button type="button" disabled={busy || reviewReason.trim().length < 3}
              onClick={() => changeState('payroll-batches', batch.id, batch.state === 'RECEIVED' ? 'VALIDATED' : 'POSTED')}>
              {batch.state === 'RECEIVED' ? 'Validate' : 'Post cash'}
            </button>
          </div>
        )) : purchaseCycles.filter(c => ['CREATED','PRICED','SETTLED'].includes(c.state)).map(cycle => (
          <div className="workflow-review-row" key={cycle.id}>
            <span><strong>{cycle.id}</strong><small>{cycle.state}</small></span>
            <button type="button" disabled={busy || reviewReason.trim().length < 3}
              onClick={() => changeState('purchase-cycles', cycle.id,
                cycle.state === 'CREATED' ? 'PRICED' : cycle.state === 'PRICED' ? 'SETTLED' : 'ALLOCATED')}>
              {cycle.state === 'CREATED' ? 'Confirm price' : cycle.state === 'PRICED' ? 'Confirm settlement' : 'Allocate shares'}
            </button>
          </div>
        ))}
      </div>
    </section>
  )
}
