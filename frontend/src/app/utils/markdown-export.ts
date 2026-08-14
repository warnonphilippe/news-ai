import { Article } from '../models/article.model';

/** Convertit un texte en nom de fichier sûr (minuscules, tirets, sans accents). */
export function slugify(text: string): string {
  const cleaned = text
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '') // marques diacritiques combinantes (accents)
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/(^-+|-+$)/g, '')
    .slice(0, 60);
  return cleaned || 'export';
}

/** Construit le contenu Markdown d'une liste d'articles (digest ou recherche). */
export function buildDigestMarkdown(articles: Article[], title: string): string {
  const lines: string[] = [
    `# ${title}`,
    '',
    `_Exporté le ${new Date().toLocaleString('fr-BE')}_`,
    '',
  ];

  articles.forEach((a, i) => {
    lines.push(`## ${i + 1}. ${a.title}`);
    lines.push('');

    const meta: string[] = [];
    if (a.source) meta.push(`**Source :** ${a.source}`);
    if (a.published_date) meta.push(`**Date :** ${a.published_date}`);
    if (a.final_score !== null && a.final_score !== undefined) {
      meta.push(`**Score :** ${a.final_score}`);
    }
    if (meta.length) {
      lines.push(meta.join(' · '));
      lines.push('');
    }

    if (a.tags?.length) {
      lines.push(`**Tags :** ${a.tags.join(', ')}`);
      lines.push('');
    }

    lines.push(a.summary);
    lines.push('');

    if (a.why_it_matters) {
      lines.push(`**Pourquoi c'est important :** ${a.why_it_matters}`);
      lines.push('');
    }
    if (a.relevance_rationale) {
      lines.push(`**Retenu car :** ${a.relevance_rationale}`);
      lines.push('');
    }

    lines.push(`🔗 [Lire la source](${a.url})`);
    (a.links || []).forEach((l) => lines.push(`- [${l.title || l.url}](${l.url})`));
    lines.push('');
    lines.push('---');
    lines.push('');
  });

  return lines.join('\n');
}

/** Déclenche le téléchargement d'un fichier texte dans le navigateur. */
export function downloadMarkdown(filename: string, content: string): void {
  const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}
