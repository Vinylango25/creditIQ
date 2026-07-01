import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { forkJoin, of } from 'rxjs';
import { catchError } from 'rxjs/operators';
import { ApiService } from '../../core/api.service';
import { ChartComponent } from '../../shared/chart/chart.component';

@Component({
  selector: 'app-vintage-analysis',
  standalone: true,
  imports: [CommonModule, ChartComponent],
  templateUrl: './vintage-analysis.component.html',
  styleUrls: ['./vintage-analysis.component.scss'],
})
export class VintageAnalysisComponent implements OnInit {
  loading = true;
  vintage: any = {};
  rollRates: any = {};
  expectedLoss: any[] = [];

  vintageOpts: any = {};
  rollMatrixOpts: any = {};
  elBarOpts: any = {};
  pdLgdOpts: any = {};

  // Table data
  elTable: any[] = [];

  constructor(private api: ApiService) {}

  ngOnInit(): void {
    forkJoin({
      vintage: this.api.getVintageCurves()   .pipe(catchError(() => of({}))),
      roll:    this.api.getRollRates()        .pipe(catchError(() => of({}))),
      el:      this.api.getExpectedLoss()     .pipe(catchError(() => of([]))),
    }).subscribe({
      next: (r: any) => {
        this.vintage      = r.vintage || {};
        this.rollRates    = r.roll    || {};
        this.elTable      = Array.isArray(r.el) ? r.el : [];
        this.expectedLoss = this.elTable;
        this.buildCharts();
        this.loading = false;
      },
      error: () => { this.loading = false; }
    });
  }

  private buildCharts(): void {
    // Vintage curves — one line per cohort
    if (this.vintage?.cohorts?.length && this.vintage?.mobs?.length) {
      const palette = [
        '#3b82f6','#10b981','#f59e0b','#ef4444','#8b5cf6',
        '#06b6d4','#f97316','#84cc16','#ec4899','#14b8a6',
        '#a78bfa','#fb923c','#34d399',
      ];
      const series = this.vintage.cohorts.map((cohort: string, i: number) => ({
        name: cohort,
        type: 'line',
        smooth: true,
        showSymbol: false,
        data: this.vintage.series[cohort],
        itemStyle: { color: palette[i % palette.length] },
      }));

      this.vintageOpts = {
        tooltip: { trigger: 'axis', formatter: (params: any[]) => {
          const mob = params[0]?.axisValue;
          let html = `<b>MOB ${mob}</b><br/>`;
          params.forEach(p => {
            if (p.value != null)
              html += `${p.marker}${p.seriesName}: <b>${p.value}%</b><br/>`;
          });
          return html;
        }},
        legend: { type: 'scroll', bottom: 0, textStyle: { color: '#94a3b8' }, pageTextStyle: { color: '#94a3b8' } },
        xAxis:  { type: 'category', data: this.vintage.mobs.map((m: number) => `MOB ${m}`),
                  axisLabel: { color: '#64748b' }, name: 'Months on Book', nameLocation: 'middle', nameGap: 28 },
        yAxis:  { type: 'value', name: 'Cumulative Default Rate %',
                  axisLabel: { color: '#64748b', formatter: '{value}%' } },
        series,
        grid: { bottom: '15%' },
        backgroundColor: 'transparent',
      };
    }

    // Roll rate transition matrix as heatmap
    if (this.rollRates?.roll_matrix) {
      const buckets = ['Current','1-7 DPD','8-30 DPD','31-60 DPD','60+ DPD'];
      const data: any[] = [];
      buckets.forEach((from, fi) => {
        const row = this.rollRates.roll_matrix[from] || {};
        buckets.forEach((to, ti) => {
          const val = (row[to] || 0) * 100;
          data.push([ti, fi, +val.toFixed(1)]);
        });
      });

      this.rollMatrixOpts = {
        tooltip: { formatter: (p: any) => `${buckets[p.data[1]]} → ${buckets[p.data[0]]}: <b>${p.data[2]}%</b>` },
        xAxis:   { type: 'category', data: buckets, name: 'To State',   axisLabel: { color: '#64748b', rotate: 20, fontSize: 11 } },
        yAxis:   { type: 'category', data: buckets, name: 'From State', axisLabel: { color: '#64748b', fontSize: 11 } },
        visualMap: { min: 0, max: 100, calculable: true, orient: 'horizontal', left: 'center', bottom: 0,
                     inRange: { color: ['#1e293b','#3b82f6','#10b981'] }, textStyle: { color: '#94a3b8' } },
        series: [{ type: 'heatmap', data, label: { show: true, fontSize: 10, formatter: (p: any) => p.data[2] + '%' } }],
        grid: { bottom: '18%' },
        backgroundColor: 'transparent',
      };
    }

    // EL bar by cohort
    if (this.elTable.length) {
      this.elBarOpts = {
        tooltip: { trigger: 'axis' },
        legend:  { data: ['Disbursed (KES)', 'Expected Loss (KES)'], textStyle: { color: '#94a3b8' } },
        xAxis:   { type: 'category', data: this.elTable.map(r => r.cohort), axisLabel: { color: '#64748b', rotate: 15 } },
        yAxis:   { type: 'value', axisLabel: { color: '#64748b' } },
        series:  [
          { name: 'Disbursed (KES)',      type: 'bar', data: this.elTable.map(r => r.disbursed_kes),  itemStyle: { color: '#3b82f6', opacity: 0.7 } },
          { name: 'Expected Loss (KES)', type: 'bar', data: this.elTable.map(r => r.total_el_kes),   itemStyle: { color: '#ef4444', opacity: 0.85 } },
        ],
        backgroundColor: 'transparent',
      };

      // PD vs LGD scatter
      this.pdLgdOpts = {
        tooltip: { formatter: (p: any) => `${p.data[3]}<br/>PD: ${(p.data[0]*100).toFixed(1)}%<br/>LGD: ${(p.data[1]*100).toFixed(1)}%<br/>EL Rate: ${(p.data[2]*100).toFixed(2)}%` },
        xAxis:   { type: 'value', name: 'Avg PD', axisLabel: { color: '#64748b', formatter: (v: number) => (v*100).toFixed(0)+'%' } },
        yAxis:   { type: 'value', name: 'Avg LGD', axisLabel: { color: '#64748b', formatter: (v: number) => (v*100).toFixed(0)+'%' } },
        series:  [{
          type: 'scatter',
          symbolSize: (d: any) => Math.max(8, d[2] * 400),
          data: this.elTable.map(r => [r.avg_pd, r.avg_lgd, r.el_rate, r.cohort]),
          itemStyle: { color: (p: any) => {
            const el = p.data[2];
            return el > 0.08 ? '#ef4444' : el > 0.04 ? '#f59e0b' : '#10b981';
          }, opacity: 0.8 },
          label: { show: true, formatter: (p: any) => p.data[3], fontSize: 10, color: '#94a3b8' },
        }],
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

  elRateClass(rate: number): string {
    if (rate > 0.08) return 'badge--danger';
    if (rate > 0.04) return 'badge--warning';
    return 'badge--success';
  }
}
