import { Routes } from '@angular/router';

export const routes: Routes = [
  // No auth — go straight to dashboard
  { path: '', redirectTo: 'dashboard', pathMatch: 'full' },
  { path: 'login', redirectTo: 'dashboard', pathMatch: 'full' },

  // ── Overview ─────────────────────────────────────────────────────────────
  { path: 'dashboard',        loadComponent: () => import('./pages/dashboard/dashboard.component').then(m => m.DashboardComponent) },
  { path: 'transactions',     loadComponent: () => import('./pages/transactions/transactions.component').then(m => m.TransactionsComponent) },

  // ── Fraud Detection ───────────────────────────────────────────────────────
  { path: 'analytics-3d',     loadComponent: () => import('./pages/analytics-3d/analytics-3d.component').then(m => m.Analytics3dComponent) },
  { path: 'model-comparison', loadComponent: () => import('./pages/model-comparison/model-comparison.component').then(m => m.ModelComparisonComponent) },
  { path: 'model-monitoring', loadComponent: () => import('./pages/model-monitoring/model-monitoring.component').then(m => m.ModelMonitoringComponent) },
  { path: 'review-queue',     loadComponent: () => import('./pages/review-queue/review-queue.component').then(m => m.ReviewQueueComponent) },
  { path: 'explainability',   loadComponent: () => import('./pages/explainability/explainability.component').then(m => m.ExplainabilityComponent) },
  { path: 'training',         loadComponent: () => import('./pages/training/training.component').then(m => m.TrainingComponent) },

  // ── Credit Scoring ────────────────────────────────────────────────────────
  { path: 'credit-scoring',   loadComponent: () => import('./pages/credit-scoring/credit-scoring.component').then(m => m.CreditScoringComponent) },
  { path: 'loan-portfolio',   loadComponent: () => import('./pages/loan-portfolio/loan-portfolio.component').then(m => m.LoanPortfolioComponent) },
  { path: 'applicants',       loadComponent: () => import('./pages/applicants/applicants.component').then(m => m.ApplicantsComponent) },

  // ── Risk Analytics ────────────────────────────────────────────────────────
  { path: 'risk-analytics',   loadComponent: () => import('./pages/risk-analytics/risk-analytics.component').then(m => m.RiskAnalyticsComponent) },
  { path: 'fpd-analysis',     loadComponent: () => import('./pages/fpd-analysis/fpd-analysis.component').then(m => m.FpdAnalysisComponent) },
  { path: 'vintage-analysis', loadComponent: () => import('./pages/vintage-analysis/vintage-analysis.component').then(m => m.VintageAnalysisComponent) },

  // ── A/B Testing & Cost ────────────────────────────────────────────────────
  { path: 'ab-testing',       loadComponent: () => import('./pages/ab-testing/ab-testing.component').then(m => m.AbTestingComponent) },
  { path: 'cost-analysis',    loadComponent: () => import('./pages/cost-analysis/cost-analysis.component').then(m => m.CostAnalysisComponent) },

  { path: '**', redirectTo: 'dashboard' },
];
