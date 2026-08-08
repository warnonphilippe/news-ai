import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Article } from '../../models/article.model';

@Component({
  selector: 'app-digest-card',
  standalone: true,
  imports: [CommonModule],
  template: `
    <article class="card">
      <header class="card__head">
        <span class="card__rank">{{ article.rank }}</span>
        <div class="card__titles">
          <a class="card__title" [href]="article.url" target="_blank" rel="noopener">
            {{ article.title }}
          </a>
          <div class="card__meta">
            <span *ngIf="article.source">{{ article.source }}</span>
            <span *ngIf="article.published_date">· {{ article.published_date }}</span>
            <span *ngIf="article.topic_cluster" class="card__cluster">
              {{ article.topic_cluster }}
            </span>
            <span *ngIf="article.is_update_of" class="card__badge">Complète un sujet précédent</span>
          </div>
        </div>
      </header>

      <p class="card__summary">{{ article.summary }}</p>

      <p class="card__why" *ngIf="article.why_it_matters">
        <strong>Pourquoi c'est important&nbsp;:</strong> {{ article.why_it_matters }}
      </p>

      <div class="card__tags" *ngIf="article.tags?.length">
        <span class="tag" *ngFor="let t of article.tags">{{ t }}</span>
      </div>

      <div class="card__links">
        <a [href]="article.url" target="_blank" rel="noopener">Lire la source ↗</a>
        <a
          *ngFor="let l of article.links"
          [href]="l.url"
          target="_blank"
          rel="noopener"
          >{{ l.title || l.url }} ↗</a
        >
      </div>
    </article>
  `,
})
export class DigestCardComponent {
  @Input({ required: true }) article!: Article;
}
