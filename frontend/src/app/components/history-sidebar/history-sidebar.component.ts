import { Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { CustomSearchSummary, HistoryDay } from '../../models/article.model';

@Component({
  selector: 'app-history-sidebar',
  standalone: true,
  imports: [CommonModule],
  template: `
    <aside class="sidebar">
      <ng-container *ngIf="searches.length || pendingQuery">
        <h2 class="sidebar__title">Recherches personnalisées</h2>
        <ul class="sidebar__list sidebar__list--custom">
          <li
            *ngIf="pendingQuery"
            class="sidebar__item sidebar__item--pending"
            [class.sidebar__item--active]="customActive && activeSearchId === null"
            [title]="pendingQuery"
          >
            <span class="sidebar__query">{{ pendingQuery }}</span>
            <span class="sidebar__count">…</span>
          </li>
          <li
            *ngFor="let s of searches"
            class="sidebar__item"
            [class.sidebar__item--active]="customActive && s.id === activeSearchId"
            [title]="s.query + ' — ' + s.created_at"
            (click)="pickCustom.emit(s.id)"
          >
            <span class="sidebar__query">{{ s.query }}</span>
            <span class="sidebar__count">{{ s.count }}</span>
            <button
              type="button"
              class="sidebar__delete"
              title="Supprimer cette recherche"
              aria-label="Supprimer cette recherche"
              (click)="onDelete($event, s.id)"
            >
              ×
            </button>
          </li>
        </ul>
      </ng-container>

      <h2 class="sidebar__title">Conseils du jour</h2>
      <p class="sidebar__hint" *ngIf="!days?.length">Aucun jour enregistré.</p>
      <ul class="sidebar__list">
        <li
          *ngFor="let d of days"
          class="sidebar__item"
          [class.sidebar__item--active]="d.run_date === selected"
          (click)="pick.emit(d.run_date)"
        >
          <span class="sidebar__date">{{ d.run_date }}</span>
          <span class="sidebar__count">{{ d.count }}</span>
        </li>
      </ul>
    </aside>
  `,
})
export class HistorySidebarComponent {
  @Input() days: HistoryDay[] = [];
  /** Date affichee, ou null si la rubrique active est une recherche. */
  @Input() selected: string | null = null;
  /** Recherches memorisees, de la plus recente a la plus ancienne. */
  @Input() searches: CustomSearchSummary[] = [];
  /** Recherche en cours (pas encore memorisee, donc pas encore dans `searches`). */
  @Input() pendingQuery: string | null = null;
  /** true quand la vue affichee est une recherche (et non un digest). */
  @Input() customActive = false;
  /** Id de la recherche affichee ; null = celle encore en cours. */
  @Input() activeSearchId: number | null = null;
  @Output() pick = new EventEmitter<string>();
  @Output() pickCustom = new EventEmitter<number>();
  @Output() deleteCustom = new EventEmitter<number>();

  /** La croix ne doit pas declencher l'affichage de la recherche supprimee. */
  onDelete(event: Event, id: number): void {
    event.stopPropagation();
    this.deleteCustom.emit(id);
  }
}
