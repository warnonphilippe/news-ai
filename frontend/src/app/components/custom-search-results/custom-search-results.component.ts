import { Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Article } from '../../models/article.model';
import { DigestCardComponent } from '../digest-card/digest-card.component';
import { ExportButtonComponent } from '../export-button/export-button.component';

@Component({
  selector: 'app-custom-search-results',
  standalone: true,
  imports: [CommonModule, DigestCardComponent, ExportButtonComponent],
  template: `
    <section class="digest">
      <header class="digest__head">
        <div>
          <h1 class="digest__title">Recherche : « {{ query }} »</h1>
          <p class="digest__status">
            <ng-container [ngSwitch]="true">
              <span *ngSwitchCase="loading">Recherche en cours…</span>
              <span *ngSwitchCase="!!error">{{ error }}</span>
              <span *ngSwitchDefault>{{ articles.length }} article(s)</span>
            </ng-container>
          </p>
        </div>
        <div class="digest__actions">
          <app-export-button
            [articles]="articles"
            [contextLabel]="'Recherche ' + query"
          ></app-export-button>
          <button class="btn btn--ghost" type="button" (click)="clear.emit()">
            Revenir au digest
          </button>
        </div>
      </header>

      <div *ngIf="loading" class="digest__loading">
        Interrogation des sources sur « {{ query }} » et résumés en cours.
        Cela peut prendre 1 à 2 minutes.
      </div>

      <p *ngIf="!loading && !error && !articles.length" class="digest__empty">
        Aucun article ne correspond à ce critère.
      </p>

      <div class="digest__cards">
        <app-digest-card *ngFor="let a of articles" [article]="a"></app-digest-card>
      </div>
    </section>
  `,
})
export class CustomSearchResultsComponent {
  @Input() query: string | null = null;
  @Input() articles: Article[] = [];
  @Input() loading = false;
  @Input() error: string | null = null;
  @Output() clear = new EventEmitter<void>();
}
