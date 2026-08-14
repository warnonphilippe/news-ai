import { Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HistoryDay } from '../../models/article.model';

@Component({
  selector: 'app-history-sidebar',
  standalone: true,
  imports: [CommonModule],
  template: `
    <aside class="sidebar">
      <ng-container *ngIf="customQuery !== null">
        <h2 class="sidebar__title">Recherche personnalisée</h2>
        <ul class="sidebar__list sidebar__list--custom">
          <li
            class="sidebar__item"
            [class.sidebar__item--active]="customActive"
            [title]="customQuery"
            (click)="pickCustom.emit()"
          >
            <span class="sidebar__query">{{ customQuery }}</span>
            <span class="sidebar__count">{{ customLoading ? '…' : customCount }}</span>
          </li>
        </ul>
      </ng-container>

      <h2 class="sidebar__title">Historique</h2>
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
  /** Date affichee, ou null si la rubrique active est la recherche personnalisee. */
  @Input() selected: string | null = null;
  /** Derniere (et unique) recherche personnalisee memorisee ; null si aucune. */
  @Input() customQuery: string | null = null;
  @Input() customCount = 0;
  @Input() customLoading = false;
  @Input() customActive = false;
  @Output() pick = new EventEmitter<string>();
  @Output() pickCustom = new EventEmitter<void>();
}
