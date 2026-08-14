import { Component, OnDestroy, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Subscription, interval } from 'rxjs';
import { switchMap } from 'rxjs/operators';

import { DigestService } from './services/digest.service';
import { Article, HistoryDay } from './models/article.model';
import { DigestListComponent } from './components/digest-list/digest-list.component';
import { HistorySidebarComponent } from './components/history-sidebar/history-sidebar.component';
import { CustomSearchBarComponent } from './components/custom-search-bar/custom-search-bar.component';
import { CustomSearchResultsComponent } from './components/custom-search-results/custom-search-results.component';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [
    CommonModule,
    DigestListComponent,
    HistorySidebarComponent,
    CustomSearchBarComponent,
    CustomSearchResultsComponent,
  ],
  template: `
    <div class="layout">
      <app-history-sidebar
        [days]="history"
        [selected]="mode === 'custom' ? null : selectedDate"
        [customQuery]="customQuery"
        [customCount]="customResults.length"
        [customLoading]="customLoading"
        [customActive]="mode === 'custom'"
        (pick)="selectDate($event)"
        (pickCustom)="showCustom()"
      ></app-history-sidebar>

      <main class="main">
        <app-custom-search-bar
          [pending]="searchPending"
          (search)="onSearch($event)"
        ></app-custom-search-bar>

        <app-digest-list
          *ngIf="mode === 'daily'"
          [articles]="articles"
          [runDate]="selectedDate || today"
          [status]="status"
        ></app-digest-list>

        <app-custom-search-results
          *ngIf="mode === 'custom'"
          [query]="customQuery"
          [articles]="customResults"
          [loading]="customLoading"
          [error]="customError"
          (clear)="exitCustomMode()"
        ></app-custom-search-results>
      </main>
    </div>
  `,
})
export class AppComponent implements OnInit, OnDestroy {
  today = '';
  selectedDate: string | null = null;
  status = 'none';
  articles: Article[] = [];
  history: HistoryDay[] = [];

  mode: 'daily' | 'custom' = 'daily';
  customQuery: string | null = null;
  customResults: Article[] = [];
  customLoading = false;
  customError: string | null = null;

  private poll?: Subscription;
  private customSub?: Subscription;

  constructor(private svc: DigestService) {}

  get isToday(): boolean {
    return this.selectedDate === null || this.selectedDate === this.today;
  }

  /** Une seule barre de recherche pilote les deux recherches : elle reste
   * inactive tant que l'une ou l'autre est en cours. */
  get searchPending(): boolean {
    return this.customLoading || (this.status === 'running' && this.isToday);
  }

  ngOnInit(): void {
    this.svc.getToday().subscribe((res) => {
      this.today = res.run_date;
      this.selectedDate = res.run_date;
      this.status = res.status;
      this.articles = res.articles;
      if (res.status === 'running') {
        this.startPolling();
      }
    });
    this.refreshHistory();
  }

  ngOnDestroy(): void {
    this.poll?.unsubscribe();
    this.customSub?.unsubscribe();
  }

  /** Critere vide : on relance/reaffiche la selection du jour. */
  onSearch(query: string): void {
    if (query) {
      this.runCustomSearch(query);
    } else {
      this.triggerRun();
    }
  }

  selectDate(date: string): void {
    this.mode = 'daily';
    this.selectedDate = date;
    this.loadDate(date);
  }

  showCustom(): void {
    this.mode = 'custom';
  }

  triggerRun(): void {
    this.mode = 'daily';
    this.selectedDate = this.today;
    this.status = 'running';
    this.svc.run().subscribe((res) => {
      if (res.action === 'skipped') {
        // Deja fait aujourd'hui : rien n'a ete relance, on reaffiche.
        this.loadDate(this.today);
      } else {
        this.startPolling();
      }
    });
  }

  runCustomSearch(query: string): void {
    // Annule une recherche precedente en vol pour qu'une reponse tardive
    // n'ecrase pas un resultat plus recent.
    this.customSub?.unsubscribe();
    this.mode = 'custom';
    this.customQuery = query;
    this.customLoading = true;
    this.customError = null;
    this.customResults = [];
    this.customSub = this.svc.searchCustom(query).subscribe({
      next: (res) => {
        this.customResults = res.articles;
        this.customLoading = false;
      },
      error: (err) => {
        this.customError =
          err?.error?.detail || 'La recherche a échoué. Réessayez.';
        this.customLoading = false;
      },
    });
  }

  /** Repasse sur le digest sans perdre la recherche personnalisee : elle reste
   * accessible depuis sa rubrique dans l'historique. */
  exitCustomMode(): void {
    this.mode = 'daily';
  }

  private loadDate(date: string): void {
    this.svc.getByDate(date).subscribe((res) => {
      this.status = res.status;
      this.articles = res.articles;
      if (res.status === 'running' && this.isToday) {
        this.startPolling();
      } else {
        this.poll?.unsubscribe();
      }
    });
  }

  private startPolling(): void {
    this.poll?.unsubscribe();
    this.poll = interval(4000)
      .pipe(switchMap(() => this.svc.getToday()))
      .subscribe((res) => {
        this.status = res.status;
        this.articles = res.articles;
        if (res.status !== 'running') {
          this.poll?.unsubscribe();
          this.refreshHistory();
        }
      });
  }

  private refreshHistory(): void {
    this.svc.getHistory().subscribe((res) => (this.history = res.days));
  }
}
