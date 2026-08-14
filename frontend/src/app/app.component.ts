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
        [selected]="selectedDate"
        (pick)="selectDate($event)"
      ></app-history-sidebar>

      <main class="main">
        <app-custom-search-bar
          [pending]="customLoading"
          (search)="runCustomSearch($event)"
        ></app-custom-search-bar>

        <app-digest-list
          *ngIf="mode === 'daily'"
          [articles]="articles"
          [runDate]="selectedDate || today"
          [status]="status"
          [isToday]="isToday"
          (run)="triggerRun()"
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

  selectDate(date: string): void {
    this.mode = 'daily';
    this.customSub?.unsubscribe();
    this.selectedDate = date;
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

  triggerRun(): void {
    this.status = 'running';
    this.svc.run().subscribe(() => this.startPolling());
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

  exitCustomMode(): void {
    this.customSub?.unsubscribe();
    this.mode = 'daily';
    this.customQuery = null;
    this.customResults = [];
    this.customError = null;
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
