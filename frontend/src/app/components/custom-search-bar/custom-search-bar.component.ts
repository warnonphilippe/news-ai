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
        placeholder="Rechercher un sujet, une question… (ex : « RAG avec pgvector en production »)"
        [disabled]="pending"
      />
      <button
        class="btn"
        type="submit"
        [disabled]="pending || !query.trim()"
      >
        {{ pending ? 'Recherche…' : 'Rechercher' }}
      </button>
    </form>
  `,
})
export class CustomSearchBarComponent {
  @Input() pending = false;
  @Output() search = new EventEmitter<string>();

  query = '';

  submit(): void {
    const q = this.query.trim();
    if (!q || this.pending) return;
    this.search.emit(q);
  }
}
