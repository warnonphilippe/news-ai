import { Component, OnDestroy, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Subscription, interval } from 'rxjs';
import { switchMap } from 'rxjs/operators';

import { DigestService } from './services/digest.service';
import {
  Article,
  CustomSearchResponse,
  CustomSearchSummary,
  HistoryDay,
} from './models/article.model';
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
        [searches]="searches"
        [pendingQuery]="customLoading ? customQuery : null"
        [customActive]="mode === 'custom'"
        [activeSearchId]="activeSearchId"
        (pick)="selectDate($event)"
        (pickCustom)="showCustom($event)"
        (deleteCustom)="deleteSearch($event)"
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
  /** Recherches memorisees cote serveur (persistantes). */
  searches: CustomSearchSummary[] = [];
  /** Recherche affichee ; null tant que celle en cours n'est pas memorisee. */
  activeSearchId: number | null = null;

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
    this.refreshSearches();
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

  /** Relit une recherche memorisee (aucun nouvel appel aux moteurs/LLM). */
  showCustom(id: number): void {
    this.customSub?.unsubscribe();
    this.mode = 'custom';
    this.activeSearchId = id;
    this.customError = null;
    this.customResults = [];
    this.customQuery = this.searches.find((s) => s.id === id)?.query ?? null;
    this.customLoading = true;
    this.customSub = this.svc.getSearch(id).subscribe({
      next: (res) => {
        this.customQuery = res.query;
        this.customResults = res.articles;
        this.customLoading = false;
      },
      error: () => {
        this.customError = 'Cette recherche n’est plus disponible.';
        this.customLoading = false;
      },
    });
  }

  deleteSearch(id: number): void {
    this.svc.deleteSearch(id).subscribe({
      next: () => {
        this.searches = this.searches.filter((s) => s.id !== id);
        // La recherche affichee vient de disparaitre : retour au digest.
        if (this.mode === 'custom' && this.activeSearchId === id) {
          this.exitCustomMode();
        }
      },
      // Echec de suppression : on laisse la liste en place plutot que de
      // faire disparaitre une entree qui existe toujours cote serveur.
      error: () => {},
    });
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
    this.activeSearchId = null;
    this.customLoading = true;
    this.customError = null;
    this.customResults = [];
    this.customSub = this.svc.searchCustom(query).subscribe({
      next: (res) => {
        this.customResults = res.articles;
        this.customLoading = false;
        this.activeSearchId = res.id ?? null;
        // Insertion immediate depuis la reponse : la rubrique apparait sans
        // attendre l'aller-retour de la liste, et reste affichee meme si ce
        // rafraichissement echoue. refreshSearches() reconcilie ensuite.
        this.rememberSearch(res);
        this.refreshSearches(res);
      },
      error: (err) => {
        this.customError =
          err?.error?.detail || 'La recherche a échoué. Réessayez.';
        this.customLoading = false;
      },
    });
  }

  /** Repasse sur le digest ; les recherches restent accessibles depuis la
   * barre laterale (elles sont memorisees cote serveur). */
  exitCustomMode(): void {
    this.mode = 'daily';
  }

  /** Ajoute (ou remplace) une recherche dans la liste, la plus recente en tete. */
  private rememberSearch(res: CustomSearchResponse): void {
    if (res.id == null) return;
    const summary: CustomSearchSummary = {
      id: res.id,
      query: res.query,
      created_at: res.created_at,
      count: res.articles.length,
    };
    this.searches = [summary, ...this.searches.filter((s) => s.id !== res.id)];
  }

  /** Recharge la liste depuis le serveur (source de verite).
   * `keep` est reinjecte apres coup : la recherche qu'on vient de terminer ne
   * doit jamais disparaitre de la rubrique, meme si la liste renvoyee ne la
   * contient pas encore. */
  private refreshSearches(keep?: CustomSearchResponse): void {
    this.svc.listSearches().subscribe({
      next: (res) => {
        this.searches = res.searches;
        if (keep) this.rememberSearch(keep);
      },
      // Liste indisponible : on garde ce qu'on a deja affiche plutot que de
      // vider la rubrique (un echec de lecture n'efface rien cote serveur).
      error: () => {},
    });
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
