import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { timeout } from 'rxjs/operators';
import { environment } from '../../environments/environment';

const BASE = environment.apiUrl;
const TIMEOUT_MS = 8000; // 8 second timeout on all calls

@Injectable({ providedIn: 'root' })
export class ApiService {
  constructor(private http: HttpClient) {}

  private get<T>(url: string, opts?: any): Observable<T> {
    return this.get<T>(url, opts).pipe(timeout(TIMEOUT_MS));
  }

  private post<T>(url: string, body: any): Observable<T> {
    return this.post<T>(url, body).pipe(timeout(TIMEOUT_MS));
  }

  // ── Health ──────────────────────────────────────────────────────────────
  health(): Observable<any> { return this.get(`${BASE}/health`); }

  // ── Analytics ───────────────────────────────────────────────────────────
  getSummary(): Observable<any>            { return this.get(`${BASE}/analytics/summary`); }
  getFraudByChannel(): Observable<any>     { return this.get(`${BASE}/analytics/fraud-by-channel`); }
  getFraudByCountry(): Observable<any>     { return this.get(`${BASE}/analytics/fraud-by-country`); }
  getAmountDistribution(): Observable<any> { return this.get(`${BASE}/analytics/amount-distribution`); }
  getReviewQueueDepth(): Observable<any>   { return this.get(`${BASE}/analytics/review-queue-depth`); }
  getImbalanceReport(): Observable<any>    { return this.get(`${BASE}/analytics/imbalance-report`); }
  getDailyFraudTrend(): Observable<any>    { return this.get(`${BASE}/analytics/daily-fraud-trend`); }
  getModelComparison(): Observable<any>    { return this.get(`${BASE}/analytics/model-comparison`); }
  getFeatureImportance(topN = 20): Observable<any> {
    return this.get(`${BASE}/analytics/feature-importance?top_n=${topN}`);
  }
  getShapSummary(topN = 20): Observable<any> {
    return this.get(`${BASE}/analytics/shap-summary?top_n=${topN}`);
  }
  getScoreDistribution(): Observable<any> { return this.get(`${BASE}/analytics/score-distribution`); }
  getCalibration(): Observable<any>       { return this.get(`${BASE}/analytics/calibration`); }
  getTopFlagged(limit = 20): Observable<any> {
    return this.get(`${BASE}/analytics/top-flagged?limit=${limit}`);
  }
  getReviewDecisions(): Observable<any>   { return this.get(`${BASE}/analytics/review-decisions`); }
  getChannelVelocity(): Observable<any>   { return this.get(`${BASE}/analytics/channel-velocity`); }
  getPRCurve(): Observable<any>           { return this.get(`${BASE}/analytics/precision-recall-curve`); }

  // ── Transactions ─────────────────────────────────────────────────────────
  getTransactions(page = 1, pageSize = 20, filters: any = {}): Observable<any> {
    let params = new HttpParams().set('page', page).set('page_size', pageSize);
    Object.entries(filters).forEach(([k, v]) => {
      if (v !== null && v !== undefined && v !== '') params = params.set(k, String(v));
    });
    return this.get(`${BASE}/transactions/`, { params });
  }
  getTransaction(id: number): Observable<any> {
    return this.get(`${BASE}/transactions/${id}`);
  }

  // ── Predictions ──────────────────────────────────────────────────────────
  scoreTransaction(txn: any): Observable<any> {
    return this.post(`${BASE}/predictions/score`, txn);
  }
  scoreBatch(transactions: any[]): Observable<any> {
    return this.post(`${BASE}/predictions/score-batch`, { transactions });
  }
  getModelInfo(): Observable<any> {
    return this.get(`${BASE}/predictions/model-info`);
  }

  // ── Review ───────────────────────────────────────────────────────────────
  getReviewQueue(page = 1, status = 'pending'): Observable<any> {
    return this.get(`${BASE}/review/queue?page=${page}&status=${status}`);
  }
  getReviewItem(id: number): Observable<any> {
    return this.get(`${BASE}/review/item/${id}`);
  }
  submitDecision(body: any): Observable<any> {
    return this.post(`${BASE}/review/decide`, body);
  }
  getReviewStats(): Observable<any> { return this.get(`${BASE}/review/stats`); }
  populateReviewQueue(): Observable<any> {
    return this.post(`${BASE}/review/populate-queue`, {});
  }

  // ── Training ─────────────────────────────────────────────────────────────
  triggerPipeline(body: any = {}): Observable<any> {
    return this.post(`${BASE}/training/run`, body);
  }
  getPipelineStatus(): Observable<any>   { return this.get(`${BASE}/training/status`); }
  getMlflowRuns(): Observable<any>       { return this.get(`${BASE}/training/mlflow-runs`); }
  getMlflowUrl(): Observable<any>        { return this.get(`${BASE}/training/mlflow-url`); }
  // ── Re-evaluate champion ─────────────────────────────────────────────────
  getModelVersions(): Observable<any>    { return this.get(`${BASE}/training/versions`); }
  getRunMetrics(id: number): Observable<any> {
    return this.get(`${BASE}/training/metrics/${id}`);
  }
  rechampion(): Observable<any> {
    return this.post(`${BASE}/training/rechampion`, {});
  }

  // ── Explainability ───────────────────────────────────────────────────────
  getExplainFeatureImportance(topN = 20): Observable<any> {
    return this.get(`${BASE}/explainability/feature-importance?top_n=${topN}`);
  }
  getShapGlobal(topN = 20): Observable<any> {
    return this.get(`${BASE}/explainability/shap/global?top_n=${topN}`);
  }
  getShapLocal(txnId: number): Observable<any> {
    return this.get(`${BASE}/explainability/shap/transaction/${txnId}`);
  }
  getLimeLocal(txnId: number): Observable<any> {
    return this.get(`${BASE}/explainability/lime/transaction/${txnId}`);
  }
  getExplainSummary(): Observable<any> {
    return this.get(`${BASE}/explainability/summary`);
  }

  // ── 3D KPIs ─────────────────────────────────────────────────────────────
  get3dRiskLandscape(maxPoints = 800): Observable<any> {
    return this.get(`${BASE}/analytics/3d/risk-landscape?max_points=${maxPoints}`);
  }
  get3dModelPerformanceCube(): Observable<any> {
    return this.get(`${BASE}/analytics/3d/model-performance-cube`);
  }
  get3dPRTSurface(): Observable<any> {
    return this.get(`${BASE}/analytics/3d/prt-surface`);
  }

  // ── Heatmap / Polar / Boxplot ─────────────────────────────────────────
  getHeatmapFraudRisk(): Observable<any> {
    return this.get(`${BASE}/analytics/heatmap/fraud-risk`);
  }
  getPolarFraudByDow(): Observable<any> {
    return this.get(`${BASE}/analytics/polar/fraud-by-dow`);
  }
  getBoxplotAmountByChannel(): Observable<any> {
    return this.get(`${BASE}/analytics/boxplot/amount-by-channel`);
  }

  // ── Pipeline (ingest) ────────────────────────────────────────────────────
  ingestData(dataDir?: string): Observable<any> {
    return this.post(`${BASE}/pipeline/ingest`, { data_dir: dataDir ?? null });
  }
  getIngestStatus(): Observable<any> {
    return this.get(`${BASE}/pipeline/ingest-status`);
  }

  // ── Credit Scoring ───────────────────────────────────────────────────────
  getCreditSummary(): Observable<any>           { return this.get(`${BASE}/credit/summary`); }
  getCreditScoreDistribution(): Observable<any> { return this.get(`${BASE}/credit/score-distribution`); }
  getPDDistribution(): Observable<any>          { return this.get(`${BASE}/credit/pd-distribution`); }
  getPortfolioByProduct(): Observable<any>      { return this.get(`${BASE}/credit/portfolio-by-product`); }
  getPortfolioByCountry(): Observable<any>      { return this.get(`${BASE}/credit/portfolio-by-country`); }
  getScoreHeatmap(): Observable<any>            { return this.get(`${BASE}/credit/score-heatmap`); }
  getBureauSignals(): Observable<any>           { return this.get(`${BASE}/credit/bureau-signals`); }
  getApplicants(page = 1, pageSize = 20, filters: any = {}): Observable<any> {
    let params = new HttpParams().set('page', page).set('page_size', pageSize);
    Object.entries(filters).forEach(([k, v]) => {
      if (v !== null && v !== undefined && v !== '') params = params.set(k, String(v));
    });
    return this.get(`${BASE}/credit/applicants`, { params });
  }
  getApplicant(id: string): Observable<any> {
    return this.get(`${BASE}/credit/applicants/${id}`);
  }
  getLoans(page = 1, pageSize = 20, filters: any = {}): Observable<any> {
    let params = new HttpParams().set('page', page).set('page_size', pageSize);
    Object.entries(filters).forEach(([k, v]) => {
      if (v !== null && v !== undefined && v !== '') params = params.set(k, String(v));
    });
    return this.get(`${BASE}/credit/loans`, { params });
  }

  // ── Risk Analytics ───────────────────────────────────────────────────────
  getFpdSummary(): Observable<any>         { return this.get(`${BASE}/risk/fpd/summary`); }
  getFpdTrend(): Observable<any>           { return this.get(`${BASE}/risk/fpd/trend`); }
  getFpdByScoreBand(): Observable<any>     { return this.get(`${BASE}/risk/fpd/by-score-band`); }
  getVintageCurves(): Observable<any>      { return this.get(`${BASE}/risk/vintage/curves`); }
  getRollRates(): Observable<any>          { return this.get(`${BASE}/risk/roll-rates`); }
  getKsGini(): Observable<any>             { return this.get(`${BASE}/risk/ks-gini`); }
  getPsiDrift(): Observable<any>           { return this.get(`${BASE}/risk/psi-drift`); }
  getExpectedLoss(): Observable<any>       { return this.get(`${BASE}/risk/expected-loss`); }
  getRiskBySegment(): Observable<any>      { return this.get(`${BASE}/risk/risk-by-segment`); }
  getPortfolioTrend(): Observable<any>     { return this.get(`${BASE}/risk/portfolio-trend`); }

  // ── A/B Testing ──────────────────────────────────────────────────────────
  getABTests(): Observable<any>            { return this.get(`${BASE}/ab/tests`); }
  getABTest(id: string): Observable<any>   { return this.get(`${BASE}/ab/tests/${id}`); }
  getABSummary(): Observable<any>          { return this.get(`${BASE}/ab/summary`); }
  getABPowerAnalysis(params: any = {}): Observable<any> {
    let p = new HttpParams();
    Object.entries(params).forEach(([k, v]) => { if (v != null) p = p.set(k, String(v)); });
    return this.get(`${BASE}/ab/power-analysis`, { params: p });
  }
  getABCumulativeLift(testId: string): Observable<any> {
    return this.get(`${BASE}/ab/cumulative-lift/${testId}`);
  }

  // ── Cost Analysis ────────────────────────────────────────────────────────
  getCostSummary(): Observable<any>        { return this.get(`${BASE}/cost/summary`); }
  getCostByPeriod(): Observable<any>       { return this.get(`${BASE}/cost/by-period`); }
  getCostWaterfall(): Observable<any>      { return this.get(`${BASE}/cost/savings-waterfall`); }
  getCostROITrend(): Observable<any>       { return this.get(`${BASE}/cost/roi-trend`); }
  getCostBreakdown(): Observable<any>      { return this.get(`${BASE}/cost/cost-breakdown`); }
  getCostScenario(params: any = {}): Observable<any> {
    let p = new HttpParams();
    Object.entries(params).forEach(([k, v]) => { if (v != null) p = p.set(k, String(v)); });
    return this.get(`${BASE}/cost/scenario`, { params: p });
  }

  // ── AI Insights ──────────────────────────────────────────────────────────
  getDashboardInsights(): Observable<any>    { return this.get(`${BASE}/insights/dashboard`); }
  getKpiInsight(id: string): Observable<any> { return this.get(`${BASE}/insights/kpi/${id}`); }
  getActiveAlerts(): Observable<any>         { return this.get(`${BASE}/insights/alerts`); }
  // ── Credit Pipeline ─────────────────────────────────────────────────────
  triggerCreditPipeline(): Observable<any>   { return this.post(`${BASE}/credit-training/run`, {}); }
  getCreditPipelineStatus(): Observable<any> { return this.get(`${BASE}/credit-training/status`); }
  getCreditModels(): Observable<any>         { return this.get(`${BASE}/credit-training/models`); }
  getCreditChampion(): Observable<any>       { return this.get(`${BASE}/credit-training/champion`); }
  getCreditFI(id: number): Observable<any>  { return this.get(`${BASE}/credit-training/models/${id}/feature-importance`); }
  triggerHCIngest(sample = 100000): Observable<any> { return this.post(`${BASE}/credit-training/ingest?sample=${sample}&force=true`, {}); }
  getHCIngestStatus(): Observable<any>      { return this.get(`${BASE}/credit-training/ingest-status`); }
}
