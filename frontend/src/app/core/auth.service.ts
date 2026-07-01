// AuthService — stub (authentication removed from this platform)
import { Injectable, signal, computed } from '@angular/core';
import { Observable, of } from 'rxjs';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private _checked = signal(true);
  readonly isChecked       = computed(() => this._checked());
  readonly isAuthenticated = computed(() => true);  // always authenticated

  checkSession(): Observable<boolean> { return of(true); }
  login(_email: string, _password: string): Observable<any> { return of({}); }
  logout(): Observable<any> { return of({}); }
  getUser(): any { return null; }
}
