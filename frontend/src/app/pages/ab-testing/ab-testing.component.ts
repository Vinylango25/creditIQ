import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { forkJoin, of } from 'rxjs';
import { catchError, switchMap } from 'rxjs/operators';
import { ApiService } from '../../core/api.service';
import { ChartComponent } from '../../shared/chart/chart.component';

@Component({
  selector: 'app-ab-testing',
  standalone: true,
  imports: [CommonModule, FormsModule, ChartComponent],
  templateUrl: './ab-testing.component.html',
  styleUrls: ['./ab-testing.component.scss'],
})
export class AbTestingComponent implements OnInit {
  loading = true;
  abSummary: any = {};
  tests: any[] = [];
  selectedTest: any = null;
  liftCurve: any = {};
  powerResult: any = {};

  // Power analysis inputs
  baselineRate  = 0.10;
  minDetectable = 0.02;
  alpha         = 0.05;
  power         = 0.80;

  // Charts
  summaryBarOpts: any = {};
  liftOpts: any = {};
  comparisonOpts: any = {};

  constructor(private api: ApiService) {}

  ngOnInit(): void {
    forkJoin({
      summary: this.api.getABSummary().pipe(catchError(() => of({}))),
      tests:   this.api.getABTests()  .pipe(catchError(() => of([]))),
    }).subscribe({
      next: (r: any) => {
        this.abSummary = r.summary || {};
        this.tests     = Array.isArray(r.tests) ? r.tests : [];
        this.buildSummaryChart();
        if (this.tests.length) {
          this.selectTest(this.tests[0]);
        }
        this.loading = false;
      },
      error: () => { this.loading = false; }
    });
  }

  selectTest(test: any): void {
    this.selectedTest = test;
    this.api.getABCumulativeLift(test.test_id)
      .pipe(catchError(() => of({})))
      .subscribe(curve => {
        this.liftCurve = curve || {};
        this.buildLiftChart();
      });
  }

  runPowerAnalysis(): void {
    this.api.getABPowerAnalysis({
      baseline_rate:  this.baselineRate,
      min_detectable: this.minDetectable,
      alpha:          this.alpha,
      power:          this.power,
    }).pipe(catchError(() => of({}))).subscribe(r => {
      this.powerResult = r || {};
    });
  }

  private buildSummaryChart(): void {
    if (!this.tests.length) return;

    // Comparison bar: control vs treatment default rate per test
    const completedTests = this.tests.filter(t => t.status === 'completed');
    if (completedTests.length) {
      this.comparisonOpts = {
        tooltip: { trigger: 'axis' },
        legend:  { data: ['Control Default Rate %', 'Treatment Default Rate %'], textStyle: { color: '#94a3b8' } },
        xAxis:   { type: 'category', data: completedTests.map(t => t.name.slice(0, 28) + '…'), axisLabel: { color: '#64748b', rotate: 12, fontSize: 10 } },
        yAxis:   { type: 'value', axisLabel: { color: '#64748b', formatter: '{value}%' } },
        series:  [
          { name: 'Control Default Rate %',   type: 'bar', data: completedTests.map(t => +((t.control_default_rate || 0)*100).toFixed(2)),   itemStyle: { color: '#64748b' } },
          { name: 'Treatment Default Rate %', type: 'bar', data: completedTests.map(t => +((t.treatment_default_rate || 0)*100).toFixed(2)), itemStyle: { color: '#10b981' } },
        ],
        backgroundColor: 'transparent',
      };
    }
  }

  private buildLiftChart(): void {
    if (!this.liftCurve?.weeks?.length) return;

    this.liftOpts = {
      tooltip: { trigger: 'axis', formatter: (params: any[]) => {
        const w = params[0]?.axisValue;
        const lift = params[0]?.data;
        const pval = this.liftCurve.p_values?.[params[0]?.dataIndex] || 0;
        return `Week ${w}<br/>Cumulative Lift: <b>${lift?.toFixed(1)}%</b><br/>p-value: <b>${pval}</b>`;
      }},
      legend: { data: ['Cumulative Lift %', 'Significance Threshold'], textStyle: { color: '#94a3b8' } },
      xAxis:  { type: 'category', data: this.liftCurve.weeks, axisLabel: { color: '#64748b' }, name: 'Week' },
      yAxis:  { type: 'value', name: 'Lift %', axisLabel: { color: '#64748b', formatter: '{value}%' } },
      series: [
        { name: 'Cumulative Lift %',
          type: 'line', smooth: true,
          data: this.liftCurve.cumulative_lift,
          itemStyle: { color: this.liftCurve.is_significant ? '#10b981' : '#f59e0b' },
          areaStyle: { opacity: 0.15 },
          markLine: { silent: true, data: [{ yAxis: 0, lineStyle: { color: '#64748b', type: 'dashed' } }] },
        },
        { name: 'Significance Threshold',
          type: 'line', data: Array(this.liftCurve.weeks?.length).fill(-5),
          lineStyle: { color: '#ef4444', type: 'dashed' }, showSymbol: false, itemStyle: { color: '#ef4444' },
        },
      ],
      backgroundColor: 'transparent',
    };
  }

  statusClass(status: string): string {
    if (status === 'completed') return 'badge--success';
    if (status === 'active')    return 'badge--info';
    return 'badge--warning';
  }

  winnerClass(winner: string | null): string {
    if (winner === 'treatment') return 'badge--success';
    if (winner === 'control')   return 'badge--warning';
    return 'badge--info';
  }

  liftClass(lift: number): string {
    if (lift < -0.1)  return 'lift--positive';
    if (lift > 0.05)  return 'lift--negative';
    return 'lift--neutral';
  }
}
