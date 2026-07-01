import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { forkJoin, of } from 'rxjs';
import { catchError } from 'rxjs/operators';
import { ApiService } from '../../core/api.service';
import { ChartComponent } from '../../shared/chart/chart.component';

@Component({
  selector: 'app-fpd-analysis',
  standalone: true,
  imports: [CommonModule, ChartComponent],
  templateUrl: './fpd-analysis.component.html',
  styleUrls: ['./fpd-analysis.component.scss'],
})
export class FpdAnalysisComponent implements OnInit {
  loading = true;
  fpdSummary: any = {};
  fpdTrend: any = {};
  fpdByScoreBand: any[] = [];

  trendOpts: any = {};
  scoreBandOpts: any = {};
  bucketOpts: any = {};
  gaugeOpts: any = {};

  constructor(private api: ApiService) {}

  ngOnInit(): void {
    forkJoin({
      summary:     this.api.getFpdSummary()      .pipe(catchError(() => of({}))),
      trend:       this.api.getFpdTrend()         .pipe(catchError(() => of({}))),
      scoreBand:   this.api.getFpdByScoreBand()   .pipe(catchError(() => of([]))),
    }).subscribe({
      next: (r: any) => {
        this.fpdSummary     = r.summary   || {};
        this.fpdTrend       = r.trend     || {};
        this.fpdByScoreBand = Array.isArray(r.scoreBand) ? r.scoreBand : [];
        this.buildCharts();
        this.loading = false;
      },
      error: () => { this.loading = false; }
    });
  }

  private buildCharts(): void {
    // FPD rate gauge
    const fpdPct = (this.fpdSummary.fpd_pct || 0);
    this.gaugeOpts = {
      series: [{
        type: 'gauge',
        startAngle: 200, endAngle: -20,
        min: 0, max: 30,
        pointer: { show: true },
        progress: { show: true, width: 12 },
        axisLine: { lineStyle: { width: 12 } },
        axisTick: { show: false },
        splitLine: { length: 12, lineStyle: { width: 2, color: '#4a5568' } },
        axisLabel: { color: '#94a3b8', fontSize: 10 },
        detail: { valueAnimation: true, fontSize: 28, fontWeight: 700, color: fpdPct > 15 ? '#ef4444' : fpdPct > 8 ? '#f59e0b' : '#10b981',
                  formatter: '{value}%', offsetCenter: [0, '30%'] },
        title: { offsetCenter: [0, '55%'], color: '#94a3b8', fontSize: 12 },
        data: [{ value: +fpdPct.toFixed(2), name: 'FPD Rate' }],
        itemStyle: { color: fpdPct > 15 ? '#ef4444' : fpdPct > 8 ? '#f59e0b' : '#10b981' },
      }],
      backgroundColor: 'transparent',
    };

    // FPD trend
    if (this.fpdTrend?.cohorts?.length) {
      this.trendOpts = {
        tooltip: { trigger: 'axis' },
        legend: { data: ['FPD Rate %', 'Volume'], textStyle: { color: '#94a3b8' } },
        xAxis:  { type: 'category', data: this.fpdTrend.cohorts, axisLabel: { color: '#64748b', rotate: 15 } },
        yAxis:  [
          { type: 'value', name: 'FPD Rate %', axisLabel: { color: '#64748b', formatter: '{value}%' } },
          { type: 'value', name: 'Volume',     axisLabel: { color: '#64748b' } },
        ],
        series: [
          { name: 'FPD Rate %', type: 'line', data: this.fpdTrend.fpd_rates, smooth: true,
            areaStyle: { opacity: 0.2 }, itemStyle: { color: '#ef4444' }, yAxisIndex: 0 },
          { name: 'Volume', type: 'bar', data: this.fpdTrend.volumes, itemStyle: { color: '#3b82f6', opacity: 0.5 }, yAxisIndex: 1 },
        ],
        backgroundColor: 'transparent',
      };
    }

    // FPD by score band
    if (this.fpdByScoreBand.length) {
      const colors = ['#ef4444','#f97316','#f59e0b','#10b981','#3b82f6'];
      this.scoreBandOpts = {
        tooltip: { trigger: 'axis' },
        legend: { data: ['Total Loans', 'FPD Count', 'FPD Rate %'], textStyle: { color: '#94a3b8' } },
        xAxis:  { type: 'category', data: this.fpdByScoreBand.map((b: any) => b.band), axisLabel: { color: '#64748b', rotate: 15, fontSize: 11 } },
        yAxis:  [
          { type: 'value', name: 'Count',    axisLabel: { color: '#64748b' } },
          { type: 'value', name: 'FPD Rate', axisLabel: { color: '#64748b', formatter: '{value}%' } },
        ],
        series: [
          { name: 'Total Loans', type: 'bar', data: this.fpdByScoreBand.map((b: any) => b.total),     itemStyle: { color: '#3b82f6', opacity: 0.6 }, yAxisIndex: 0 },
          { name: 'FPD Count',   type: 'bar', data: this.fpdByScoreBand.map((b: any) => b.fpd_count), itemStyle: { color: '#ef4444', opacity: 0.8 }, yAxisIndex: 0 },
          { name: 'FPD Rate %',  type: 'line', data: this.fpdByScoreBand.map((b: any) => +(b.fpd_rate*100).toFixed(2)),
            itemStyle: { color: '#f59e0b' }, yAxisIndex: 1, smooth: true,
            label: { show: true, position: 'top', fontSize: 11, color: '#f59e0b', formatter: (p: any) => p.data + '%' } },
        ],
        backgroundColor: 'transparent',
      };
    }

    // Bucket donut (FPD severity buckets)
    if (this.fpdSummary?.by_bucket) {
      const buckets = Object.entries(this.fpdSummary.by_bucket)
        .map(([k, v]) => ({ name: k, value: v as number }));
      const colors = ['#f97316','#ef4444','#dc2626','#7c3aed'];
      this.bucketOpts = {
        tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
        legend:  { bottom: 0, textStyle: { color: '#94a3b8' } },
        series: [{
          type: 'pie', radius: ['40%','65%'],
          data: buckets.map((b, i) => ({ ...b, itemStyle: { color: colors[i % colors.length] } })),
          label: { color: '#94a3b8', fontSize: 11 },
        }],
        backgroundColor: 'transparent',
      };
    }
  }
}
