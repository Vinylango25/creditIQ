import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { forkJoin, of } from 'rxjs';
import { catchError } from 'rxjs/operators';
import { ApiService } from '../../core/api.service';
import { ChartComponent } from '../../shared/chart/chart.component';

@Component({
  selector: 'app-risk-analytics',
  standalone: true,
  imports: [CommonModule, ChartComponent],
  templateUrl: './risk-analytics.component.html',
  styleUrls: ['./risk-analytics.component.scss'],
})
export class RiskAnalyticsComponent implements OnInit {
  loading = true;

  ksGini:       any = {};
  psiDrift:     any[] = [];
  expectedLoss: any[] = [];
  rollRates:    any = {};
  portTrend:    any = {};
  riskSegment:  any = {};
  fpd:          any = {};
  fpdTrend:     any = {};
  fpdBand:      any[] = [];
  creditSum:    any = {};
  vintage:      any = {};

  // Charts
  ksOpts:       any = {};
  psiOpts:      any = {};
  elOpts:       any = {};
  rollMatrixOpts:any = {};
  rollDonutOpts: any = {};
  trendOpts:    any = {};
  segmentOpts:  any = {};
  fpdGaugeOpts: any = {};
  fpdTrendOpts: any = {};
  fpdBandOpts:  any = {};
  vintageOpts:  any = {};
  elScatterOpts:any = {};

  constructor(private api: ApiService) {}

  ngOnInit(): void {
    forkJoin({
      ks:       this.api.getKsGini()          .pipe(catchError(() => of({}))),
      psi:      this.api.getPsiDrift()         .pipe(catchError(() => of([]))),
      el:       this.api.getExpectedLoss()     .pipe(catchError(() => of([]))),
      roll:     this.api.getRollRates()        .pipe(catchError(() => of({}))),
      trend:    this.api.getPortfolioTrend()   .pipe(catchError(() => of({}))),
      segment:  this.api.getRiskBySegment()    .pipe(catchError(() => of({}))),
      fpd:      this.api.getFpdSummary()       .pipe(catchError(() => of({}))),
      fpdTrend: this.api.getFpdTrend()         .pipe(catchError(() => of({}))),
      fpdBand:  this.api.getFpdByScoreBand()   .pipe(catchError(() => of([]))),
      credit:   this.api.getCreditSummary()    .pipe(catchError(() => of({}))),
      vintage:  this.api.getVintageCurves()    .pipe(catchError(() => of({}))),
    }).subscribe({
      next: (r: any) => {
        this.ksGini       = r.ks     || {};
        this.psiDrift     = Array.isArray(r.psi) ? r.psi : [];
        this.expectedLoss = Array.isArray(r.el)  ? r.el  : [];
        this.rollRates    = r.roll    || {};
        this.portTrend    = r.trend   || {};
        this.riskSegment  = r.segment || {};
        this.fpd          = r.fpd     || {};
        this.fpdTrend     = r.fpdTrend|| {};
        this.fpdBand      = Array.isArray(r.fpdBand) ? r.fpdBand : [];
        this.creditSum    = r.credit  || {};
        this.vintage      = r.vintage || {};
        this.buildCharts();
        this.loading = false;
      },
      error: () => { this.loading = false; }
    });
  }

  private buildCharts(): void {

    // FPD gauge
    const fpdPct = +(this.fpd.fpd_pct || 0);
    this.fpdGaugeOpts = {
      series: [{
        type: 'gauge', startAngle: 200, endAngle: -20, min: 0, max: 30,
        pointer: { show: true, length: '60%', width: 5 },
        progress: { show: true, width: 12 },
        axisLine: { lineStyle: { width: 12,
          color: [[0.27,'#10b981'],[0.53,'#f59e0b'],[1,'#ef4444']] } },
        axisTick: { show: false },
        splitLine: { length: 12, lineStyle: { width: 2, color: 'var(--border)' } },
        axisLabel: { color: '#94a3b8', fontSize: 10 },
        detail: { valueAnimation: true, fontSize: 26, fontWeight: 800,
                  color: fpdPct > 15 ? '#ef4444' : fpdPct > 8 ? '#f59e0b' : '#10b981',
                  formatter: '{value}%', offsetCenter: [0, '28%'] },
        title: { offsetCenter: [0, '52%'], color: '#94a3b8', fontSize: 11 },
        data: [{ value: +fpdPct.toFixed(2), name: 'FPD Rate' }],
        itemStyle: { color: fpdPct > 15 ? '#ef4444' : fpdPct > 8 ? '#f59e0b' : '#10b981' },
      }],
      backgroundColor: 'transparent',
    };

    // KS CAP curve
    if (this.ksGini?.curve?.length) {
      this.ksOpts = {
        tooltip: { trigger: 'axis' },
        legend: { data: ['Credit Model','Random','Perfect'], textStyle: { color: '#94a3b8' } },
        xAxis: { type: 'value', name: '% Population', min:0, max:100,
                 axisLabel: { color: '#64748b', formatter: '{value}%' } },
        yAxis: { type: 'value', name: '% Defaults', min:0, max:100,
                 axisLabel: { color: '#64748b', formatter: '{value}%' } },
        series: [
          { name: 'Credit Model', type: 'line', smooth: true, showSymbol: false,
            data: this.ksGini.curve.map((p: any) => [p.pct_population, p.cum_bad_rate*100]),
            itemStyle: { color: '#3b82f6' }, areaStyle: { opacity: .18 }, lineStyle: { width: 3 } },
          { name: 'Random',  type: 'line', data: [[0,0],[100,100]], itemStyle: { color: '#94a3b8' }, lineStyle: { type: 'dashed' }, showSymbol: false },
          { name: 'Perfect', type: 'line', data: [[0,0],[18,100],[100,100]], itemStyle: { color: '#10b981' }, lineStyle: { type: 'dashed' }, showSymbol: false },
        ],
        backgroundColor: 'transparent',
      };
    }

    // Roll rate matrix (heatmap)
    if (this.rollRates?.roll_matrix) {
      const buckets = ['Current','1-7 DPD','8-30 DPD','31-60 DPD','60+ DPD'];
      const data: any[] = [];
      buckets.forEach((from, fi) => {
        const row = this.rollRates.roll_matrix[from] || {};
        buckets.forEach((to, ti) => {
          data.push([ti, fi, +((row[to]||0)*100).toFixed(1)]);
        });
      });
      this.rollMatrixOpts = {
        tooltip: { formatter: (p: any) => `${buckets[p.data[1]]} → ${buckets[p.data[0]]}: <b>${p.data[2]}%</b>` },
        xAxis: { type: 'category', data: buckets, name: 'To', axisLabel: { color: '#64748b', rotate: 20, fontSize: 11 } },
        yAxis: { type: 'category', data: buckets, name: 'From', axisLabel: { color: '#64748b', fontSize: 11 } },
        visualMap: { min: 0, max: 100, calculable: true, orient: 'horizontal', left: 'center', bottom: 0,
                     inRange: { color: ['#1e293b','#3b82f6','#10b981'] }, textStyle: { color: '#94a3b8' } },
        series: [{ type: 'heatmap', data,
                   label: { show: true, fontSize: 10, formatter: (p: any) => p.data[2] + '%', color: '#fff' } }],
        grid: { bottom: '20%' },
        backgroundColor: 'transparent',
      };

      // Roll donut
      const bkts = this.rollRates.buckets.filter((b: string) => b !== 'Paid');
      const clrs = ['#10b981','#3b82f6','#f59e0b','#f97316','#ef4444','#7c3aed'];
      this.rollDonutOpts = {
        tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
        legend: { bottom: 0, textStyle: { color: '#94a3b8' } },
        series: [{ type: 'pie', radius: ['38%','65%'],
          data: bkts.map((b: string, i: number) => ({
            name: b, value: this.rollRates.counts[b] || 0, itemStyle: { color: clrs[i] },
          })),
          label: { color: '#94a3b8', fontSize: 10 },
        }],
        backgroundColor: 'transparent',
      };
    }

    // EL by cohort
    if (this.expectedLoss.length) {
      this.elOpts = {
        tooltip: { trigger: 'axis' },
        legend: { data: ['Disbursed','Expected Loss'], textStyle: { color: '#94a3b8' } },
        xAxis: { type: 'category', data: this.expectedLoss.map(r => r.cohort), axisLabel: { color: '#64748b', rotate: 20, fontSize: 10 } },
        yAxis: { type: 'value', axisLabel: { color: '#64748b' } },
        series: [
          { name: 'Disbursed',      type: 'bar', data: this.expectedLoss.map(r => r.disbursed_kes), itemStyle: { color: '#3b82f6', opacity: .7, borderRadius: [3,3,0,0] } },
          { name: 'Expected Loss', type: 'bar', data: this.expectedLoss.map(r => r.total_el_kes),  itemStyle: { color: '#ef4444', opacity: .85, borderRadius: [3,3,0,0] } },
        ],
        backgroundColor: 'transparent',
      };
      // PD vs LGD scatter
      this.elScatterOpts = {
        tooltip: { formatter: (p: any) => `${p.data[3]}<br/>PD: ${(p.data[0]*100).toFixed(1)}%<br/>LGD: ${(p.data[1]*100).toFixed(1)}%<br/>EL: ${(p.data[2]*100).toFixed(2)}%` },
        xAxis: { type: 'value', name: 'Avg PD', axisLabel: { color: '#64748b', formatter: (v: number) => (v*100).toFixed(0)+'%' } },
        yAxis: { type: 'value', name: 'Avg LGD', axisLabel: { color: '#64748b', formatter: (v: number) => (v*100).toFixed(0)+'%' } },
        series: [{ type: 'scatter', symbolSize: (d: any) => Math.max(8, d[2]*400),
          data: this.expectedLoss.map(r => [r.avg_pd, r.avg_lgd, r.el_rate, r.cohort]),
          itemStyle: { color: (p: any) => p.data[2] > 0.08 ? '#ef4444' : p.data[2] > 0.04 ? '#f59e0b' : '#10b981', opacity: .8 },
          label: { show: true, formatter: (p: any) => p.data[3], fontSize: 10, color: '#94a3b8' },
        }],
        backgroundColor: 'transparent',
      };
    }

    // Portfolio trend
    if (this.portTrend?.months?.length) {
      const m = this.portTrend;
      this.trendOpts = {
        tooltip: { trigger: 'axis' },
        legend: { data: ['Loans','Default Rate %','Avg PD %'], textStyle: { color: '#94a3b8' } },
        xAxis: { type: 'category', data: m.months, axisLabel: { color: '#64748b', rotate: 20, interval: 2, fontSize: 10 } },
        yAxis: [
          { type: 'value', name: 'Loans', axisLabel: { color: '#64748b' } },
          { type: 'value', name: '%', axisLabel: { color: '#64748b', formatter: '{value}%' } },
        ],
        series: [
          { name: 'Loans', type: 'bar', data: m.loan_volumes, itemStyle: { color: '#3b82f6', opacity: .7, borderRadius: [3,3,0,0] }, yAxisIndex: 0 },
          { name: 'Default Rate %', type: 'line', data: m.default_rates, smooth: true, itemStyle: { color: '#ef4444' }, yAxisIndex: 1, lineStyle: { width: 2 } },
          { name: 'Avg PD %', type: 'line', data: m.avg_pd.map((v: number) => +(v*100).toFixed(2)), smooth: true, itemStyle: { color: '#f59e0b' }, yAxisIndex: 1, lineStyle: { width: 2, type: 'dashed' } },
        ],
        backgroundColor: 'transparent',
      };
    }

    // Risk by segment
    if (this.riskSegment?.by_employment?.length) {
      const segs = this.riskSegment.by_employment;
      this.segmentOpts = {
        tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
        legend: { data: ['Default Rate %','Avg PD %','Avg Score /10'], textStyle: { color: '#94a3b8' } },
        xAxis: { type: 'category', data: segs.map((s: any) => s.segment), axisLabel: { color: '#64748b' } },
        yAxis: { type: 'value', axisLabel: { color: '#64748b', formatter: '{value}%' } },
        series: [
          { name: 'Default Rate %', type: 'bar', data: segs.map((s: any) => +(s.default_rate*100).toFixed(2)), itemStyle: { color: '#ef4444', borderRadius: [4,4,0,0] } },
          { name: 'Avg PD %',       type: 'bar', data: segs.map((s: any) => +(s.avg_pd*100).toFixed(2)),      itemStyle: { color: '#f59e0b', borderRadius: [4,4,0,0] } },
          { name: 'Avg Score /10',  type: 'line', data: segs.map((s: any) => +(s.avg_score/10).toFixed(1)), smooth: true, itemStyle: { color: '#10b981' }, lineStyle: { width: 2 } },
        ],
        backgroundColor: 'transparent',
      };
    }

    // FPD trend
    if (this.fpdTrend?.cohorts?.length) {
      this.fpdTrendOpts = {
        tooltip: { trigger: 'axis' },
        legend: { data: ['FPD Rate %','Volume'], textStyle: { color: '#94a3b8' } },
        xAxis: { type: 'category', data: this.fpdTrend.cohorts, axisLabel: { color: '#64748b', rotate: 15, fontSize: 10 } },
        yAxis: [
          { type: 'value', name: 'FPD Rate %', axisLabel: { color: '#64748b', formatter: '{value}%' } },
          { type: 'value', name: 'Volume',     axisLabel: { color: '#64748b' } },
        ],
        series: [
          { name: 'FPD Rate %', type: 'line', smooth: true, data: this.fpdTrend.fpd_rates,
            itemStyle: { color: '#ef4444' }, areaStyle: { opacity: .2 }, lineStyle: { width: 2.5 }, yAxisIndex: 0 },
          { name: 'Volume', type: 'bar', data: this.fpdTrend.volumes,
            itemStyle: { color: '#3b82f6', opacity: .5, borderRadius: [3,3,0,0] }, yAxisIndex: 1 },
        ],
        backgroundColor: 'transparent',
      };
    }

    // FPD by score band
    if (this.fpdBand.length) {
      this.fpdBandOpts = {
        tooltip: { trigger: 'axis' },
        legend: { data: ['FPD Rate %','FPD Count'], textStyle: { color: '#94a3b8' } },
        xAxis: { type: 'category', data: this.fpdBand.map((b: any) => b.band), axisLabel: { color: '#64748b', rotate: 12, fontSize: 11 } },
        yAxis: [
          { type: 'value', name: 'Rate %', axisLabel: { color: '#64748b', formatter: '{value}%' } },
          { type: 'value', name: 'Count',  axisLabel: { color: '#64748b' } },
        ],
        series: [
          { name: 'FPD Rate %', type: 'line', smooth: true, data: this.fpdBand.map((b: any) => +(b.fpd_rate*100).toFixed(2)),
            itemStyle: { color: '#ef4444' }, lineStyle: { width: 3 }, areaStyle: { opacity: .15 }, yAxisIndex: 0,
            label: { show: true, position: 'top', fontSize: 10, color: '#ef4444', formatter: (p: any) => p.data + '%' } },
          { name: 'FPD Count', type: 'bar', data: this.fpdBand.map((b: any) => b.fpd_count),
            itemStyle: { color: '#f59e0b', opacity: .7, borderRadius: [3,3,0,0] }, yAxisIndex: 1 },
        ],
        backgroundColor: 'transparent',
      };
    }

    // Vintage curves
    if (this.vintage?.cohorts?.length) {
      const palette = ['#3b82f6','#10b981','#f59e0b','#ef4444','#8b5cf6','#06b6d4','#f97316','#84cc16','#ec4899'];
      this.vintageOpts = {
        tooltip: { trigger: 'axis' },
        legend: { type: 'scroll', bottom: 0, textStyle: { color: '#94a3b8' }, pageTextStyle: { color: '#94a3b8' } },
        xAxis: { type: 'category', data: this.vintage.mobs.map((m: number) => `M${m}`),
                 axisLabel: { color: '#64748b' }, name: 'Months on Book' },
        yAxis: { type: 'value', name: 'Cum. Default Rate %', axisLabel: { color: '#64748b', formatter: '{value}%' } },
        series: this.vintage.cohorts.map((c: string, i: number) => ({
          name: c, type: 'line', smooth: true, showSymbol: false,
          data: this.vintage.series[c], lineStyle: { width: 2 },
          itemStyle: { color: palette[i % palette.length] },
        })),
        grid: { bottom: '18%' },
        backgroundColor: 'transparent',
      };
    }

    // PSI bar
    if (this.psiDrift.length) {
      const sorted = [...this.psiDrift].sort((a, b) => b.psi - a.psi);
      this.psiOpts = {
        tooltip: { trigger: 'axis' },
        xAxis: { type: 'value', axisLabel: { color: '#64748b' } },
        yAxis: { type: 'category', data: sorted.map((r: any) => r.feature), axisLabel: { color: '#64748b', fontSize: 11 } },
        series: [{ type: 'bar', data: sorted.map((r: any) => r.psi), barMaxWidth: 24,
          itemStyle: { color: (p: any) => p.data >= 0.25 ? '#ef4444' : p.data >= 0.1 ? '#f59e0b' : '#10b981', borderRadius: [0,4,4,0] },
          label: { show: true, position: 'right', formatter: (p: any) => p.data.toFixed(3), color: '#94a3b8', fontSize: 10 },
          markLine: { data: [
            { xAxis: 0.1,  lineStyle: { color: '#f59e0b', type: 'dashed' }, label: { formatter: 'Warning', color: '#f59e0b' } },
            { xAxis: 0.25, lineStyle: { color: '#ef4444', type: 'dashed' }, label: { formatter: 'Alert', color: '#ef4444' } },
          ]},
        }],
        grid: { left: '30%', right: '18%', top: '5%', bottom: '5%' },
        backgroundColor: 'transparent',
      };
    }
  }

  psiClass(v: number): string { return v >= 0.25 ? 'badge--danger' : v >= 0.1 ? 'badge--warning' : 'badge--success'; }
  psiLabel(v: number): string { return v >= 0.25 ? 'Alert' : v >= 0.1 ? 'Warning' : 'Stable'; }
  psiDriftSorted(): any[] { return [...this.psiDrift].sort((a,b) => b.psi - a.psi); }
  maxElCohort(): string {
    if (!this.expectedLoss.length) return '—';
    return this.expectedLoss.reduce((a, b) => (a.el_rate||0) > (b.el_rate||0) ? a : b).cohort;
  }
  fmtKES(n: number): string {
    if (!n) return '—';
    if (n >= 1e9) return (n/1e9).toFixed(1)+'B';
    if (n >= 1e6) return (n/1e6).toFixed(1)+'M';
    if (n >= 1e3) return (n/1e3).toFixed(1)+'K';
    return n.toFixed(0);
  }
  totalEL(): number { return this.expectedLoss.reduce((s, r) => s + (r.total_el_kes||0), 0); }
  alertFeatures(): number { return this.psiDrift.filter(p => p.psi >= 0.25).length; }
  warnFeatures():  number { return this.psiDrift.filter(p => p.psi >= 0.1 && p.psi < 0.25).length; }
}
