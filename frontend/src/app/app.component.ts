import { Component, OnDestroy, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Subscription, interval } from 'rxjs';
import { switchMap } from 'rxjs/operators';

import { DigestService } from './services/digest.service';
import { Article, HistoryDay } from './models/article.model';
import { DigestListComponent } from './components/digest-list/digest-list.component';
import { HistorySidebarComponent } from './components/history-sidebar/history-sidebar.component';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, DigestListComponent, HistorySidebarComponent],
  template: `
    <div class="layout">
      <app-history-sidebar
        [days]="history"
        [selected]="selectedDate"
        (pick)="selectDate($event)"
      ></app-history-sidebar>

      <main class="main">
        <app-digest-list
          [articles]="articles"
          [runDate]="selectedDate || today"
          [status]="status"
          [isToday]="isToday"
          (run)="triggerRun()"
        ></app-digest-list>
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

  private poll?: Subscription;

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
  }

  selectDate(date: string): void {
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
