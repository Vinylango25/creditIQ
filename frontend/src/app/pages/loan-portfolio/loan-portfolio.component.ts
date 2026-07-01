import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { forkJoin, of } from 'rxjs';
import { catchError, debounceTime, distinctUntilChanged, Subject, switchMap } from 'rxjs';
import { ApiService } from '../../core/api.service';
import { ChartComponent } from '../../shared/chart/chart.component';

@Component({
  selector: 'app-loan-portfolio',
  standalone: true,
  imports: [CommonModule, FormsModule, ChartComponent],
  templateUrl: './loan-portfolio.component.html',
  styleUrls: ['./loan-portfolio.component.scss'],
})
export class LoanPortfolioComponent implements OnInit {
  loading = true;
  loans: any[] = [];
  total = 0; page = 1; pageSize = 25;
  summary: any = {};
  statusFilter   = '';
  productFilter  = '';
  cohortFilter   = '';

  statusOpts: any = {};
  productOpts: any = {};

  constructor(private api: ApiService) {}

  ngOnInit(): void {
    forkJoin({
      summary: this.api.getCreditSummary().pipe(catchError(() => of({}))),
    }).subscribe({
      next: (r: any) => {
        this.summary = r.summary || {};
        this.buildCharts();
        this.loadLoans();
        this.loading = false;
      },
    });
  }

  loadLoans(): void {
    this.api.getLoans(this.page, this.pageSize, {
      status:       this.statusFilter   || undefined,
      product_type: this.productFilter  || undefined,
      cohort:       this.cohortFilter   || undefined,
    }).pipe(catchError(() => of({ total: 0, loans: [] }))).subscribe((r: any) => {
      this.loans = r.loans || [];
      this.total = r.total || 0;
    });
  }

  applyFilters(): void { this.page = 1; this.loadLoans(); }
  prevPage(): void { if (this.page > 1) { this.page--; this.loadLoans(); } }
  nextPage(): void { if (this.page * this.pageSize < this.total) { this.page++; this.loadLoans(); } }
  get totalPages(): number { return Math.ceil(this.total / this.pageSize); }

  private buildCharts(): void {
    // Status donut
    const statuses = ['active','paid','default','written_off'];
    const counts = [
      this.summary.active_loans    || 0,
      this.summary.paid_loans      || 0,
      this.summary.defaulted_loans || 0,
      this.summary.written_off_loans || 0,
    ];
    const colors = ['#3b82f6','#10b981','#ef4444','#7c3aed'];
    this.statusOpts = {
      tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
      legend:  { bottom: 0, textStyle: { color: '#94a3b8' } },
      series:  [{ type: 'pie', radius: ['40%','68%'],
        data: statuses.map((s, i) => ({ name: s, value: counts[i], itemStyle: { color: colors[i] } })),
        label: { color: '#94a3b8', fontSize: 11 },
      }],
      backgroundColor: 'transparent',
    };
  }

  statusClass(status: string): string {
    const map: Record<string, string> = { active: 'badge--info', paid: 'badge--success', default: 'badge--danger', written_off: 'badge--danger' };
    return map[status] || 'badge--info';
  }

  fmtKES(n: number): string {
    if (!n) return '0';
    if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
    if (n >= 1_000)     return (n / 1_000).toFixed(1) + 'K';
    return n.toFixed(0);
  }

  pdClass(pd: number): string {
    if (pd > 0.2) return 'risk--high';
    if (pd > 0.1) return 'risk--medium';
    return 'risk--low';
  }
}
