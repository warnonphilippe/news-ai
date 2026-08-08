import { Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Article } from '../../models/article.model';
import { DigestCardComponent } from '../digest-card/digest-card.component';

@Component({
  selector: 'app-digest-list',
  standalone: true,
  imports: [CommonModule, DigestCardComponent],
  template: `
    <section class="digest">
      <header class="digest__head">
        <div>
          <h1 class="digest__title">Sélection du {{ runDate }}</h1>
          <p class="digest__status" [ngClass]="'status--' + status">
            <ng-container [ngSwitch]="status">
              <span *ngSwitchCase="'running'">Recherche en cours…</span>
              <span *ngSwitchCase="'done'">{{ articles.length }} article(s)</span>
              <span *ngSwitchCase="'error'">Erreur lors de la dernière recherche</span>
              <span *ngSwitchCase="'none'">Aucune recherche pour cette date</span>
              <span *ngSwitchDefault>{{ status }}</span>
            </ng-container>
          </p>
        </div>
        <button
          class="btn"
          [disabled]="status === 'running' || !isToday"
          (click)="run.emit()"
        >
          {{ status === 'running' ? '…' : 'Rechercher aujourd’hui' }}
        </button>
      </header>

      <div *ngIf="status === 'running'" class="digest__loading">
        Interrogation des sources (Exa, Brave) et résumés en cours. Cela peut
        prendre 1 à 3 minutes.
      </div>

      <p
        *ngIf="status !== 'running' && !articles.length"
        class="digest__empty"
      >
        Rien à afficher. Lancez une recherche pour aujourd’hui.
      </p>

      <div class="digest__cards">
        <app-digest-card
          *ngFor="let a of articles"
          [article]="a"
        ></app-digest-card>
      </div>
    </section>
  `,
})
export class DigestListComponent {
  @Input() articles: Article[] = [];
  @Input() runDate = '';
  @Input() status = 'none';
  @Input() isToday = true;
  @Output() run = new EventEmitter<void>();
}
