import { Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';

@Component({
  selector: 'app-custom-search-bar',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <form class="search-bar" (ngSubmit)="submit()">
      <input
        class="search-bar__input"
        type="text"
        name="query"
        [(ngModel)]="query"
        maxlength="300"
        placeholder="Rechercher un sujet, une question… (vide = sélection du jour)"
        [disabled]="pending"
      />
      <button class="btn" type="submit" [disabled]="pending">
        {{ label }}
      </button>
    </form>
  `,
})
export class CustomSearchBarComponent {
  @Input() pending = false;
  /** Emet le critere saisi, ou une chaine vide pour la recherche du jour. */
  @Output() search = new EventEmitter<string>();

  query = '';

  get label(): string {
    if (this.pending) return 'Recherche…';
    return this.query.trim() ? 'Rechercher' : 'Rechercher aujourd’hui';
  }

  submit(): void {
    if (this.pending) return;
    this.search.emit(this.query.trim());
  }
}
