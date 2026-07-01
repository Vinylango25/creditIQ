import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { of } from 'rxjs';
import { catchError } from 'rxjs/operators';
import { ApiService } from '../../core/api.service';

@Component({
  selector: 'app-applicants',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './applicants.component.html',
  styleUrls: ['./applicants.component.scss'],
})
export class ApplicantsComponent implements OnInit {
  loading = true;
  applicants: any[] = [];
  total = 0; page = 1; pageSize = 25;
  selectedApplicant: any = null;
  loadingDetail = false;

  // Filters
  countryFilter    = '';
  tuGradeFilter    = '';
  employmentFilter = '';

  constructor(private api: ApiService) {}

  ngOnInit(): void {
    this.loadApplicants();
  }

  loadApplicants(): void {
    this.api.getApplicants(this.page, this.pageSize, {
      country:    this.countryFilter    || undefined,
      tu_grade:   this.tuGradeFilter    || undefined,
      employment: this.employmentFilter || undefined,
    }).pipe(catchError(() => of({ total: 0, applicants: [] }))).subscribe((r: any) => {
      this.applicants = r.applicants || [];
      this.total      = r.total || 0;
      this.loading    = false;
    });
  }

  applyFilters(): void { this.page = 1; this.loadApplicants(); }
  prevPage(): void { if (this.page > 1) { this.page--; this.loadApplicants(); } }
  nextPage(): void { if (this.page * this.pageSize < this.total) { this.page++; this.loadApplicants(); } }
  get totalPages(): number { return Math.ceil(this.total / this.pageSize); }

  viewDetail(applicantId: string): void {
    this.loadingDetail = true;
    this.selectedApplicant = null;
    this.api.getApplicant(applicantId)
      .pipe(catchError(() => of(null)))
      .subscribe(r => {
        this.selectedApplicant = r;
        this.loadingDetail = false;
      });
  }

  closeDetail(): void { this.selectedApplicant = null; }

  scoreClass(score: number): string {
    if (score >= 750) return 'grade--excellent';
    if (score >= 700) return 'grade--good';
    if (score >= 650) return 'grade--fair';
    if (score >= 600) return 'grade--poor';
    return 'grade--very-poor';
  }

  seonClass(s: number): string {
    if (s >= 70) return 'risk--high';
    if (s >= 40) return 'risk--medium';
    return 'risk--low';
  }

  gradeClass(g: string): string {
    const m: Record<string, string> = { A: 'badge--success', B: 'badge--info', C: 'badge--warning', D: 'badge--danger', E: 'badge--danger' };
    return m[g] || 'badge--info';
  }

  woeEntries(woe: any): { key: string; val: number }[] {
    if (!woe) return [];
    return Object.entries(woe)
      .map(([key, val]) => ({ key, val: val as number }))
      .sort((a, b) => Math.abs(b.val) - Math.abs(a.val));
  }

  fmtKey(key: string): string {
    return key.split('_').join(' ');
  }

  absBarPct(val: number): number {
    return Math.min(Math.abs(val) * 3, 100);
  }

  fmtKES(n: number): string {
    if (!n) return '0';
    if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
    if (n >= 1_000)     return (n / 1_000).toFixed(1) + 'K';
    return n.toFixed(0);
  }
}
