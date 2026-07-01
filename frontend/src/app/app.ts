import { Component, OnInit, signal, HostListener } from '@angular/core';
import { Router, RouterOutlet, RouterLink, RouterLinkActive, NavigationEnd } from '@angular/router';
import { CommonModule } from '@angular/common';
import { ThemeService } from './core/theme.service';
import { filter } from 'rxjs/operators';

export interface NavGroup {
  label: string; icon: string; paths: string[]; primary: string;
}

interface NavItem { path: string; label: string; icon: string; group: string; }

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, RouterOutlet, RouterLink, RouterLinkActive],
  templateUrl: './app.html',
  styleUrl: './app.scss',
})
export class App implements OnInit {

  readonly navGroups: NavGroup[] = [
    { label: 'Overview',       icon: '📊', primary: 'dashboard',      paths: ['dashboard','transactions'] },
    { label: 'Fraud',          icon: '🚨', primary: 'analytics-3d',   paths: ['analytics-3d','model-comparison','model-monitoring'] },
    { label: 'Credit',         icon: '🏦', primary: 'credit-scoring', paths: ['credit-scoring','loan-portfolio','applicants'] },
    { label: 'Risk',           icon: '📉', primary: 'risk-analytics', paths: ['risk-analytics','fpd-analysis','vintage-analysis'] },
    { label: 'A/B & Cost',     icon: '⚗️', primary: 'ab-testing',     paths: ['ab-testing','cost-analysis'] },
    { label: 'Explainability', icon: '🧠', primary: 'explainability', paths: ['explainability'] },
    { label: 'ML Pipeline',    icon: '⚙️', primary: 'training',       paths: ['training','review-queue'] },
  ];

  readonly subNav: Record<string, { path: string; label: string }[]> = {
    'dashboard':      [{ path:'dashboard',label:'Dashboard'},{ path:'transactions',label:'Transactions'}],
    'analytics-3d':   [{ path:'analytics-3d',label:'Advanced Analytics'},{ path:'model-comparison',label:'Model Comparison'},{ path:'model-monitoring',label:'Model Health'}],
    'credit-scoring': [{ path:'credit-scoring',label:'Credit Scoring'},{ path:'loan-portfolio',label:'Loan Portfolio'},{ path:'applicants',label:'Applicant Profiles'}],
    'risk-analytics': [{ path:'risk-analytics',label:'Risk Overview'},{ path:'fpd-analysis',label:'FPD Analysis'},{ path:'vintage-analysis',label:'Vintage & Cohorts'}],
    'ab-testing':     [{ path:'ab-testing',label:'A/B Testing'},{ path:'cost-analysis',label:'Cost & ROI'}],
    'explainability': [{ path:'explainability',label:'SHAP / LIME / Feature Importance'}],
    'training':       [{ path:'training',label:'Pipeline & Training'},{ path:'review-queue',label:'Human-in-the-Loop'}],
  };

  // All nav items flattened for mobile drawer
  readonly allNavItems: NavItem[] = this.navGroups.flatMap(g =>
    (this.subNav[g.primary] || []).map(s => ({
      path: s.path, label: s.label, icon: g.icon, group: g.label,
    }))
  );

  activeGroup = signal<string>('dashboard');
  currentUrl  = signal('/dashboard');
  mobileOpen  = signal(false);

  constructor(public theme: ThemeService, public router: Router) {}

  ngOnInit(): void {
    this.router.events.pipe(filter(e => e instanceof NavigationEnd))
      .subscribe((e: any) => {
        const url = e.urlAfterRedirects || e.url;
        this.currentUrl.set(url);
        this.updateActiveGroup(url);
        this.mobileOpen.set(false); // close drawer on navigation
      });
    this.updateActiveGroup(this.router.url);
  }

  private updateActiveGroup(url: string): void {
    const seg = url.replace('/','').split('/')[0];
    const g   = this.navGroups.find(g => g.paths.includes(seg));
    if (g) this.activeGroup.set(g.primary);
  }

  isGroupActive(group: NavGroup): boolean {
    const seg = this.currentUrl().replace('/','').split('/')[0];
    return group.paths.includes(seg);
  }

  isItemActive(path: string): boolean {
    const seg = this.currentUrl().replace('/','').split('/')[0];
    return seg === path;
  }

  getSubNav(): { path: string; label: string }[] {
    return this.subNav[this.activeGroup()] || [];
  }

  get hasSubNav(): boolean { return this.getSubNav().length > 1; }

  toggleMobile(): void { this.mobileOpen.update(v => !v); }
  closeMobile():  void { this.mobileOpen.set(false); }

  @HostListener('document:keydown.escape')
  onEsc(): void { this.mobileOpen.set(false); }
}
