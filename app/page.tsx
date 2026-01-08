'use client'

import { useState, useRef, useEffect } from 'react'
import dynamic from 'next/dynamic'
import Papa from 'papaparse'

// Dynamically import Plotly to avoid SSR issues
const Plot = dynamic(() => import('react-plotly.js'), { 
  ssr: false,
  loading: () => <div>Loading chart...</div>
})

// Utility functions
const eur = (x: number, d: number = 0): string => {
  const n = isFinite(x) ? x : 0
  return '€' + n.toLocaleString(undefined, { minimumFractionDigits: d, maximumFractionDigits: d })
}

const pct = (x: number, d: number = 1): string => {
  const n = isFinite(x) ? x : 0
  return (n * 100).toFixed(d) + '%'
}

const num = (v: any): number => {
  if (v === null || v === undefined) return 0
  const s = String(v).replace(/,/g, '').trim()
  const n = parseFloat(s)
  return isFinite(n) ? n : 0
}

const str = (v: any): string => (v === null || v === undefined) ? '' : String(v)

const parseList = (s: string): number[] => {
  return s.split(',').map(x => x.trim()).filter(Boolean).map(x => parseFloat(x)).filter(x => isFinite(x) && x > 0 && x <= 1)
}

function percentile(arr: number[], p: number): number {
  const xs = arr.filter(x => isFinite(x)).slice().sort((a, b) => a - b)
  if (!xs.length) return 0
  const idx = (xs.length - 1) * p
  const lo = Math.floor(idx)
  const hi = Math.ceil(idx)
  if (lo === hi) return xs[lo]
  const w = idx - lo
  return xs[lo] * (1 - w) + xs[hi] * w
}

interface DashboardResult {
  periodStart: Date | null
  periodEnd: Date | null
  totalBill: number
  computePublicBaseline: number
  computeActualCost: number
  computeShareTotal: number
  observedDiscount: number
  currentCoverage: number
  addCoverage: number
  targetCoverage: number
  incrementalCommitmentOD: number
  affectedSliceTotalBill: number
  dailyX: string[]
  dailyNormY: number[]
  dailyVarY: number[]
  topSvcNames: string[]
  topSvcCosts: number[]
  ptRows: Array<{
    pt: number
    discToCustomer: number
    overallReduction: number
    monthlySavings: number
    annualSavings: number
  }>
  spotNet: number
  spotShareTotal: number
  spotShareCompute: number
  ec2BoxNet: number
  ecsNet: number
  fargateSpotNet: number
  spotDisc: number
  spotScenario: Array<{
    a: number
    savEC2: number
    overallEC2: number
    savECS: number
    overallECS: number
  }>
}

function computeDashboard(rows: any[], opts: {
  addCoverage: number
  spotDiscount: number
  passThrough: number[]
  computeCodes: string[]
}): DashboardResult {
  const col = {
    net: (r: any) => num(r['lineItem/NetUnblendedCost'] ?? r['lineItem/UnblendedCost']),
    publicOD: (r: any) => num(r['pricing/publicOnDemandCost']),
    lineType: (r: any) => str(r['lineItem/LineItemType'] ?? 'Unknown'),
    productCode: (r: any) => str(r['lineItem/ProductCode'] ?? 'Unknown'),
    usageType: (r: any) => str(r['lineItem/UsageType'] ?? ''),
    service: (r: any) => str(r['product/ProductName'] ?? r['lineItem/ProductCode'] ?? 'Unknown'),
    usageStart: (r: any) => str(r['lineItem/UsageStartDate'] ?? ''),
    billStart: (r: any) => str(r['bill/BillingPeriodStartDate'] ?? ''),
    billEnd: (r: any) => str(r['bill/BillingPeriodEndDate'] ?? '')
  }

  const bs = col.billStart(rows[0])
  const be = col.billEnd(rows[0])
  const periodStart = bs ? new Date(bs) : null
  const periodEnd = be ? new Date(be) : null
  const daysInMonth = (periodStart && periodEnd) ? Math.max(1, Math.round((periodEnd.getTime() - periodStart.getTime()) / (24 * 3600 * 1000))) : 30

  const fixedTypes = new Set(['SavingsPlanRecurringFee', 'RIFee', 'Fee', 'EdpDiscount', 'SavingsPlanNegation'])
  const dailyVar = new Map<string, number>()
  const serviceSpend = new Map<string, number>()

  const computeCodes = new Set(opts.computeCodes)
  const computeUsageLineTypes = new Set(['Usage', 'SavingsPlanCoveredUsage', 'SavingsPlanNegation'])

  let totalBill = 0
  let fixedMonthly = 0

  let computePublicBaseline = 0
  let computeActualCost = 0
  let coveredPublic = 0

  let spotNet = 0

  let ec2BoxNet = 0
  let ec2BoxPublic = 0

  const ecsCodes = new Set(['AmazonECS', 'AWSFargate'])
  let ecsNet = 0
  let ecsPublic = 0
  let fargateSpotNet = 0

  for (const r of rows) {
    const net = col.net(r)
    const pub = col.publicOD(r)
    const lt = col.lineType(r)
    const pc = col.productCode(r)
    const ut = col.usageType(r)
    const svc = col.service(r)

    totalBill += net
    serviceSpend.set(svc, (serviceSpend.get(svc) || 0) + net)

    const isFixed = fixedTypes.has(lt)
    if (isFixed) fixedMonthly += net
    else {
      const d = col.usageStart(r)
      const dtObj = d ? new Date(d) : null
      if (dtObj && !isNaN(dtObj.getTime())) {
        const key = dtObj.toISOString().slice(0, 10)
        dailyVar.set(key, (dailyVar.get(key) || 0) + net)
      }
    }

    if (computeCodes.has(pc) && computeUsageLineTypes.has(lt)) {
      computePublicBaseline += pub
      computeActualCost += net
      if (lt === 'SavingsPlanCoveredUsage') coveredPublic += pub
    }

    const isSpot = (ut.toLowerCase().includes('spotusage') || lt.toLowerCase().includes('spot'))
    if (isSpot) {
      spotNet += net
    }

    if (pc === 'AmazonEC2' && computeUsageLineTypes.has(lt) && ut.toLowerCase().includes('boxusage')) {
      ec2BoxNet += net
      ec2BoxPublic += pub
    }

    if (ecsCodes.has(pc) && computeUsageLineTypes.has(lt)) {
      ecsNet += net
      ecsPublic += pub
      if (ut.toLowerCase().includes('spotusage')) fargateSpotNet += net
    }
  }

  const computeShareTotal = totalBill > 0 ? (computeActualCost / totalBill) : 0
  const observedDiscount = computePublicBaseline > 0 ? (1 - (computeActualCost / computePublicBaseline)) : 0
  const currentCoverage = computePublicBaseline > 0 ? (coveredPublic / computePublicBaseline) : 0

  const addCoverage = Math.max(0, Math.min(1, opts.addCoverage))
  const targetCoverage = Math.min(1, currentCoverage + addCoverage)
  const incrementalCommitmentOD = computePublicBaseline * addCoverage
  const affectedSliceTotalBill = computeShareTotal * addCoverage

  let dates: string[] = []
  if (periodStart && periodEnd && !isNaN(periodStart.getTime()) && !isNaN(periodEnd.getTime())) {
    const d = new Date(periodStart)
    for (let i = 0; i < daysInMonth; i++) {
      dates.push(d.toISOString().slice(0, 10))
      d.setDate(d.getDate() + 1)
    }
  } else {
    dates = Array.from(dailyVar.keys()).sort()
  }
  const fixedPerDay = fixedMonthly / Math.max(1, dates.length)

  const dailyX: string[] = []
  const dailyNormY: number[] = []
  const dailyVarY: number[] = []
  for (const key of dates) {
    dailyX.push(key)
    const v = dailyVar.get(key) || 0
    dailyVarY.push(v)
    dailyNormY.push(v + fixedPerDay)
  }

  // Filter out Savings Plans related services
  const topServices = Array.from(serviceSpend.entries())
    .filter(([name]) => !name.toLowerCase().includes('savings plan'))
    .sort((a, b) => b[1] - a[1])
    .slice(0, 10)
  const topSvcNames = topServices.map(x => x[0])
  const topSvcCosts = topServices.map(x => x[1])

  const ptRows = opts.passThrough.map(pt => {
    const discToCustomer = observedDiscount * pt
    const overallReduction = affectedSliceTotalBill * discToCustomer
    const monthlySavings = totalBill * overallReduction
    const annualSavings = monthlySavings * 12
    return { pt, discToCustomer, overallReduction, monthlySavings, annualSavings }
  })

  const spotShareTotal = totalBill > 0 ? spotNet / totalBill : 0
  const spotShareCompute = computeActualCost > 0 ? spotNet / computeActualCost : 0

  const candidateEC2Box = (ec2BoxPublic > 0 ? ec2BoxPublic : ec2BoxNet)
  const candidateECS = (ecsPublic > 0 ? ecsPublic : ecsNet)

  const spotDisc = Math.max(0, Math.min(0.95, opts.spotDiscount))
  const adopt = [0.10, 0.15, 0.20, 0.30]
  const spotScenario = adopt.map(a => {
    const savEC2 = candidateEC2Box * a * spotDisc
    const savECS = candidateECS * a * spotDisc
    return {
      a,
      savEC2,
      overallEC2: totalBill > 0 ? savEC2 / totalBill : 0,
      savECS,
      overallECS: totalBill > 0 ? savECS / totalBill : 0
    }
  })

  return {
    periodStart, periodEnd,
    totalBill, computePublicBaseline, computeActualCost, computeShareTotal,
    observedDiscount, currentCoverage, addCoverage, targetCoverage,
    incrementalCommitmentOD, affectedSliceTotalBill,
    dailyX, dailyNormY, dailyVarY,
    topSvcNames, topSvcCosts,
    ptRows,
    spotNet, spotShareTotal, spotShareCompute,
    ec2BoxNet, ecsNet, fargateSpotNet,
    spotDisc, spotScenario
  }
}

type StatusKind = '' | 'ok' | 'bad'

export default function Home() {
  const [statusKind, setStatusKind] = useState<StatusKind>('')
  const [statusText, setStatusText] = useState('Upload a CUR CSV, then click "Compute scenarios".')
  const [fileName, setFileName] = useState('No file selected')
  const [addCoverage, setAddCoverage] = useState('0.30')
  const [spotDiscount, setSpotDiscount] = useState('0.60')
  const [passThrough, setPassThrough] = useState('0.3,0.4,0.5,0.6,0.7,0.8,1.0')
  const [result, setResult] = useState<DashboardResult | null>(null)
  const [generatedAt, setGeneratedAt] = useState('')
  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    setGeneratedAt('Loaded: ' + new Date().toISOString().slice(0, 16).replace('T', ' '))
  }, [])

  const handleFileChange = () => {
    const f = fileInputRef.current?.files?.[0]
    setFileName(f ? f.name : 'No file selected')
  }

  const handleCompute = () => {
    const f = fileInputRef.current?.files?.[0]
    if (!f) {
      setStatusKind('bad')
      setStatusText('Please select a CUR CSV file first.')
      return
    }

    const addCoverageNum = parseFloat(addCoverage)
    const spotDiscountNum = parseFloat(spotDiscount)
    const passThroughList = parseList(passThrough)

    if (!isFinite(addCoverageNum) || addCoverageNum < 0 || addCoverageNum > 1) {
      setStatusKind('bad')
      setStatusText('Additional SP coverage must be a number between 0 and 1 (e.g., 0.30).')
      return
    }
    if (!isFinite(spotDiscountNum) || spotDiscountNum < 0 || spotDiscountNum > 0.95) {
      setStatusKind('bad')
      setStatusText('Spot discount must be a number between 0 and 0.95 (e.g., 0.60).')
      return
    }
    if (!passThroughList.length) {
      setStatusKind('bad')
      setStatusText('Pass-through list must contain values in (0,1], e.g., 0.3,0.5,1.0')
      return
    }

    setStatusKind('')
    setStatusText('Parsing CSV… (large CURs may take a few seconds)')

    Papa.parse(f, {
      header: true,
      skipEmptyLines: true,
      worker: true,
      complete: (results) => {
        try {
          const rows = results.data || []
          if (!rows.length) {
            setStatusKind('bad')
            setStatusText('CSV parsed but contains no rows.')
            return
          }

          const res = computeDashboard(rows, {
            addCoverage: addCoverageNum,
            spotDiscount: spotDiscountNum,
            passThrough: passThroughList,
            computeCodes: ['AmazonEC2', 'AmazonECS', 'AWSFargate', 'AWSLambda']
          })

          setResult(res)
          setStatusKind('ok')
          setStatusText('Done. Scenarios computed successfully.')
        } catch (e) {
          console.error(e)
          setStatusKind('bad')
          setStatusText('Failed to compute dashboard. Check console for details.')
        }
      },
      error: (err) => {
        console.error(err)
        setStatusKind('bad')
        setStatusText('CSV parsing error. Check console for details.')
      }
    })
  }

  const kpis = result ? [
    ['Total monthly AWS bill', eur(result.totalBill, 2)],
    ['Compute OD baseline (SP-eligible)', eur(result.computePublicBaseline, 2)],
    ['Compute actual cost (SP-eligible)', eur(result.computeActualCost, 2)],
    ['Compute share of total bill', pct(result.computeShareTotal, 1)],
    ['Observed effective compute discount', pct(result.observedDiscount, 1)],
    ['Current SP coverage (OD-basis)', pct(result.currentCoverage, 1)],
    ['Proposed additional coverage', pct(result.addCoverage, 1)],
    ['Target coverage (OD-basis)', pct(result.targetCoverage, 1)],
    ['Incremental SP commitment (OD-equiv)', eur(result.incrementalCommitmentOD, 2)],
    ['Total-bill slice affected (compute share × add)', pct(result.affectedSliceTotalBill, 1)]
  ] : []

  const ps = result?.periodStart ? result.periodStart.toISOString().slice(0, 10) : 'n/a'
  const pe = result?.periodEnd ? result.periodEnd.toISOString().slice(0, 10) : 'n/a'

  const p95 = result ? percentile(result.dailyNormY.concat(result.dailyVarY), 0.95) : 0
  const ymax = Math.max(1, p95 * 1.25)

  const spotKpis = result ? [
    ['Spot spend (Net)', eur(result.spotNet, 2)],
    ['Spot share of total bill', pct(result.spotShareTotal, 2)],
    ['Spot share of compute', pct(result.spotShareCompute, 2)],
    ['EC2 instance-hours proxy (BoxUsage) — Net', eur(result.ec2BoxNet, 2)],
    ['ECS/Fargate — Net', eur(result.ecsNet, 2)],
    ['Fargate Spot — Net', eur(result.fargateSpotNet, 2)],
  ] : []

  return (
    <div className="wrap">
      <div className="title">
        <div>
          <h1>FinOps CUR Scenario Dashboard <span className="pill">Upload CUR CSV → See scenarios</span></h1>
          <div className="sub">Client-side only • Your CSV never leaves your browser</div>
        </div>
        <div className="sub">{generatedAt}</div>
      </div>

      <div className="card wide">
        <div className="row" style={{ justifyContent: 'space-between' }}>
          <div className="row">
            <input
              className="input"
              type="file"
              id="fileInput"
              ref={fileInputRef}
              accept=".csv"
              onChange={handleFileChange}
            />
            <button className="btn" onClick={handleCompute}>Compute scenarios</button>
            <span className="badge">{fileName}</span>
          </div>
          <div className="row">
            <label className="sub">Additional SP coverage</label>
            <input
              className="input"
              id="addCoverage"
              value={addCoverage}
              onChange={(e) => setAddCoverage(e.target.value)}
            />
            <label className="sub">Spot discount</label>
            <input
              className="input"
              id="spotDiscount"
              value={spotDiscount}
              onChange={(e) => setSpotDiscount(e.target.value)}
            />
            <label className="sub">Pass-through list</label>
            <input
              className="input"
              id="passThrough"
              value={passThrough}
              onChange={(e) => setPassThrough(e.target.value)}
              style={{ minWidth: '260px' }}
            />
          </div>
        </div>

        <div style={{ marginTop: '12px' }} className="status">
          <span className={`dot ${statusKind === 'ok' ? 'ok' : statusKind === 'bad' ? 'bad' : ''}`}></span>
          <span>{statusText}</span>
        </div>

        <div className="note" style={{ marginTop: '10px' }}>
          <b>Expected CUR columns:</b> lineItem/NetUnblendedCost (or UnblendedCost), pricing/publicOnDemandCost (optional),
          lineItem/UsageStartDate, bill/BillingPeriodStartDate, bill/BillingPeriodEndDate,
          lineItem/LineItemType, lineItem/ProductCode, lineItem/UsageType (optional), product/ProductName (optional).
        </div>
      </div>

      {result && (
        <>
          <div className="grid" style={{ marginTop: '14px' }}>
            {kpis.map(([k, v], i) => (
              <div key={i} className="card kpi">
                <div className="k">{k}</div>
                <div className="v">{v}</div>
              </div>
            ))}
          </div>

          <div className="grid" style={{ marginTop: '14px' }}>
            <div className="card wide note">
              <b>SP sizing logic (CUR-backed):</b>
              Compute universe = ProductCode ∈ {'{AmazonEC2, AmazonECS, AWSFargate, AWSLambda}'} and LineItemType ∈ Usage / SavingsPlanCoveredUsage / SavingsPlanNegation.
              Underwriting baseline uses <code>pricing/publicOnDemandCost</code>.
              Current SP coverage = OD-baseline of SavingsPlanCoveredUsage ÷ OD-baseline of total compute usage.
              <br /><br />
              <b>Incremental +{Math.round(result.addCoverage * 100)}% coverage:</b>
              {' '}commitment sized as {pct(result.addCoverage, 1)} × compute OD baseline (= {eur(result.incrementalCommitmentOD, 2)}).
              Only {pct(result.affectedSliceTotalBill, 1)} of the total bill is affected by this incremental move (compute share × additional coverage).
              <br /><br />
              <span className="badge">Input: {fileName}</span> <span className="badge">Billing period: {ps} → {pe}</span>
            </div>
          </div>

          <div className="grid" style={{ marginTop: '14px' }}>
            <div className="card wide">
              {result && (
                <Plot
                  data={[
                    { x: result.dailyX, y: result.dailyNormY, type: 'scatter', mode: 'lines', name: 'Normalized daily spend' },
                    { x: result.dailyX, y: result.dailyVarY, type: 'scatter', mode: 'lines', name: 'Variable usage only', line: { dash: 'dot' } }
                  ]}
                  layout={{
                    title: 'Normalized Daily Spend (Run-rate view)',
                    height: 360,
                    margin: { l: 50, r: 20, t: 55, b: 45 },
                    template: 'plotly_white',
                    yaxis: { range: [0, ymax], title: '€ / day (clipped view)' }
                  }}
                  config={{ displayModeBar: false }}
                />
              )}
              <div className="note" style={{ marginTop: '8px' }}>
                Chart uses a <b>clipped Y-axis</b> (p95×1.25) to keep the daily run-rate readable and avoid one-off postings dominating the view.
              </div>
            </div>

            <div className="card wide" style={{ display: 'flex', justifyContent: 'center' }}>
              {result && (
                <div style={{ width: '100%', maxWidth: '1000px', margin: '0 auto' }}>
                  <Plot
                    data={[{
                      x: result.topSvcCosts,
                      y: result.topSvcNames,
                      type: 'bar',
                      orientation: 'h',
                      name: 'Net cost',
                      marker: { color: '#1d4ed8' }
                    }]}
                    layout={{
                      title: {
                        text: 'Top 10 services by Net cost',
                        x: 0.5,
                        xanchor: 'center'
                      },
                      height: 420,
                      margin: { l: 250, r: 50, t: 55, b: 45 },
                      template: 'plotly_white',
                      xaxis: {
                        title: 'Net Cost (€)',
                        showgrid: true
                      },
                      yaxis: {
                        title: '',
                        showgrid: false,
                        automargin: true
                      },
                      showlegend: false
                    }}
                    config={{ displayModeBar: false }}
                    style={{ width: '100%', height: '100%' }}
                  />
                </div>
              )}
            </div>

            <div className="card wide">
              <div className="section-title">Pass-through impact table (incremental slice only)</div>
              <div className="note" style={{ marginBottom: '10px' }}>
                Discount proxy = observed effective compute discount ({pct(result.observedDiscount, 1)}). Incremental slice affected = {pct(result.affectedSliceTotalBill, 1)} of total bill.
              </div>
              <div style={{ overflow: 'auto' }}>
                <table>
                  <thead>
                    <tr>
                      <th>Pass-through</th>
                      <th style={{ textAlign: 'right' }}>Discount to customer (on +slice)</th>
                      <th style={{ textAlign: 'right' }}>Overall bill reduction</th>
                      <th style={{ textAlign: 'right' }}>Monthly € savings</th>
                      <th style={{ textAlign: 'right' }}>Annual € savings</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.ptRows.map((r, i) => (
                      <tr key={i}>
                        <td>{Math.round(r.pt * 100)}%</td>
                        <td style={{ textAlign: 'right' }}>{pct(r.discToCustomer, 1)}</td>
                        <td style={{ textAlign: 'right' }}>{pct(r.overallReduction, 2)}</td>
                        <td style={{ textAlign: 'right' }}>{eur(r.monthlySavings, 0)}</td>
                        <td style={{ textAlign: 'right' }}>{eur(r.annualSavings, 0)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="note" style={{ marginTop: '10px' }}>
                Note: This reflects only incremental SP economics (no RDS/logging/storage changes assumed).
              </div>
            </div>

            <div className="card wide"><hr /></div>

            <div className="card wide">
              <div className="section-title">Spot analysis (CUR-backed)</div>
              <div className="note" style={{ marginBottom: '10px' }}>
                Spot detected via <code>lineItem/UsageType</code> containing <code>SpotUsage</code> (plus Spot-like lineItem types). Current Spot share of compute is <b>{pct(result.spotShareCompute, 2)}</b>.
              </div>
              <div className="grid" style={{ gap: '14px' }}>
                {spotKpis.map(([k, v], i) => (
                  <div key={i} className="card" style={{ gridColumn: 'span 4' }}>
                    <div className="note">{k}</div>
                    <div style={{ fontSize: '22px', fontWeight: 800 }}>{v}</div>
                  </div>
                ))}
              </div>
            </div>

            <div className="card wide">
              <div className="section-title">
                Spot adoption scenarios (conservative {Math.round(result.spotDisc * 100)}% Spot discount)
              </div>
              <div className="note" style={{ marginBottom: '10px' }}>
                Savings computed from CUR baselines: EC2 uses the BoxUsage pool; ECS/Fargate uses its pool.
                Treat Spot as upside (best-effort), not contractual.
              </div>
              <div style={{ overflow: 'auto' }}>
                <table>
                  <thead>
                    <tr>
                      <th>Shift to Spot</th>
                      <th style={{ textAlign: 'right' }}>EC2 BoxUsage savings /mo</th>
                      <th style={{ textAlign: 'right' }}>EC2 overall bill ↓</th>
                      <th style={{ textAlign: 'right' }}>ECS/Fargate savings /mo</th>
                      <th style={{ textAlign: 'right' }}>ECS/Fargate overall bill ↓</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.spotScenario.map((s, i) => (
                      <tr key={i}>
                        <td>{Math.round(s.a * 100)}%</td>
                        <td style={{ textAlign: 'right' }}>{eur(s.savEC2, 0)}</td>
                        <td style={{ textAlign: 'right' }}>{pct(s.overallEC2, 2)}</td>
                        <td style={{ textAlign: 'right' }}>{eur(s.savECS, 0)}</td>
                        <td style={{ textAlign: 'right' }}>{pct(s.overallECS, 2)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="note" style={{ marginTop: '10px' }}>
                Practical policy: keep baseline on Savings Plans / On-Demand; use Spot for overflow + stateless workers with fallback capacity.
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  )
}

