# FinOps CUR Scenario Dashboard

A Next.js application for analyzing AWS Cost and Usage Reports (CUR) with scenario modeling for Savings Plans and Spot instances.

## Features

- Upload AWS CUR CSV files directly in the browser
- Client-side processing (your data never leaves your browser)
- Analyze cost scenarios for:
  - Savings Plans coverage
  - Spot instance adoption
  - Pass-through discount modeling
- Interactive charts and visualizations
- Real-time KPI calculations

## Getting Started

### Install Dependencies

```bash
npm install
```

### Run Development Server

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

### Build for Production

```bash
npm run build
npm start
```

## Deploying to Vercel

1. **Push your code to GitHub** (if not already done):
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin <your-github-repo-url>
   git push -u origin main
   ```

2. **Deploy to Vercel**:
   - Go to [vercel.com](https://vercel.com)
   - Click "New Project"
   - Import your GitHub repository
   - Vercel will automatically detect Next.js and configure the build settings
   - Click "Deploy"

   Alternatively, use the Vercel CLI:
   ```bash
   npm i -g vercel
   vercel
   ```

3. **That's it!** Your dashboard will be live on Vercel.

## Usage

1. Upload a CUR CSV file using the file input
2. Adjust parameters:
   - **Additional SP coverage**: Additional Savings Plan coverage percentage (0-1)
   - **Spot discount**: Expected discount from Spot instances (0-0.95)
   - **Pass-through list**: Comma-separated list of pass-through percentages (e.g., 0.3,0.4,0.5,0.6,0.7,0.8,1.0)
3. Click "Compute scenarios" to analyze your data
4. Review the generated charts, KPIs, and scenario tables

## Expected CUR Columns

The dashboard expects the following columns in your CUR CSV:
- `lineItem/NetUnblendedCost` (or `lineItem/UnblendedCost`)
- `pricing/publicOnDemandCost` (optional)
- `lineItem/UsageStartDate`
- `bill/BillingPeriodStartDate`
- `bill/BillingPeriodEndDate`
- `lineItem/LineItemType`
- `lineItem/ProductCode`
- `lineItem/UsageType` (optional)
- `product/ProductName` (optional)

## Technology Stack

- **Next.js 14** - React framework
- **TypeScript** - Type safety
- **Plotly.js** - Interactive charts
- **PapaParse** - CSV parsing
- **React Plotly** - React wrapper for Plotly

## Privacy

All processing happens client-side. Your CSV files are never uploaded to any server - they're processed entirely in your browser.

