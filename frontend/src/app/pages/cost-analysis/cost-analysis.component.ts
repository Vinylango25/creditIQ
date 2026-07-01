import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { forkJoin, of } from 'rxjs';
import { catchError } from 'rxjs/operators';
import { ApiService } from '../../core/api.service';
import { ChartComponent } from '../../shared/chart/chart.component';

@Component({
  selector: 'app-cost-analysis',
  standalone: true,
  imports: [CommonModule, FormsModule, ChartComponent],
  templateUrl: './cost-analysis.component.html',
  styleUrls: ['./cost-analysis.component.scss'],
})
export class CostAnalysisComponent implements OnInit {
  loading = true;
  summary: any = {};
  periods: any[] = [];
  waterfall: any = {};
  roiTrend: any = {};
  breakdown: any = {};

  // Charts
  roiOpts: any = {};
  savingsOpts: any = {};
  defaultCompareOpts: any = {};
  breakdownOpts: any = {};
  waterfallOpts: any = {};

  // Scenario simulator
  scenario: any = {};
  sim = {
    monthly_loans: 1000,
    avg_loan_kes: 8500,
    baseline_dr: 0.18,
    model_dr: 0.095,
    lgd: 0.55,
    fraud_pct_of_default: 0.22,
    model_cost_per_loan: 2.50,
    manual_review_pct: 0.15,
  };

  constructor(private api: ApiService) {}

  ngOnInit(): void {
    forkJoin({
      summary:   this.api.getCostSummary()   .pipe(catchError(() => of({}))),
      periods:   this.api.getCostByPeriod()  .pipe(catchError(() => of([]))),
      waterfall: this.api.getCostWaterfall() .pipe(catchError(() => of({}))),
      roi:       this.api.getCostROITrend()  .pipe(catchError(() => of({}))),
      breakdown: this.api.getCostBreakdown() .pipe(catchError(() => of({}))),
    }).subscribe({
      next: (r: any) => {
        this.summary   = r.summary   || {};
        this.periods   = Array.isArray(r.periods) ? r.periods : [];
        this.waterfall = r.waterfall || {};
        this.roiTrend  = r.roi       || {};
        this.breakdown = r.breakdown || {};
        this.buildCharts();
        this.runScenario();
        this.loading = false;
      },
      error: () => { this.loading = false; }
    });
  }

  runScenario(): void {
    this.api.getCostScenario(this.sim)
      .pipe(catchError(() => of({})))
      .subscribe((r: any) => { this.scenario = r || {}; });
  }

  private buildCharts(): void {
    // ROI trend
    if (this.roiTrend?.periods?.length) {
      this.roiOpts = {
        tooltip: { trigger: 'axis' },
        legend:  { data: ['ROI %', 'Net Benefit (KES)'], textStyle: { color: '#94a3b8' } },
        xAxis:   { type: 'category', data: this.roiTrend.periods, axisLabel: { color: '#64748b', rotate: 20, fontSize: 10 } },
        yAxis:   [
          { type: 'value', name: 'ROI %',         axisLabel: { color: '#64748b', formatter: '{value}%' } },
          { type: 'value', name: 'Net Benefit',   axisLabel: { color: '#64748b' } },
        ],
        series:  [
          { name: 'ROI %',          type: 'line', data: this.roiTrend.roi_pct,         smooth: true, itemStyle: { color: '#10b981' }, yAxisIndex: 0, areaStyle: { opacity: 0.15 } },
          { name: 'Net Benefit (KES)', type: 'bar', data: this.roiTrend.net_benefit_kes, itemStyle: { color: '#3b82f6', opacity: 0.7 }, yAxisIndex: 1 },
        ],
        backgroundColor: 'transparent',
      };
    }

    // Savings waterfall
    if (this.waterfall?.items?.length) {
      const items = this.waterfall.items;
      const colors: Record<string, string> = {
        total:   '#64748b',
        saving:  '#10b981',
        cost:    '#ef4444',
        net:     '#3b82f6',
      };
      this.waterfallOpts = {
        tooltip: { trigger: 'axis', formatter: (p: any) => `${p[0].name}: <b>KES ${this.fmtKES(Math.abs(p[0].data))}</b>` },
        xAxis:   { type: 'category', data: items.map((i: any) => i.label), axisLabel: { color: '#64748b', rotate: 15, fontSize: 10 } },
        yAxis:   { type: 'value', axisLabel: { color: '#64748b' } },
        series:  [{
          type: 'bar',
          data: items.map((i: any) => ({
            value: Math.abs(i.value),
            itemStyle: { color: colors[i.type] || '#64748b' },
          })),
          label: { show: true, position: 'top', color: '#94a3b8', fontSize: 10,
                   formatter: (p: any) => this.fmtKES(p.value) },
        }],
        backgroundColor: 'transparent',
      };
    }

    // Default rate comparison baseline vs model
    if (this.periods.length) {
      this.defaultCompareOpts = {
        tooltip: { trigger: 'axis' },
        legend:  { data: ['Baseline Default Rate %', 'Model Default Rate %'], textStyle: { color: '#94a3b8' } },
        xAxis:   { type: 'category', data: this.periods.map(p => p.period), axisLabel: { color: '#64748b', rotate: 20, fontSize: 10 } },
        yAxis:   { type: 'value', axisLabel: { color: '#64748b', formatter: '{value}%' } },
        series:  [
          { name: 'Baseline Default Rate %', type: 'line', data: this.periods.map(p => +(p.baseline_default_rate*100).toFixed(2)), smooth: true, itemStyle: { color: '#ef4444' }, lineStyle: { type: 'dashed' } },
          { name: 'Model Default Rate %',    type: 'line', data: this.periods.map(p => +(p.model_default_rate*100).toFixed(2)),    smooth: true, itemStyle: { color: '#10b981' }, areaStyle: { opacity: 0.15 } },
        ],
        backgroundColor: 'transparent',
      };
    }

    // Savings stacked bar
    if (this.periods.length) {
      this.savingsOpts = {
        tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
        legend:  { data: ['Credit Loss Saved','Fraud Loss Saved','Ops Saved'], textStyle: { color: '#94a3b8' } },
        xAxis:   { type: 'category', data: this.periods.map(p => p.period), axisLabel: { color: '#64748b', rotate: 20, fontSize: 10 } },
        yAxis:   { type: 'value', axisLabel: { color: '#64748b' } },
        series:  [
          { name: 'Credit Loss Saved', type: 'bar', stack: 'savings', data: this.periods.map(p => p.credit_saved_kes), itemStyle: { color: '#ef4444' } },
          { name: 'Fraud Loss Saved',  type: 'bar', stack: 'savings', data: this.periods.map(p => p.fraud_saved_kes),  itemStyle: { color: '#f97316' } },
          { name: 'Ops Saved',         type: 'bar', stack: 'savings', data: this.periods.map(p => p.ops_saved_kes),    itemStyle: { color: '#f59e0b' } },
        ],
        backgroundColor: 'transparent',
      };
    }

    // Cost breakdown donuts
    if (this.breakdown?.baseline?.length) {
      const bColors = ['#ef4444','#f97316','#f59e0b'];
      const mColors = ['#dc2626','#ea580c','#d97706','#8b5cf6'];
      this.breakdownOpts = {
        tooltip: { trigger: 'item', formatter: '{b}: KES {c} ({d}%)' },
        legend:  { bottom: 0, textStyle: { color: '#94a3b8' } },
        series:  [
          { name: 'Baseline', type: 'pie', radius: ['20%','45%'], center: ['30%','45%'],
            data: this.breakdown.baseline.map((d: any, i: number) => ({ ...d, itemStyle: { color: bColors[i] } })),
            label: { color: '#94a3b8', fontSize: 10 }, title: { text: 'Baseline', left: '20%', top: '80%' } },
          { name: 'With Model', type: 'pie', radius: ['20%','45%'], center: ['70%','45%'],
            data: this.breakdown.model.map((d: any, i: number) => ({ ...d, itemStyle: { color: mColors[i] } })),
            label: { color: '#94a3b8', fontSize: 10 } },
        ],
        backgroundColor: 'transparent',
      };
    }
  }

  fmtKES(n: number): string {
    if (!n) return '0';
    if (n >= 1_000_000_000) return (n / 1_000_000_000).toFixed(1) + 'B';
    if (n >= 1_000_000)     return (n / 1_000_000).toFixed(1) + 'M';
    if (n >= 1_000)         return (n / 1_000).toFixed(1) + 'K';
    return n.toFixed(0);
  }

  roiClass(roi: number): string {
    if (roi >= 300) return 'kpi-card--success';
    if (roi >= 100) return 'kpi-card--info';
    return 'kpi-card--warning';
  }
}
