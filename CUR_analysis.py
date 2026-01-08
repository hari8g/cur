#!/usr/bin/env python
# coding: utf-8

# In[ ]:


"""
Generate a SINGLE-PAGE HTML (no server) that lets you UPLOAD an AWS CUR CSV in the browser,
then computes & renders the scenarios (SP + Spot) with the UX changes you requested:

✅ Changes implemented
1) Normalized Daily Spend chart shows a "daily run-rate" view WITHOUT the ~40k spike:
   - We CLIP the Y-axis to a robust range (95th percentile * 1.25) so outlier postings don't dominate.
   - (We keep the real values in computation; we just make the chart readable.)
2) "Top 10 services by Net cost" moved BELOW the daily chart in a separate container.
3) Removed the "Savings Plan coverage move" chart completely.
4) Removed "Spot spend by ProductCode" chart completely.
5) Removed "Bosch retained discount" column from the pass-through table.

How to use:
  1) python make_finops_cur_dashboard_html_v2.py
  2) Open the generated HTML file in Chrome/Edge
  3) Upload your CUR CSV → dashboard renders instantly

Your CSV never leaves the browser.
"""

from pathlib import Path

OUT_HTML = Path("finops_cur_scenario_dashboard_v2.html")

html = r"""<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>FinOps CUR Scenario Dashboard</title>

  <!-- CSV parsing + charts -->
  <script src="https://cdn.jsdelivr.net/npm/papaparse@5.4.1/papaparse.min.js"></script>
  <script src="https://cdn.plot.ly/plotly-2.30.0.min.js"></script>

  <style>
    :root{
      --bg:#ffffff;
      --card:#ffffff;
      --stroke:rgba(15,23,42,0.14);
      --text:rgba(2,6,23,0.92);
      --muted:rgba(2,6,23,0.62);
      --accent:#1d4ed8;
      --good:#16a34a;
      --warn:#f59e0b;
      --bad:#dc2626;
    }
    body{
      margin:0;
      font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial;
      background:var(--bg);
      color:var(--text);
    }
    .wrap{max-width:1200px;margin:0 auto;padding:22px;}
    .title{display:flex;justify-content:space-between;align-items:flex-end;gap:16px;margin-bottom:14px;}
    h1{margin:0;font-size:20px;}
    .sub{color:var(--muted);font-size:12.5px;}
    .pill{
      display:inline-block;padding:2px 10px;border-radius:999px;
      border:1px solid rgba(29,78,216,0.25);
      color:var(--accent);font-size:12px;margin-left:8px;
    }
    .grid{display:grid;grid-template-columns:repeat(12,1fr);gap:14px;}
    .card{
      background:var(--card);
      border:1px solid var(--stroke);
      border-radius:14px;
      padding:14px;
      box-shadow:0 8px 24px rgba(15,23,42,0.06);
    }
    .kpi{grid-column:span 3;}
    .kpi .k{font-size:12px;color:var(--muted);margin-bottom:6px;}
    .kpi .v{font-size:20px;font-weight:750;}
    .wide{grid-column:span 12;}
    .note{color:var(--muted);font-size:13px;line-height:1.45;}
    .section-title{font-weight:800;font-size:14px;margin:0 0 8px 0;}
    table{width:100%;border-collapse:collapse;font-size:13px;}
    th,td{border-bottom:1px solid rgba(15,23,42,0.10);padding:8px 6px;}
    th{color:var(--muted);font-weight:700;text-align:left;position:sticky;top:0;background:rgba(248,250,252,0.95);}
    hr{border:none;border-top:1px solid rgba(15,23,42,0.10);margin:0;}
    .row{display:flex;gap:10px;flex-wrap:wrap;align-items:center}
    .btn{
      border:1px solid rgba(15,23,42,0.18);
      background:#fff;
      padding:8px 10px;border-radius:10px;
      cursor:pointer;
      font-weight:650;
    }
    .btn:hover{border-color:rgba(29,78,216,0.45)}
    .input{
      border:1px solid rgba(15,23,42,0.18);
      border-radius:10px;
      padding:8px 10px;
      min-width:160px;
      font-size:13px;
    }
    .badge{
      display:inline-block;
      padding:2px 8px;border-radius:999px;
      font-size:12px;
      border:1px solid rgba(15,23,42,0.14);
      background:rgba(248,250,252,0.9);
      color:rgba(2,6,23,0.72);
    }
    .status{
      display:flex;align-items:center;gap:10px;
      padding:10px 12px;border-radius:12px;
      border:1px solid rgba(15,23,42,0.12);
      background:rgba(248,250,252,0.7);
      color:rgba(2,6,23,0.8);
      font-size:13px;
    }
    .dot{width:10px;height:10px;border-radius:999px;background:var(--warn);}
    .dot.ok{background:var(--good);}
    .dot.bad{background:var(--bad);}
    @media (max-width:980px){.kpi{grid-column:span 12;}}
  </style>
</head>

<body>
  <div class="wrap">
    <div class="title">
      <div>
        <h1>FinOps CUR Scenario Dashboard <span class="pill">Upload CUR CSV → See scenarios</span></h1>
        <div class="sub">Client-side only • Your CSV never leaves your browser</div>
      </div>
      <div class="sub" id="generatedAt"></div>
    </div>

    <div class="card wide">
      <div class="row" style="justify-content:space-between;">
        <div class="row">
          <input class="input" type="file" id="fileInput" accept=".csv" />
          <button class="btn" id="runBtn">Compute scenarios</button>
          <span class="badge" id="fileName">No file selected</span>
        </div>
        <div class="row">
          <label class="sub">Additional SP coverage</label>
          <input class="input" id="addCoverage" value="0.30" />
          <label class="sub">Spot discount</label>
          <input class="input" id="spotDiscount" value="0.60" />
          <label class="sub">Pass-through list</label>
          <input class="input" id="passThrough" value="0.3,0.4,0.5,0.6,0.7,0.8,1.0" style="min-width:260px"/>
        </div>
      </div>

      <div style="margin-top:12px" class="status">
        <span class="dot" id="statusDot"></span>
        <span id="statusText">Upload a CUR CSV, then click “Compute scenarios”.</span>
      </div>

      <div class="note" style="margin-top:10px">
        <b>Expected CUR columns:</b> lineItem/NetUnblendedCost (or UnblendedCost), pricing/publicOnDemandCost (optional),
        lineItem/UsageStartDate, bill/BillingPeriodStartDate, bill/BillingPeriodEndDate,
        lineItem/LineItemType, lineItem/ProductCode, lineItem/UsageType (optional), product/ProductName (optional).
      </div>
    </div>

    <!-- KPIs -->
    <div class="grid" id="kpiGrid" style="margin-top:14px; display:none;"></div>

    <!-- Explanations -->
    <div class="grid" id="infoGrid" style="margin-top:14px; display:none;">
      <div class="card wide note" id="spExplain"></div>
    </div>

    <!-- Charts -->
    <div class="grid" id="chartsGrid" style="margin-top:14px; display:none;">
      <!-- 1) DAILY chart (full width) -->
      <div class="card wide">
        <div id="chartDaily"></div>
        <div class="note" id="dailyNote" style="margin-top:8px;"></div>
      </div>

      <!-- 2) TOP services BELOW daily chart (full width, separate container) -->
      <div class="card wide">
        <div id="chartTop"></div>
      </div>

      <!-- Pass-through table -->
      <div class="card wide" id="ptCard">
        <div class="section-title">Pass-through impact table (incremental slice only)</div>
        <div class="note" id="ptNote" style="margin-bottom:10px;"></div>
        <div style="overflow:auto">
          <table>
            <thead>
              <tr>
                <th>Pass-through</th>
                <th style="text-align:right">Discount to customer (on +slice)</th>
                <th style="text-align:right">Overall bill reduction</th>
                <th style="text-align:right">Monthly € savings</th>
                <th style="text-align:right">Annual € savings</th>
              </tr>
            </thead>
            <tbody id="ptBody"></tbody>
          </table>
        </div>
        <div class="note" style="margin-top:10px">
          Note: This reflects only incremental SP economics (no RDS/logging/storage changes assumed).
        </div>
      </div>

      <div class="card wide"><hr/></div>

      <!-- Spot analysis -->
      <div class="card wide">
        <div class="section-title">Spot analysis (CUR-backed)</div>
        <div class="note" id="spotNote" style="margin-bottom:10px;"></div>
        <div class="grid" style="gap:14px" id="spotKpiGrid"></div>
      </div>

      <!-- Spot scenarios table ONLY (no spot by product code chart) -->
      <div class="card wide">
        <div class="section-title" id="spotScTitle"></div>
        <div class="note" style="margin-bottom:10px">
          Savings computed from CUR baselines: EC2 uses the BoxUsage pool; ECS/Fargate uses its pool.
          Treat Spot as upside (best-effort), not contractual.
        </div>
        <div style="overflow:auto">
          <table>
            <thead>
              <tr>
                <th>Shift to Spot</th>
                <th style="text-align:right">EC2 BoxUsage savings /mo</th>
                <th style="text-align:right">EC2 overall bill ↓</th>
                <th style="text-align:right">ECS/Fargate savings /mo</th>
                <th style="text-align:right">ECS/Fargate overall bill ↓</th>
              </tr>
            </thead>
            <tbody id="spotBody"></tbody>
          </table>
        </div>
        <div class="note" style="margin-top:10px">
          Practical policy: keep baseline on Savings Plans / On-Demand; use Spot for overflow + stateless workers with fallback capacity.
        </div>
      </div>
    </div>
  </div>

<script>
  // -----------------------------
  // Utilities
  // -----------------------------
  const eur = (x, d=0) => {
    const n = (isFinite(x) ? x : 0);
    return "€" + n.toLocaleString(undefined, {minimumFractionDigits:d, maximumFractionDigits:d});
  };
  const pct = (x, d=1) => {
    const n = (isFinite(x) ? x : 0);
    return (n*100).toFixed(d) + "%";
  };
  const num = (v) => {
    if (v === null || v === undefined) return 0;
    const s = String(v).replace(/,/g,"").trim();
    const n = parseFloat(s);
    return isFinite(n) ? n : 0;
  };
  const str = (v) => (v === null || v === undefined) ? "" : String(v);

  const setStatus = (kind, msg) => {
    const dot = document.getElementById("statusDot");
    dot.classList.remove("ok","bad");
    if (kind === "ok") dot.classList.add("ok");
    if (kind === "bad") dot.classList.add("bad");
    document.getElementById("statusText").textContent = msg;
  };

  const parseList = (s) => s.split(",").map(x=>x.trim()).filter(Boolean).map(x=>parseFloat(x)).filter(x=>isFinite(x) && x>0 && x<=1);

  // Percentile helper (robust y-axis clipping)
  function percentile(arr, p){
    const xs = arr.filter(x=>isFinite(x)).slice().sort((a,b)=>a-b);
    if (!xs.length) return 0;
    const idx = (xs.length-1) * p;
    const lo = Math.floor(idx), hi = Math.ceil(idx);
    if (lo === hi) return xs[lo];
    const w = idx - lo;
    return xs[lo]*(1-w) + xs[hi]*w;
  }

  // -----------------------------
  // Core computation
  // -----------------------------
  function computeDashboard(rows, opts){
    const col = {
      net: (r)=> num(r["lineItem/NetUnblendedCost"] ?? r["lineItem/UnblendedCost"]),
      publicOD: (r)=> num(r["pricing/publicOnDemandCost"]),
      lineType: (r)=> str(r["lineItem/LineItemType"] ?? "Unknown"),
      productCode: (r)=> str(r["lineItem/ProductCode"] ?? "Unknown"),
      usageType: (r)=> str(r["lineItem/UsageType"] ?? ""),
      service: (r)=> str(r["product/ProductName"] ?? r["lineItem/ProductCode"] ?? "Unknown"),
      usageStart: (r)=> str(r["lineItem/UsageStartDate"] ?? ""),
      billStart: (r)=> str(r["bill/BillingPeriodStartDate"] ?? ""),
      billEnd: (r)=> str(r["bill/BillingPeriodEndDate"] ?? "")
    };

    const bs = col.billStart(rows[0]);
    const be = col.billEnd(rows[0]);
    const periodStart = bs ? new Date(bs) : null;
    const periodEnd = be ? new Date(be) : null;
    const daysInMonth = (periodStart && periodEnd) ? Math.max(1, Math.round((periodEnd - periodStart)/(24*3600*1000))) : 30;

    const fixedTypes = new Set(["SavingsPlanRecurringFee","RIFee","Fee","EdpDiscount","SavingsPlanNegation"]);
    const dailyVar = new Map();
    const serviceSpend = new Map();

    const computeCodes = new Set(opts.computeCodes);
    const computeUsageLineTypes = new Set(["Usage","SavingsPlanCoveredUsage","SavingsPlanNegation"]);

    let totalBill = 0;
    let fixedMonthly = 0;

    let computePublicBaseline = 0;
    let computeActualCost = 0;
    let coveredPublic = 0;

    // Spot (only for KPIs/scenarios)
    let spotNet = 0;

    // EC2 BoxUsage proxy
    let ec2BoxNet = 0;
    let ec2BoxPublic = 0;

    // ECS/Fargate pool
    const ecsCodes = new Set(["AmazonECS","AWSFargate"]);
    let ecsNet = 0;
    let ecsPublic = 0;
    let fargateSpotNet = 0;

    for (const r of rows){
      const net = col.net(r);
      const pub = col.publicOD(r);
      const lt = col.lineType(r);
      const pc = col.productCode(r);
      const ut = col.usageType(r);
      const svc = col.service(r);

      totalBill += net;
      serviceSpend.set(svc, (serviceSpend.get(svc)||0) + net);

      const isFixed = fixedTypes.has(lt);
      if (isFixed) fixedMonthly += net;
      else{
        const d = col.usageStart(r);
        const dtObj = d ? new Date(d) : null;
        if (dtObj && !isNaN(dtObj.getTime())){
          const key = dtObj.toISOString().slice(0,10);
          dailyVar.set(key, (dailyVar.get(key)||0) + net);
        }
      }

      if (computeCodes.has(pc) && computeUsageLineTypes.has(lt)){
        computePublicBaseline += pub;
        computeActualCost += net;
        if (lt === "SavingsPlanCoveredUsage") coveredPublic += pub;
      }

      const isSpot = (ut.toLowerCase().includes("spotusage") || lt.toLowerCase().includes("spot"));
      if (isSpot){
        spotNet += net;
      }

      if (pc === "AmazonEC2" && computeUsageLineTypes.has(lt) && ut.toLowerCase().includes("boxusage")){
        ec2BoxNet += net;
        ec2BoxPublic += pub;
      }

      if (ecsCodes.has(pc) && computeUsageLineTypes.has(lt)){
        ecsNet += net;
        ecsPublic += pub;
        if (ut.toLowerCase().includes("spotusage")) fargateSpotNet += net;
      }
    }

    const computeShareTotal = totalBill > 0 ? (computeActualCost / totalBill) : 0;
    const observedDiscount = computePublicBaseline > 0 ? (1 - (computeActualCost / computePublicBaseline)) : 0;
    const currentCoverage = computePublicBaseline > 0 ? (coveredPublic / computePublicBaseline) : 0;

    const addCoverage = Math.max(0, Math.min(1, opts.addCoverage));
    const targetCoverage = Math.min(1, currentCoverage + addCoverage);
    const incrementalCommitmentOD = computePublicBaseline * addCoverage;
    const affectedSliceTotalBill = computeShareTotal * addCoverage;

    // build normalized daily series
    let dates = [];
    if (periodStart && periodEnd && !isNaN(periodStart.getTime()) && !isNaN(periodEnd.getTime())){
      const d = new Date(periodStart);
      for (let i=0;i<daysInMonth;i++){
        dates.push(d.toISOString().slice(0,10));
        d.setDate(d.getDate()+1);
      }
    } else {
      dates = Array.from(dailyVar.keys()).sort();
    }
    const fixedPerDay = fixedMonthly / Math.max(1, dates.length);

    const dailyX = [];
    const dailyNormY = [];
    const dailyVarY = [];
    for (const key of dates){
      dailyX.push(key);
      const v = dailyVar.get(key)||0;
      dailyVarY.push(v);
      dailyNormY.push(v + fixedPerDay);
    }

    // top services
    const topServices = Array.from(serviceSpend.entries()).sort((a,b)=>b[1]-a[1]).slice(0,10);
    const topSvcNames = topServices.map(x=>x[0]);
    const topSvcCosts = topServices.map(x=>x[1]);

    // pass-through table
    const ptRows = opts.passThrough.map(pt=>{
      const discToCustomer = observedDiscount * pt;
      const overallReduction = affectedSliceTotalBill * discToCustomer;
      const monthlySavings = totalBill * overallReduction;
      const annualSavings = monthlySavings * 12;
      return {pt, discToCustomer, overallReduction, monthlySavings, annualSavings};
    });

    // spot KPIs + scenario
    const spotShareTotal = totalBill>0 ? spotNet/totalBill : 0;
    const spotShareCompute = computeActualCost>0 ? spotNet/computeActualCost : 0;

    const candidateEC2Box = (ec2BoxPublic>0 ? ec2BoxPublic : ec2BoxNet);
    const candidateECS = (ecsPublic>0 ? ecsPublic : ecsNet);

    const spotDisc = Math.max(0, Math.min(0.95, opts.spotDiscount));
    const adopt = [0.10,0.15,0.20,0.30];
    const spotScenario = adopt.map(a=>{
      const savEC2 = candidateEC2Box * a * spotDisc;
      const savECS = candidateECS * a * spotDisc;
      return {
        a,
        savEC2,
        overallEC2: totalBill>0 ? savEC2/totalBill : 0,
        savECS,
        overallECS: totalBill>0 ? savECS/totalBill : 0
      };
    });

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
    };
  }

  // -----------------------------
  // Rendering
  // -----------------------------
  function renderAll(res, fileName){
    document.getElementById("kpiGrid").style.display = "";
    document.getElementById("infoGrid").style.display = "";
    document.getElementById("chartsGrid").style.display = "";

    // KPIs
    const kpis = [
      ["Total monthly AWS bill", eur(res.totalBill, 2)],
      ["Compute OD baseline (SP-eligible)", eur(res.computePublicBaseline, 2)],
      ["Compute actual cost (SP-eligible)", eur(res.computeActualCost, 2)],
      ["Compute share of total bill", pct(res.computeShareTotal, 1)],
      ["Observed effective compute discount", pct(res.observedDiscount, 1)],
      ["Current SP coverage (OD-basis)", pct(res.currentCoverage, 1)],
      ["Proposed additional coverage", pct(res.addCoverage, 1)],
      ["Target coverage (OD-basis)", pct(res.targetCoverage, 1)],
      ["Incremental SP commitment (OD-equiv)", eur(res.incrementalCommitmentOD, 2)],
      ["Total-bill slice affected (compute share × add)", pct(res.affectedSliceTotalBill, 1)]
    ];

    document.getElementById("kpiGrid").innerHTML = kpis.map(([k,v]) =>
      `<div class="card kpi"><div class="k">${k}</div><div class="v">${v}</div></div>`
    ).join("");

    // SP explanation
    const ps = res.periodStart ? res.periodStart.toISOString().slice(0,10) : "n/a";
    const pe = res.periodEnd ? res.periodEnd.toISOString().slice(0,10) : "n/a";
    document.getElementById("spExplain").innerHTML = `
      <b>SP sizing logic (CUR-backed):</b>
      Compute universe = ProductCode ∈ {AmazonEC2, AmazonECS, AWSFargate, AWSLambda} and LineItemType ∈ Usage / SavingsPlanCoveredUsage / SavingsPlanNegation.
      Underwriting baseline uses <code>pricing/publicOnDemandCost</code>.
      Current SP coverage = OD-baseline of SavingsPlanCoveredUsage ÷ OD-baseline of total compute usage.
      <br/><br/>
      <b>Incremental +${Math.round(res.addCoverage*100)}% coverage:</b>
      commitment sized as ${pct(res.addCoverage,1)} × compute OD baseline (= ${eur(res.incrementalCommitmentOD,2)}).
      Only ${pct(res.affectedSliceTotalBill,1)} of the total bill is affected by this incremental move (compute share × additional coverage).
      <br/><br/>
      <span class="badge">Input: ${fileName}</span> <span class="badge">Billing period: ${ps} → ${pe}</span>
    `;

    // NORMALIZED daily chart — clip y-axis so outlier postings (e.g., day-1) don't dominate
    const p95 = percentile(res.dailyNormY.concat(res.dailyVarY), 0.95);
    const ymax = Math.max(1, p95 * 1.25);

    Plotly.newPlot("chartDaily", [
      {x: res.dailyX, y: res.dailyNormY, type:"scatter", mode:"lines", name:"Normalized daily spend"},
      {x: res.dailyX, y: res.dailyVarY, type:"scatter", mode:"lines", name:"Variable usage only", line:{dash:"dot"}}
    ], {
      title:"Normalized Daily Spend (Run-rate view)",
      height:360, margin:{l:50,r:20,t:55,b:45},
      template:"plotly_white",
      yaxis:{range:[0, ymax], title:"€ / day (clipped view)"}
    }, {displayModeBar:false});

    document.getElementById("dailyNote").innerHTML =
      `Chart uses a <b>clipped Y-axis</b> (p95×1.25) to keep the daily run-rate readable and avoid one-off postings dominating the view.`;

    // Top services chart (now below daily, full width)
    Plotly.newPlot("chartTop", [{
      x: res.topSvcCosts,
      y: res.topSvcNames,
      type:"bar",
      orientation:"h",
      name:"Net cost"
    }], {
      title:"Top 10 services by Net cost",
      height:420, margin:{l:220,r:20,t:55,b:45},
      template:"plotly_white"
    }, {displayModeBar:false});

    // Pass-through table (removed Bosch retained discount)
    document.getElementById("ptNote").textContent =
      `Discount proxy = observed effective compute discount (${pct(res.observedDiscount,1)}). Incremental slice affected = ${pct(res.affectedSliceTotalBill,1)} of total bill.`;

    document.getElementById("ptBody").innerHTML = res.ptRows.map(r => `
      <tr>
        <td>${Math.round(r.pt*100)}%</td>
        <td style="text-align:right">${pct(r.discToCustomer,1)}</td>
        <td style="text-align:right">${pct(r.overallReduction,2)}</td>
        <td style="text-align:right">${eur(r.monthlySavings,0)}</td>
        <td style="text-align:right">${eur(r.annualSavings,0)}</td>
      </tr>
    `).join("");

    // Spot KPIs + note (no spot-by-product chart)
    document.getElementById("spotNote").innerHTML =
      `Spot detected via <code>lineItem/UsageType</code> containing <code>SpotUsage</code> (plus Spot-like lineItem types). Current Spot share of compute is <b>${pct(res.spotShareCompute,2)}</b>.`;

    const spotKpis = [
      ["Spot spend (Net)", eur(res.spotNet,2)],
      ["Spot share of total bill", pct(res.spotShareTotal,2)],
      ["Spot share of compute", pct(res.spotShareCompute,2)],
      ["EC2 instance-hours proxy (BoxUsage) — Net", eur(res.ec2BoxNet,2)],
      ["ECS/Fargate — Net", eur(res.ecsNet,2)],
      ["Fargate Spot — Net", eur(res.fargateSpotNet,2)],
    ];
    document.getElementById("spotKpiGrid").innerHTML = spotKpis.map(([k,v]) =>
      `<div class="card third"><div class="note">${k}</div><div style="font-size:22px;font-weight:800">${v}</div></div>`
    ).join("");

    // Spot scenarios table
    document.getElementById("spotScTitle").textContent =
      `Spot adoption scenarios (conservative ${Math.round(res.spotDisc*100)}% Spot discount)`;

    document.getElementById("spotBody").innerHTML = res.spotScenario.map(s => `
      <tr>
        <td>${Math.round(s.a*100)}%</td>
        <td style="text-align:right">${eur(s.savEC2,0)}</td>
        <td style="text-align:right">${pct(s.overallEC2,2)}</td>
        <td style="text-align:right">${eur(s.savECS,0)}</td>
        <td style="text-align:right">${pct(s.overallECS,2)}</td>
      </tr>
    `).join("");
  }

  // -----------------------------
  // Event wiring
  // -----------------------------
  document.getElementById("generatedAt").textContent = "Loaded: " + new Date().toISOString().slice(0,16).replace("T"," ");

  const fileInput = document.getElementById("fileInput");
  const runBtn = document.getElementById("runBtn");

  fileInput.addEventListener("change", () => {
    const f = fileInput.files && fileInput.files[0];
    document.getElementById("fileName").textContent = f ? f.name : "No file selected";
  });

  runBtn.addEventListener("click", () => {
    const f = fileInput.files && fileInput.files[0];
    if (!f){
      setStatus("bad", "Please select a CUR CSV file first.");
      return;
    }

    const addCoverage = parseFloat(document.getElementById("addCoverage").value);
    const spotDiscount = parseFloat(document.getElementById("spotDiscount").value);
    const passThrough = parseList(document.getElementById("passThrough").value);

    if (!isFinite(addCoverage) || addCoverage < 0 || addCoverage > 1){
      setStatus("bad", "Additional SP coverage must be a number between 0 and 1 (e.g., 0.30).");
      return;
    }
    if (!isFinite(spotDiscount) || spotDiscount < 0 || spotDiscount > 0.95){
      setStatus("bad", "Spot discount must be a number between 0 and 0.95 (e.g., 0.60).");
      return;
    }
    if (!passThrough.length){
      setStatus("bad", "Pass-through list must contain values in (0,1], e.g., 0.3,0.5,1.0");
      return;
    }

    setStatus("", "Parsing CSV… (large CURs may take a few seconds)");
    Papa.parse(f, {
      header: true,
      skipEmptyLines: true,
      worker: true,
      complete: (results) => {
        try{
          const rows = results.data || [];
          if (!rows.length){
            setStatus("bad", "CSV parsed but contains no rows.");
            return;
          }

          const res = computeDashboard(rows, {
            addCoverage,
            spotDiscount,
            passThrough,
            computeCodes: ["AmazonEC2","AmazonECS","AWSFargate","AWSLambda"]
          });

          renderAll(res, f.name);
          setStatus("ok", "Done. Scenarios computed successfully.");
        } catch (e){
          console.error(e);
          setStatus("bad", "Failed to compute dashboard. Check console for details.");
        }
      },
      error: (err) => {
        console.error(err);
        setStatus("bad", "CSV parsing error. Check console for details.");
      }
    });
  });
</script>
</body>
</html>
"""

OUT_HTML.write_text(html, encoding="utf-8")
print(f"✅ Generated: {OUT_HTML.resolve()}")

