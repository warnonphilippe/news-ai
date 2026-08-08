import { Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HistoryDay } from '../../models/article.model';

@Component({
  selector: 'app-history-sidebar',
  standalone: true,
  imports: [CommonModule],
  template: `
    <aside class="sidebar">
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
  @Input() selected: string | null = null;
  @Output() pick = new EventEmitter<string>();
}
