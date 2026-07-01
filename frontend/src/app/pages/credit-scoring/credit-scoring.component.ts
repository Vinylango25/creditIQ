import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { forkJoin, of } from 'rxjs';
import { catchError } from 'rxjs/operators';
import { ApiService } from '../../core/api.service';
import { ChartComponent } from '../../shared/chart/chart.component';

@Component({
  selector: 'app-credit-scoring',
  standalone: true,
  imports: [CommonModule, RouterLink, ChartComponent],
  templateUrl: './credit-scoring.component.html',
  styleUrls: ['./credit-scoring.component.scss'],
})
export class CreditScoringComponent implements OnInit {
  loading = true;

  summary:       any = {};
  scoreDist:     any = {};
  pdDist:        any = {};
  byProduct:     any[] = [];
  byCountry:     any[] = [];
  heatmap:       any = {};
  bureau:        any = {};
  fpd:           any = {};
  portfolioTrend:any = {};
  rollRates:     any = {};
  ksGini:        any = {};

  // Charts
  scoreDistOpts:  any = {};
  pdDistOpts:     any = {};
  productOpts:    any = {};
  countryOpts:    any = {};
  heatmapOpts:    any = {};
  utilizationOpts:any = {};
  dtiOpts:        any = {};
  inquiryOpts:    any = {};
  delinquencyOpts:any = {};
  trendOpts:      any = {};
  rollOpts:       any = {};
  ksCapOpts:      any = {};
  fpdBandOpts:    any = {};
  scoreGaugeOpts: any = {};
  pdHeatmapOpts:  any = {};

  // Score ring
  avgScore = 0;
  avgScoreOffset = 314;

  constructor(private api: ApiService) {}

  ngOnInit(): void {
    forkJoin({
      summary:    this.api.getCreditSummary()            .pipe(catchError(() => of({}))),
      scoreDist:  this.api.getCreditScoreDistribution()  .pipe(catchError(() => of({}))),
      pdDist:     this.api.getPDDistribution()           .pipe(catchError(() => of({}))),
      byProduct:  this.api.getPortfolioByProduct()       .pipe(catchError(() => of([]))),
      byCountry:  this.api.getPortfolioByCountry()       .pipe(catchError(() => of([]))),
      heatmap:    this.api.getScoreHeatmap()             .pipe(catchError(() => of({}))),
      bureau:     this.api.getBureauSignals()            .pipe(catchError(() => of({}))),
      fpd:        this.api.getFpdSummary()               .pipe(catchError(() => of({}))),
      portTrend:  this.api.getPortfolioTrend()           .pipe(catchError(() => of({}))),
      roll:       this.api.getRollRates()                .pipe(catchError(() => of({}))),
      ks:         this.api.getKsGini()                   .pipe(catchError(() => of({}))),
      fpdBand:    this.api.getFpdByScoreBand()           .pipe(catchError(() => of([]))),
    }).subscribe({
      next: (r: any) => {
        this.summary       = r.summary   || {};
        this.scoreDist     = r.scoreDist || {};
        this.pdDist        = r.pdDist    || {};
        this.byProduct     = Array.isArray(r.byProduct) ? r.byProduct : [];
        this.byCountry     = Array.isArray(r.byCountry) ? r.byCountry : [];
        this.heatmap       = r.heatmap   || {};
        this.bureau        = r.bureau    || {};
        this.fpd           = r.fpd       || {};
        this.portfolioTrend= r.portTrend || {};
        this.rollRates     = r.roll      || {};
        this.ksGini        = r.ks        || {};
        this.avgScore = Math.round(this.summary?.avg_credit_score || 0);
        if (this.avgScore) {
          const pct = (this.avgScore - 300) / 550;
          this.avgScoreOffset = 314 * (1 - pct);
        }
        this.buildCharts(Array.isArray(r.fpdBand) ? r.fpdBand : []);
        this.loading = false;
      },
      error: () => { this.loading = false; }
    });
  }

  private buildCharts(fpdBand: any[]): void {
    // Score gauge
    const pct = this.avgScore ? Math.round((this.avgScore - 300) / 550 * 100) : 0;
    this.scoreGaugeOpts = {
      series: [{
        type: 'gauge', startAngle: 200, endAngle: -20, min: 300, max: 850,
        pointer: { show: true, length: '65%', width: 6 },
        progress: { show: true, width: 14 },
        axisLine: { lineStyle: { width: 14, color: [[0.3,'#ef4444'],[0.5,'#f59e0b'],[0.7,'#3b82f6'],[1,'#10b981']] } },
        axisTick: { show: false },
        splitLine: { length: 14, lineStyle: { width: 2, color: 'var(--border)' } },
        axisLabel: { color: '#94a3b8', fontSize: 10, distance: 20 },
        detail: { valueAnimation: true, fontSize: 32, fontWeight: 800,
                  color: this.scoreColor(this.avgScore),
                  formatter: '{value}', offsetCenter: [0, '25%'] },
        title:  { offsetCenter: [0, '50%'], color: '#94a3b8', fontSize: 11 },
        data: [{ value: this.avgScore, name: 'Avg Credit Score' }],
        itemStyle: { color: this.scoreColor(this.avgScore) },
      }],
      backgroundColor: 'transparent',
    };

    // Score distribution
    if (this.scoreDist?.bands?.length) {
      const colors = ['#ef4444','#f97316','#f59e0b','#3b82f6','#10b981'];
      this.scoreDistOpts = {
        tooltip: { trigger: 'axis' },
        xAxis: { type: 'category', data: this.scoreDist.bands, axisLabel: { color: '#64748b', rotate: 12, fontSize: 11 } },
        yAxis: { type: 'value', axisLabel: { color: '#64748b' } },
        series: [{ type: 'bar', data: this.scoreDist.counts,
          itemStyle: { color: (p: any) => colors[p.dataIndex] || '#3b82f6', borderRadius: [4,4,0,0] },
          label: { show: true, position: 'top', color: '#94a3b8', fontSize: 11,
                   formatter: (p: any) => this.fmtNum(p.data) },
        }],
        backgroundColor: 'transparent',
      };
    }

    // PD distribution — gradient colored
    if (this.pdDist?.bins?.length) {
      this.pdDistOpts = {
        tooltip: { trigger: 'axis', formatter: (p: any) => `PD ${p[0].name}: <b>${p[0].data} loans</b>` },
        xAxis: { type: 'category', data: this.pdDist.bins, axisLabel: { color: '#64748b', rotate: 30, interval: 3, fontSize: 10 } },
        yAxis: { type: 'value', axisLabel: { color: '#64748b' } },
        series: [{ type: 'bar', data: this.pdDist.counts,
          itemStyle: { color: (p: any) => {
            const idx = p.dataIndex / this.pdDist.bins.length;
            return idx > 0.6 ? '#ef4444' : idx > 0.3 ? '#f59e0b' : '#10b981';
          }, borderRadius: [3,3,0,0] },
        }],
        backgroundColor: 'transparent',
      };
    }

    // Portfolio by product — grouped bars
    if (this.byProduct.length) {
      this.productOpts = {
        tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
        legend: { data: ['Loan Volume','Default Rate %','Avg Score'], textStyle: { color: '#94a3b8' } },
        xAxis: { type: 'category', data: this.byProduct.map(p => p.product.replace(/_/g,' ')),
                 axisLabel: { color: '#64748b', rotate: 15, fontSize: 11 } },
        yAxis: [
          { type: 'value', name: 'Loans', axisLabel: { color: '#64748b' } },
          { type: 'value', name: 'Rate/Score', axisLabel: { color: '#64748b' } },
        ],
        series: [
          { name: 'Loan Volume',   type: 'bar', data: this.byProduct.map(p => p.total_loans), itemStyle: { color: '#3b82f6', borderRadius: [4,4,0,0] }, yAxisIndex: 0 },
          { name: 'Default Rate %', type: 'line', smooth: true, data: this.byProduct.map(p => +(p.default_rate*100).toFixed(2)), itemStyle: { color: '#ef4444' }, yAxisIndex: 1 },
          { name: 'Avg Score',     type: 'line', smooth: true, data: this.byProduct.map(p => +(p.avg_score||0).toFixed(0)), itemStyle: { color: '#10b981' }, yAxisIndex: 1 },
        ],
        backgroundColor: 'transparent',
      };
    }

    // Country donut
    if (this.byCountry.length) {
      const colors = ['#3b82f6','#10b981','#f59e0b','#8b5cf6'];
      this.countryOpts = {
        tooltip: { trigger: 'item', formatter: '{b}: {c} loans ({d}%)' },
        legend: { bottom: 0, textStyle: { color: '#94a3b8' } },
        series: [{ type: 'pie', radius: ['42%','70%'], center: ['50%','44%'],
          data: this.byCountry.map((c, i) => ({ name: c.country, value: c.total_loans, itemStyle: { color: colors[i] } })),
          label: { color: '#94a3b8', formatter: '{b}\n{d}%' },
          emphasis: { itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,.3)' } },
        }],
        backgroundColor: 'transparent',
      };
    }

    // Score heatmap
    if (this.heatmap?.matrix?.length) {
      const data = this.heatmap.matrix.map((m: any) => [m.emp_idx, m.age_idx, m.avg_score||0]);
      this.heatmapOpts = {
        tooltip: { formatter: (p: any) => {
          const emp = this.heatmap.employment?.[p.data[0]];
          const age = this.heatmap.age_groups?.[p.data[1]];
          return `${emp} · ${age}<br/>Avg Score: <b>${p.data[2]}</b>`;
        }},
        xAxis: { type: 'category', data: this.heatmap.employment || [], axisLabel: { color: '#64748b' } },
        yAxis: { type: 'category', data: this.heatmap.age_groups  || [], axisLabel: { color: '#64748b' } },
        visualMap: { min: 550, max: 800, calculable: true, orient: 'horizontal',
                     left: 'center', bottom: 0,
                     inRange: { color: ['#ef4444','#f59e0b','#10b981'] },
                     textStyle: { color: '#94a3b8' } },
        series: [{ type: 'heatmap', data,
                   label: { show: true, fontSize: 10, color: '#fff' } }],
        backgroundColor: 'transparent',
      };
    }

    // KS/Gini CAP curve
    if (this.ksGini?.curve?.length) {
      this.ksCapOpts = {
        tooltip: { trigger: 'axis' },
        legend: { data: ['Credit Score Model','Random','Perfect'], textStyle: { color: '#94a3b8' } },
        xAxis: { type: 'value', name: '% Population', min: 0, max: 100, axisLabel: { color: '#64748b', formatter: '{value}%' } },
        yAxis: { type: 'value', name: '% Defaults Captured', min: 0, max: 100, axisLabel: { color: '#64748b', formatter: '{value}%' } },
        series: [
          { name: 'Credit Score Model', type: 'line', smooth: true, showSymbol: false,
            data: this.ksGini.curve.map((p: any) => [p.pct_population, p.cum_bad_rate*100]),
            itemStyle: { color: '#3b82f6' }, areaStyle: { opacity: .2 },
            lineStyle: { width: 2.5 } },
          { name: 'Random',  type: 'line', data: [[0,0],[100,100]], itemStyle: { color: '#94a3b8' }, lineStyle: { type: 'dashed' }, showSymbol: false },
          { name: 'Perfect', type: 'line', data: [[0,0],[20,100],[100,100]], itemStyle: { color: '#10b981' }, lineStyle: { type: 'dashed' }, showSymbol: false },
        ],
        backgroundColor: 'transparent',
      };
    }

    // FPD by score band
    if (fpdBand.length) {
      this.fpdBandOpts = {
        tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
        legend: { data: ['FPD Rate %','Total Loans'], textStyle: { color: '#94a3b8' } },
        xAxis: { type: 'category', data: fpdBand.map((b: any) => b.band), axisLabel: { color: '#64748b', rotate: 12, fontSize: 11 } },
        yAxis: [
          { type: 'value', name: 'FPD Rate %', axisLabel: { color: '#64748b', formatter: '{value}%' } },
          { type: 'value', name: 'Loans', axisLabel: { color: '#64748b' } },
        ],
        series: [
          { name: 'FPD Rate %', type: 'line', smooth: true,
            data: fpdBand.map((b: any) => +(b.fpd_rate*100).toFixed(2)),
            itemStyle: { color: '#ef4444' }, lineStyle: { width: 2.5 },
            areaStyle: { opacity: 0.15 }, yAxisIndex: 0,
            label: { show: true, position: 'top', fontSize: 10, color: '#ef4444', formatter: (p: any) => p.data + '%' } },
          { name: 'Total Loans', type: 'bar', data: fpdBand.map((b: any) => b.total),
            itemStyle: { color: '#3b82f6', opacity: 0.6, borderRadius: [3,3,0,0] }, yAxisIndex: 1 },
        ],
        backgroundColor: 'transparent',
      };
    }

    // Credit utilization
    if (this.bureau?.utilization?.labels?.length) {
      const u = this.bureau.utilization;
      this.utilizationOpts = {
        tooltip: { trigger: 'axis' },
        xAxis: { type: 'category', data: u.labels, axisLabel: { color: '#64748b', rotate: 30, fontSize: 10 } },
        yAxis: { type: 'value', axisLabel: { color: '#64748b' } },
        series: [{ type: 'bar', data: u.counts, itemStyle: { color: '#8b5cf6', borderRadius: [3,3,0,0] }, barMaxWidth: 28 }],
        backgroundColor: 'transparent',
      };
    }

    // DTI
    if (this.bureau?.dti?.labels?.length) {
      const d = this.bureau.dti;
      this.dtiOpts = {
        tooltip: { trigger: 'axis' },
        xAxis: { type: 'category', data: d.labels, axisLabel: { color: '#64748b', rotate: 30, fontSize: 10 } },
        yAxis: { type: 'value', axisLabel: { color: '#64748b' } },
        series: [{ type: 'bar', data: d.counts, itemStyle: { color: '#f59e0b', borderRadius: [3,3,0,0] }, barMaxWidth: 28 }],
        backgroundColor: 'transparent',
      };
    }

    // Hard inquiries
    if (this.bureau?.hard_inquiries?.labels?.length) {
      const h = this.bureau.hard_inquiries;
      this.inquiryOpts = {
        tooltip: { trigger: 'axis' },
        xAxis: { type: 'category', data: h.labels, axisLabel: { color: '#64748b' } },
        yAxis: { type: 'value', axisLabel: { color: '#64748b' } },
        series: [{ type: 'bar', data: h.counts, itemStyle: { color: '#ef4444', borderRadius: [3,3,0,0] }, barMaxWidth: 28 }],
        backgroundColor: 'transparent',
      };
    }

    // Delinquent accounts
    if (this.bureau?.delinquent_accounts?.labels?.length) {
      const d = this.bureau.delinquent_accounts;
      const colors = ['#10b981','#f59e0b','#f97316','#ef4444'];
      this.delinquencyOpts = {
        tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
        legend: { bottom: 0, textStyle: { color: '#94a3b8' } },
        series: [{ type: 'pie', radius: ['38%','62%'],
          data: d.labels.map((l: string, i: number) => ({ name: l + ' delinquent', value: d.counts[i], itemStyle: { color: colors[i] } })),
          label: { color: '#94a3b8', fontSize: 11 } }],
        backgroundColor: 'transparent',
      };
    }

    // Portfolio trend
    if (this.portfolioTrend?.months?.length) {
      const m = this.portfolioTrend;
      this.trendOpts = {
        tooltip: { trigger: 'axis' },
        legend: { data: ['Loan Volume','Default Rate %','Avg Score'], textStyle: { color: '#94a3b8' } },
        xAxis: { type: 'category', data: m.months, axisLabel: { color: '#64748b', rotate: 20, interval: 2, fontSize: 10 } },
        yAxis: [
          { type: 'value', name: 'Volume/Score', axisLabel: { color: '#64748b' } },
          { type: 'value', name: 'Default %', axisLabel: { color: '#64748b', formatter: '{value}%' } },
        ],
        series: [
          { name: 'Loan Volume', type: 'bar', data: m.loan_volumes, itemStyle: { color: '#3b82f6', opacity: .7 }, yAxisIndex: 0 },
          { name: 'Default Rate %', type: 'line', data: m.default_rates, smooth: true, itemStyle: { color: '#ef4444' }, yAxisIndex: 1, lineStyle: { width: 2 } },
          { name: 'Avg Score', type: 'line', data: m.avg_scores, smooth: true, itemStyle: { color: '#10b981' }, yAxisIndex: 0, lineStyle: { width: 2, type: 'dashed' } },
        ],
        backgroundColor: 'transparent',
      };
    }

    // Roll rate buckets
    if (this.rollRates?.buckets?.length) {
      const bkts = this.rollRates.buckets.filter((b: string) => b !== 'Paid');
      const colors = ['#10b981','#3b82f6','#f59e0b','#f97316','#ef4444','#7c3aed'];
      this.rollOpts = {
        tooltip: { trigger: 'item', formatter: '{b}: {c} loans ({d}%)' },
        legend: { bottom: 0, textStyle: { color: '#94a3b8' }, type: 'scroll' },
        series: [{ type: 'pie', radius: ['35%','65%'],
          data: bkts.map((b: string, i: number) => ({
            name: b, value: this.rollRates.counts[b] || 0,
            itemStyle: { color: colors[i % colors.length] },
          })),
          label: { color: '#94a3b8', fontSize: 10 },
          emphasis: { itemStyle: { shadowBlur: 10 } },
        }],
        backgroundColor: 'transparent',
      };
    }

    // PD vs score scatter (from score band stats in ks)
    if (this.ksGini?.band_stats?.length) {
      const bs = this.ksGini.band_stats;
      const scoreColors = ['#ef4444','#f97316','#f59e0b','#3b82f6','#10b981'];
      this.pdHeatmapOpts = {
        tooltip: { formatter: (p: any) => `${p.data[2]}<br/>Default Rate: <b>${(p.data[1]*100).toFixed(1)}%</b><br/>Count: ${p.data[3]}` },
        xAxis: { type: 'category', data: bs.map((b: any) => b.band), axisLabel: { color: '#64748b', fontSize: 11 } },
        yAxis: { type: 'value', name: 'Default Rate %', axisLabel: { color: '#64748b', formatter: '{value}%' } },
        series: [{ type: 'bar', data: bs.map((b: any, i: number) => ({
          value: +(b.default_rate*100).toFixed(2),
          itemStyle: { color: scoreColors[i] || '#3b82f6', borderRadius: [4,4,0,0] },
        })),
          label: { show: true, position: 'top', color: '#94a3b8', fontSize: 11, formatter: (p: any) => p.data.value + '%' },
        }],
        backgroundColor: 'transparent',
      };
    }
  }

  scoreColor(s: number): string {
    if (s >= 750) return '#10b981';
    if (s >= 700) return '#3b82f6';
    if (s >= 650) return '#f59e0b';
    if (s >= 600) return '#f97316';
    return '#ef4444';
  }

  scoreGrade(s: number): string {
    if (s >= 750) return 'grade-a';
    if (s >= 700) return 'grade-b';
    if (s >= 650) return 'grade-c';
    if (s >= 600) return 'grade-d';
    return 'grade-e';
  }

  scoreLabel(s: number): string {
    if (s >= 750) return 'Excellent'; if (s >= 700) return 'Good';
    if (s >= 650) return 'Fair'; if (s >= 600) return 'Poor'; return 'Very Poor';
  }

  fmtKES(n: number): string {
    if (!n) return '—';
    if (n >= 1e9) return (n/1e9).toFixed(1)+'B';
    if (n >= 1e6) return (n/1e6).toFixed(1)+'M';
    if (n >= 1e3) return (n/1e3).toFixed(1)+'K';
    return n.toFixed(0);
  }

  fmtNum(n: number): string {
    if (n >= 1e3) return (n/1e3).toFixed(1)+'K';
    return String(n);
  }
}
