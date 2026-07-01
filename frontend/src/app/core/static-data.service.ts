/**
 * StaticDataService — serves all analytics from pre-built JSON assets.
 * Replaces ApiService HTTP calls for fully static Vercel deployment.
 * All data is pre-computed from the seeded database and bundled at build time.
 */
import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, of } from 'rxjs';
import { catchError, shareReplay } from 'rxjs/operators';

const ASSETS = 'data';

@Injectable({ providedIn: 'root' })
export class StaticDataService {
  private cache = new Map<string, Observable<any>>();

  constructor(private http: HttpClient) {}

  private load(file: string): Observable<any> {
    if (!this.cache.has(file)) {
      const obs = this.http.get(`${ASSETS}/${file}.json`)
        .pipe(
          catchError(() => of(null)),
          shareReplay(1),
        );
      this.cache.set(file, obs);
    }
    return this.cache.get(file)!;
  }

  // ── Health ──────────────────────────────────────────────────────────────
  health():                    Observable<any> { return of({ status:'ok', service:'CreditIQ Static' }); }

  // ── Analytics (Fraud) ────────────────────────────────────────────────────
  getSummary():                Observable<any> { return this.load('analytics_summary'); }
  getFraudByChannel():         Observable<any> { return this.load('fraud_by_channel'); }
  getFraudByCountry():         Observable<any> { return this.load('fraud_by_country'); }
  getAmountDistribution():     Observable<any> { return this.load('amount_distribution'); }
  getReviewQueueDepth():       Observable<any> { return this.load('review_queue_depth'); }
  getImbalanceReport():        Observable<any> { return this.load('imbalance_report'); }
  getDailyFraudTrend():        Observable<any> { return this.load('daily_fraud_trend'); }
  getModelComparison():        Observable<any> { return this.load('model_comparison'); }
  getFeatureImportance(_n=20): Observable<any> { return this.load('feature_importance'); }
  getShapSummary(_n=20):       Observable<any> { return this.load('shap_summary'); }
  getScoreDistribution():      Observable<any> { return this.load('score_distribution'); }
  getCalibration():            Observable<any> { return this.load('calibration'); }
  getTopFlagged(_l=20):        Observable<any> { return this.load('top_flagged'); }
  getReviewDecisions():        Observable<any> { return this.load('review_decisions'); }
  getChannelVelocity():        Observable<any> { return this.load('channel_velocity'); }
  getPRCurve():                Observable<any> { return this.load('precision_recall_curve'); }
  get3dRiskLandscape(_n=800):  Observable<any> { return this.load('3d_risk_landscape'); }
  get3dModelPerformanceCube(): Observable<any> { return this.load('3d_model_cube'); }
  get3dPRTSurface():           Observable<any> { return this.load('3d_prt_surface'); }
  getHeatmapFraudRisk():       Observable<any> { return this.load('heatmap_fraud_risk'); }
  getPolarFraudByDow():        Observable<any> { return this.load('polar_fraud_dow'); }
  getBoxplotAmountByChannel(): Observable<any> { return this.load('boxplot_amount'); }

  // ── Transactions ─────────────────────────────────────────────────────────
  getTransactions(_p=1,_ps=20,_f:any={}): Observable<any> {
    return this.load('transactions_sample').pipe(
      catchError(() => of({ total: 0, page: 1, page_size: 20, transactions: [] }))
    );
  }
  getTransaction(_id: number): Observable<any> { return of(null); }

  // ── Predictions ──────────────────────────────────────────────────────────
  scoreTransaction(_t: any): Observable<any> { return of({ status: 'static_mode' }); }
  scoreBatch(_t: any[]):     Observable<any> { return of({ status: 'static_mode' }); }
  getModelInfo():            Observable<any> { return this.load('model_comparison'); }

  // ── Review ───────────────────────────────────────────────────────────────
  getReviewQueue(_p=1,_s='pending'): Observable<any> { return of({ total:0,page:1,page_size:20,items:[] }); }
  getReviewItem(_id: number):        Observable<any> { return of(null); }
  submitDecision(_b: any):           Observable<any> { return of({ status:'static_mode' }); }
  getReviewStats():                  Observable<any> { return this.load('review_queue_depth'); }
  populateReviewQueue():             Observable<any> { return of({ status:'static_mode' }); }

  // ── Training ─────────────────────────────────────────────────────────────
  triggerPipeline(_b: any={}):   Observable<any> { return of({ status:'static_mode' }); }
  getPipelineStatus():           Observable<any> { return of({ running:false,last_run_id:null }); }
  getMlflowRuns():               Observable<any> { return of([]); }
  getMlflowUrl():                Observable<any> { return of({ url:'#' }); }
  getModelVersions():            Observable<any> { return this.load('model_comparison'); }
  getRunMetrics(_id: number):    Observable<any> { return of({}); }
  rechampion():                  Observable<any> { return of({ status:'static_mode' }); }

  // ── Explainability ───────────────────────────────────────────────────────
  getExplainFeatureImportance(_n=20): Observable<any> { return this.load('feature_importance'); }
  getShapGlobal(_n=20):              Observable<any> { return this.load('shap_summary'); }
  getShapLocal(_id: number):         Observable<any> { return of({ status:'not_available' }); }
  getLimeLocal(_id: number):         Observable<any> { return of({ status:'not_available' }); }
  getExplainSummary():               Observable<any> { return of({ status:'static' }); }

  // ── Pipeline ─────────────────────────────────────────────────────────────
  ingestData(_d?: string): Observable<any> { return of({ status:'static_mode' }); }
  getIngestStatus():       Observable<any> { return of({ running:false, db_transaction_count: 160000 }); }

  // ── Credit Scoring ───────────────────────────────────────────────────────
  getCreditSummary():            Observable<any> { return this.load('credit_summary'); }
  getCreditScoreDistribution():  Observable<any> { return this.load('credit_score_distribution'); }
  getPDDistribution():           Observable<any> { return this.load('pd_distribution'); }
  getPortfolioByProduct():       Observable<any> { return this.load('portfolio_by_product'); }
  getPortfolioByCountry():       Observable<any> { return this.load('portfolio_by_country'); }
  getScoreHeatmap():             Observable<any> { return this.load('score_heatmap'); }
  getBureauSignals():            Observable<any> { return this.load('bureau_signals'); }
  getApplicants(_p=1,_ps=20,_f:any={}): Observable<any> {
    return this.load('applicants').pipe(
      catchError(() => of({ total:5000,page:1,page_size:20,applicants:[] }))
    );
  }
  getApplicant(_id: string): Observable<any> { return of(null); }
  getLoans(_p=1,_ps=20,_f:any={}): Observable<any> {
    return this.load('loans').pipe(
      catchError(() => of({ total:12000,page:1,page_size:20,loans:[] }))
    );
  }

  // ── Risk Analytics ───────────────────────────────────────────────────────
  getFpdSummary():     Observable<any> { return this.load('fpd_summary'); }
  getFpdTrend():       Observable<any> { return this.load('fpd_trend'); }
  getFpdByScoreBand(): Observable<any> { return this.load('fpd_by_score_band'); }
  getVintageCurves():  Observable<any> { return this.load('vintage_curves'); }
  getRollRates():      Observable<any> { return this.load('roll_rates'); }
  getKsGini():         Observable<any> { return this.load('ks_gini'); }
  getPsiDrift():       Observable<any> { return this.load('psi_drift'); }
  getExpectedLoss():   Observable<any> { return this.load('expected_loss'); }
  getRiskBySegment():  Observable<any> { return this.load('risk_by_segment'); }
  getPortfolioTrend(): Observable<any> { return this.load('portfolio_trend'); }

  // ── A/B Testing ──────────────────────────────────────────────────────────
  getABTests():                     Observable<any> { return this.load('ab_tests'); }
  getABTest(_id: string):           Observable<any> { return this.load('ab_tests'); }
  getABSummary():                   Observable<any> { return this.load('ab_summary'); }
  getABPowerAnalysis(_p: any={}):   Observable<any> { return of({ n_per_arm: 2340, total_n: 4680, baseline_rate: 0.10, treatment_rate: 0.08, alpha: 0.05, power: 0.80 }); }
  getABCumulativeLift(_id: string): Observable<any> { return this.load('ab_tests'); }

  // ── Cost Analysis ────────────────────────────────────────────────────────
  getCostSummary():          Observable<any> { return this.load('cost_summary'); }
  getCostByPeriod():         Observable<any> { return this.load('cost_by_period'); }
  getCostWaterfall():        Observable<any> { return this.load('cost_waterfall'); }
  getCostROITrend():         Observable<any> { return this.load('cost_roi_trend'); }
  getCostBreakdown():        Observable<any> { return this.load('cost_breakdown'); }
  getCostScenario(_p: any={}): Observable<any> {
    const bl=_p.baseline_dr||0.18, ml=_p.model_dr||0.095, n=_p.monthly_loans||1000, amt=_p.avg_loan_kes||8500;
    const saved = Math.round((bl-ml)*n*amt*0.55);
    return of({ savings:{ monthly_saved_kes:saved, annual_saved_kes:saved*12, roi_pct:320, default_rate_reduction_pct:((bl-ml)/bl*100).toFixed(1) }, baseline:{defaults:Math.round(n*bl)}, model:{defaults:Math.round(n*ml)} });
  }

  // ── AI Insights ──────────────────────────────────────────────────────────
  getDashboardInsights():      Observable<any> { return this.load('dashboard_insights'); }
  getKpiInsight(_id: string):  Observable<any> { return this.load('dashboard_insights'); }
  getActiveAlerts():           Observable<any> { return this.load('dashboard_insights'); }

  // ── Credit Pipeline (read-only in static mode) ────────────────────────────
  triggerCreditPipeline():     Observable<any> { return of({ status:'static_mode' }); }
  getCreditPipelineStatus():   Observable<any> { return of({ running:false, stage:'static' }); }
  getCreditModels():           Observable<any> { return this.load('model_comparison'); }
  getCreditChampion():         Observable<any> { return this.load('analytics_summary'); }
  getCreditFI(_id: number):    Observable<any> { return this.load('feature_importance'); }
  triggerHCIngest(_n=100000):  Observable<any> { return of({ status:'static_mode' }); }
  getHCIngestStatus():         Observable<any> { return of({ applicants:5000, loans:12000 }); }
}
