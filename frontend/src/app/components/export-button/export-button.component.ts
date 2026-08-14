import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Article } from '../../models/article.model';
import { buildDigestMarkdown, downloadMarkdown, slugify } from '../../utils/markdown-export';

@Component({
  selector: 'app-export-button',
  standalone: true,
  imports: [CommonModule],
  template: `
    <button
      class="btn btn--ghost"
      type="button"
      [disabled]="!articles.length"
      (click)="onExport()"
      title="Exporter cette liste en fichier Markdown"
    >
      Exporter (.md)
    </button>
  `,
})
export class ExportButtonComponent {
  @Input({ required: true }) articles: Article[] = [];
  @Input({ required: true }) contextLabel = '';

  onExport(): void {
    const content = buildDigestMarkdown(this.articles, this.contextLabel);
    downloadMarkdown(`${slugify(this.contextLabel)}.md`, content);
  }
}
