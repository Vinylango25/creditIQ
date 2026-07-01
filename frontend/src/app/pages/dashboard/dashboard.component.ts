import { Component, OnInit } from '@angular/core';
import { CommonModule, DecimalPipe } from '@angular/common';
import { RouterLink } from '@angular/router';
import { forkJoin, of } from 'rxjs';
import { catchError } from 'rxjs/operators';
import { ApiService } from '../../core/api.service';
import { ChartComponent } from '../../shared/chart/chart.component';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, RouterLink, ChartComponent],
  templateUrl: './dashboard.component.html',
  styleUrls: ['./dashboard.component.scss'],
})
export class DashboardComponent implements OnInit {
  loading = true;

  // ── Data ─────────────────────────────────────────────────────────────────
  fraudSummary:   any = {};
  creditSummary:  any = {};
  fraudByChannel: any[] = [];
  fraudByCountry: any[] = [];
  topFlagged:     any[] = [];
  reviewStats:    any = {};
  modelComparison:any[] = [];
  dailyTrend:     any = {};
  prCurve:        any = {};
  scoreDistribution: any = {};
  portfolioTrend: any = {};
  riskBySegment:  any = {};
  fpd:            any = {};
  costSummary:    any = {};
  psiDrift:       any[] = [];

  // ── AI Insights ───────────────────────────────────────────────────────────
  insights:       any = { insights: [], alerts: 0, warnings: 0, good: 0 };
  expandedInsight: string | null = null;
  insightFilter:  string = 'all';  // all | alert | warning | good

  // ── Derived KPIs ─────────────────────────────────────────────────────────
  recallPct        = '—';
  recallDashOffset = 314;
  avgScoreOffset   = 314;   // for credit score ring
  avgScore         = 0;

  // ── Charts ────────────────────────────────────────────────────────────────
  trendOpts:      any = {};
  channelOpts:    any = {};
  prOpts:         any = {};
  scoreBandOpts:  any = {};
  portfolioOpts:  any = {};
  segmentOpts:    any = {};
  psiOpts:        any = {};
  countryOpts:    any = {};

  constructor(private api: ApiService) {}

  ngOnInit(): void {
    // Show shell immediately — don't block on loading
    this.loading = false;
    // Load data async — each call handles its own error
    this.loadData();
  }

  private loadData(): void {
    forkJoin({
      fraud:       this.api.getSummary()            .pipe(catchError(() => of({}))),
      credit:      this.api.getCreditSummary()      .pipe(catchError(() => of({}))),
      channel:     this.api.getFraudByChannel()     .pipe(catchError(() => of([]))),
      country:     this.api.getFraudByCountry()     .pipe(catchError(() => of([]))),
      trend:       this.api.getDailyFraudTrend()    .pipe(catchError(() => of({}))),
      prCurve:     this.api.getPRCurve()            .pipe(catchError(() => of({}))),
      score:       this.api.getScoreDistribution()  .pipe(catchError(() => of({}))),
      topFlagged:  this.api.getTopFlagged(8)        .pipe(catchError(() => of([]))),
      reviewDepth: this.api.getReviewQueueDepth()   .pipe(catchError(() => of({}))),
      models:      this.api.getModelComparison()    .pipe(catchError(() => of([]))),
      portTrend:   this.api.getPortfolioTrend()     .pipe(catchError(() => of({}))),
      segment:     this.api.getRiskBySegment()      .pipe(catchError(() => of({}))),
      fpdSum:      this.api.getFpdSummary()         .pipe(catchError(() => of({}))),
      cost:        this.api.getCostSummary()        .pipe(catchError(() => of({}))),
      insights:    this.api.getDashboardInsights()   .pipe(catchError(() => of({ insights:[], alerts:0, warnings:0, good:0 }))),
      scoreDist:   this.api.getCreditScoreDistribution().pipe(catchError(() => of({}))),
      psi:         this.api.getPsiDrift()               .pipe(catchError(() => of([]))),
    }).subscribe({
      next: (r: any) => {
        this.fraudSummary    = r.fraud    || {};
        this.creditSummary   = r.credit   || {};
        this.fraudByChannel  = Array.isArray(r.channel) ? r.channel : [];
        this.fraudByCountry  = Array.isArray(r.country) ? r.country : [];
        this.dailyTrend      = r.trend    || {};
        this.prCurve         = r.prCurve  || {};
        this.scoreDistribution = r.score  || {};
        this.topFlagged      = Array.isArray(r.topFlagged) ? r.topFlagged : [];
        this.reviewStats     = r.reviewDepth || {};
        this.modelComparison = Array.isArray(r.models) ? r.models : [];
        this.portfolioTrend  = r.portTrend   || {};
        this.riskBySegment   = r.segment     || {};
        this.fpd             = r.fpdSum      || {};
        this.costSummary     = r.cost        || {};
        this.psiDrift        = Array.isArray(r.psi) ? r.psi : [];
        this.insights        = r.insights || { insights: [], alerts: 0, warnings: 0, good: 0 };

        // Fraud recall ring
        const recall = this.fraudSummary?.champion_recall ?? 0;
        if (recall) {
          this.recallPct        = Math.round(recall * 100) + '%';
          this.recallDashOffset = 314 * (1 - recall);
        }

        // Credit score ring
        this.avgScore = Math.round(this.creditSummary?.avg_credit_score || 0);
        if (this.avgScore) {
          const pct = (this.avgScore - 300) / 550; // 300–850 range
          this.avgScoreOffset = 314 * (1 - pct);
        }

        this.buildCharts(r.scoreDist || {});
        this.loading = false;
      },
      error: () => { this.loading = false; }
    });
  }

  private buildCharts(scoreDist: any): void {

    // ── Fraud trend + portfolio default rate overlay ─────────────────────
    if (this.dailyTrend?.buckets?.length) {
      this.trendOpts = {
        tooltip: { trigger: 'axis' },
        legend:  { data: ['Fraud Txns', 'Legit Txns'], textStyle: { color: '#94a3b8' } },
        xAxis:   { type: 'category', data: this.dailyTrend.buckets,
                   axisLabel: { color: '#64748b', interval: 5, rotate: 20, fontSize: 10 } },
        yAxis:   { type: 'value', axisLabel: { color: '#64748b' } },
        series:  [
          { name: 'Fraud Txns', type: 'line', smooth: true, showSymbol: false,
            data: this.dailyTrend.fraud, itemStyle: { color: '#ef4444' }, areaStyle: { opacity: .25 } },
          { name: 'Legit Txns', type: 'line', smooth: true, showSymbol: false,
            data: this.dailyTrend.legit, itemStyle: { color: '#10b981' }, areaStyle: { opacity: .12 } },
        ],
        backgroundColor: 'transparent',
      };
    }

    // ── Channel fraud rate ────────────────────────────────────────────────
    if (this.fraudByChannel.length) {
      const ch = this.fraudByChannel;
      this.channelOpts = {
        tooltip: { trigger: 'axis' },
        legend:  { data: ['Fraud Rate %', 'Volume'], textStyle: { color: '#94a3b8' } },
        xAxis:   { type: 'category', data: ch.map((r: any) => r.channel),
                   axisLabel: { color: '#64748b', rotate: 15, fontSize: 11 } },
        yAxis:   [
          { type: 'value', name: 'Fraud %', axisLabel: { color: '#64748b', formatter: '{value}%' } },
          { type: 'value', name: 'Volume',  axisLabel: { color: '#64748b' } },
        ],
        series: [
          { name: 'Fraud Rate %', type: 'bar', data: ch.map((r: any) => +(r.fraud_rate*100).toFixed(2)),
            itemStyle: { color: '#ef4444' }, yAxisIndex: 0 },
          { name: 'Volume', type: 'line', data: ch.map((r: any) => r.total), smooth: true,
            itemStyle: { color: '#3b82f6' }, yAxisIndex: 1 },
        ],
        backgroundColor: 'transparent',
      };
    }

    // ── PR curve ─────────────────────────────────────────────────────────
    if (this.prCurve?.precision?.length) {
      this.prOpts = {
        tooltip: { trigger: 'axis' },
        xAxis: { type: 'value', name: 'Recall',    min: 0, max: 1, axisLabel: { color: '#64748b' } },
        yAxis: { type: 'value', name: 'Precision', min: 0, max: 1, axisLabel: { color: '#64748b' } },
        series: [{ type: 'line', smooth: true, showSymbol: false,
          data: this.prCurve.recall.map((r: number, i: number) => [r, this.prCurve.precision[i]]),
          itemStyle: { color: '#8b5cf6' }, areaStyle: { opacity: .2 } }],
        backgroundColor: 'transparent',
      };
    }

    // ── Credit score band distribution ───────────────────────────────────
    if (scoreDist?.bands?.length) {
      const colors = ['#ef4444','#f97316','#f59e0b','#10b981','#3b82f6'];
      this.scoreBandOpts = {
        tooltip: { trigger: 'axis' },
        xAxis:   { type: 'category', data: scoreDist.bands,
                   axisLabel: { color: '#64748b', fontSize: 10, rotate: 12 } },
        yAxis:   { type: 'value', axisLabel: { color: '#64748b' } },
        series:  [{ type: 'bar', data: scoreDist.counts,
          itemStyle: { color: (p: any) => colors[p.dataIndex] || '#3b82f6' },
          label: { show: true, position: 'top', fontSize: 10, color: '#94a3b8' },
        }],
        backgroundColor: 'transparent',
      };
    }

    // ── Portfolio trend ───────────────────────────────────────────────────
    if (this.portfolioTrend?.months?.length) {
      const m = this.portfolioTrend;
      this.portfolioOpts = {
        tooltip: { trigger: 'axis' },
        legend:  { data: ['Loans Disbursed', 'Default Rate %'], textStyle: { color: '#94a3b8' } },
        xAxis:   { type: 'category', data: m.months,
                   axisLabel: { color: '#64748b', interval: 2, rotate: 20, fontSize: 10 } },
        yAxis: [
          { type: 'value', name: 'Loans', axisLabel: { color: '#64748b' } },
          { type: 'value', name: 'Default %', axisLabel: { color: '#64748b', formatter: '{value}%' } },
        ],
        series: [
          { name: 'Loans Disbursed', type: 'bar', data: m.loan_volumes,
            itemStyle: { color: '#3b82f6', opacity: .7 }, yAxisIndex: 0 },
          { name: 'Default Rate %', type: 'line', data: m.default_rates, smooth: true,
            itemStyle: { color: '#ef4444' }, yAxisIndex: 1 },
        ],
        backgroundColor: 'transparent',
      };
    }

    // ── Risk by employment ────────────────────────────────────────────────
    if (this.riskBySegment?.by_employment?.length) {
      const segs = this.riskBySegment.by_employment;
      this.segmentOpts = {
        tooltip: { trigger: 'axis' },
        legend:  { data: ['Default Rate %', 'Avg PD %'], textStyle: { color: '#94a3b8' } },
        xAxis:   { type: 'category', data: segs.map((s: any) => s.segment), axisLabel: { color: '#64748b' } },
        yAxis:   { type: 'value', axisLabel: { color: '#64748b', formatter: '{value}%' } },
        series:  [
          { name: 'Default Rate %', type: 'bar', data: segs.map((s: any) => +(s.default_rate*100).toFixed(2)), itemStyle: { color: '#ef4444' } },
          { name: 'Avg PD %',       type: 'bar', data: segs.map((s: any) => +(s.avg_pd*100).toFixed(2)),      itemStyle: { color: '#f59e0b' } },
        ],
        backgroundColor: 'transparent',
      };
    }

    // ── PSI drift summary ─────────────────────────────────────────────────
    if (this.psiDrift.length) {
      const top8 = [...this.psiDrift].sort((a, b) => b.psi - a.psi).slice(0, 8);
      this.psiOpts = {
        tooltip: { trigger: 'axis' },
        xAxis:   { type: 'value', axisLabel: { color: '#64748b' } },
        yAxis:   { type: 'category', data: top8.map((r: any) => r.feature),
                   axisLabel: { color: '#64748b', fontSize: 11 } },
        series:  [{ type: 'bar', data: top8.map((r: any) => r.psi),
          itemStyle: { color: (p: any) => {
            const v = p.data;
            return v >= 0.25 ? '#ef4444' : v >= 0.1 ? '#f59e0b' : '#10b981';
          }},
          label: { show: true, position: 'right', formatter: (p: any) => p.data.toFixed(3), color: '#94a3b8', fontSize: 10 },
        }],
        grid: { left: '30%', right: '15%', top: '5%', bottom: '5%' },
        backgroundColor: 'transparent',
      };
    }

    // ── Country donut ─────────────────────────────────────────────────────
    if (this.fraudByCountry.length) {
      this.countryOpts = {
        tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
        legend:  { bottom: 0, textStyle: { color: '#94a3b8' } },
        series: [{ type: 'pie', radius: ['42%','68%'], center: ['50%','45%'],
          data: this.fraudByCountry.map((r: any) => ({ name: r.country, value: r.fraud_count })),
          label: { color: '#94a3b8', formatter: '{b}\n{d}%' },
        }],
        backgroundColor: 'transparent',
      };
    }
  }

  // ── Helpers ───────────────────────────────────────────────────────────────
  scoreGrade(s: number): string {
    if (s >= 750) return 'grade-a';
    if (s >= 700) return 'grade-b';
    if (s >= 650) return 'grade-c';
    if (s >= 600) return 'grade-d';
    return 'grade-e';
  }

  scoreLabel(s: number): string {
    if (s >= 750) return 'Excellent';
    if (s >= 700) return 'Good';
    if (s >= 650) return 'Fair';
    if (s >= 600) return 'Poor';
    return 'Very Poor';
  }

  riskClass(p: number): string {
    return p >= 0.7 ? 'risk--high' : p >= 0.3 ? 'risk--medium' : 'risk--low';
  }

  metricClass(v: number): string {
    return v >= 0.85 ? 'mc--excellent' : v >= 0.70 ? 'mc--good' : v >= 0.55 ? 'mc--fair' : 'mc--poor';
  }

  compositeScore(m: any): number {
    return +(0.50*(m.recall_fraud||0)+0.20*(m.pr_auc||0)+0.20*(m.auc_roc||0)+0.10*(m.f1_fraud||0)).toFixed(4);
  }

  fmtKES(n: number): string {
    if (!n) return '—';
    if (n >= 1_000_000_000) return (n/1_000_000_000).toFixed(1)+'B';
    if (n >= 1_000_000)     return (n/1_000_000).toFixed(1)+'M';
    if (n >= 1_000)         return (n/1_000).toFixed(1)+'K';
    return n.toFixed(0);
  }

  bestAuc(): string {
    if (!this.modelComparison.length) return '—';
    const best = this.modelComparison.reduce((a, b) => (a.auc_roc||0) > (b.auc_roc||0) ? a : b);
    return best.auc_roc?.toFixed(4) || '—';
  }

  topPsi(): any {
    if (!this.psiDrift.length) return null;
    return [...this.psiDrift].sort((a, b) => b.psi - a.psi)[0];
  }

  psiAlertCount(): number {
    return this.psiDrift.filter(p => p.psi >= 0.25).length;
  }

  psiAlertClass(v: number): string {
    return v >= 0.25 ? 'badge--danger' : v >= 0.1 ? 'badge--warning' : 'badge--success';
  }

  // ── AI Insights helpers ───────────────────────────────────────────────────
  filteredInsights(): any[] {
    const ins = this.insights?.insights || [];
    if (this.insightFilter === 'all') return ins;
    return ins.filter((i: any) => i.status === this.insightFilter);
  }

  toggleInsight(id: string): void {
    this.expandedInsight = this.expandedInsight === id ? null : id;
  }

  setFilter(f: string): void { this.insightFilter = f; }

  insightStatusIcon(status: string): string {
    return status === 'good' ? '✅' : status === 'warning' ? '⚠️' : '🔴';
  }

  insightBadgeClass(status: string): string {
    return status === 'good' ? 'badge--success' : status === 'warning' ? 'badge--warning' : 'badge--danger';
  }
}
