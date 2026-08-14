import { buildDigestMarkdown, downloadMarkdown, slugify } from './markdown-export';
import { Article } from '../models/article.model';

function makeArticle(overrides: Partial<Article> = {}): Article {
  return {
    id: 1,
    run_date: '2026-08-14',
    url: 'https://example.com/article',
    title: 'Titre de test',
    summary: 'Un resume de test.',
    why_it_matters: 'Ca compte.',
    source: 'example.com',
    published_date: '2026-08-13',
    tags: ['AI', 'Java'],
    topic_cluster: 'Test',
    links: [],
    is_update_of: null,
    rank: 1,
    relevance: 80,
    relevance_rationale: 'Pertinent.',
    age_days: 1,
    freshness_factor: 1.0,
    source_factor: 1.0,
    community_factor: 1.0,
    hn_points: null,
    hn_comments: null,
    final_score: 80,
    ...overrides,
  };
}

describe('slugify', () => {
  it('lowercases and replaces spaces with dashes', () => {
    expect(slugify('Hello World')).toBe('hello-world');
  });

  it('strips accents', () => {
    expect(slugify('Sélection du jour')).toBe('selection-du-jour');
  });

  it('replaces non-alphanumeric characters with dashes', () => {
    expect(slugify('Recherche : « RAG avec pgvector »')).toBe('recherche-rag-avec-pgvector');
  });

  it('trims leading and trailing dashes', () => {
    expect(slugify('---hello---')).toBe('hello');
  });

  it('truncates to 60 characters', () => {
    const long = 'a'.repeat(100);
    expect(slugify(long).length).toBe(60);
  });

  it('falls back to "export" when the cleaned result is empty', () => {
    expect(slugify('!!!???')).toBe('export');
  });

  it('falls back to "export" for an empty string', () => {
    expect(slugify('')).toBe('export');
  });

  it('collapses multiple separators into a single dash', () => {
    expect(slugify('a   b---c')).toBe('a-b-c');
  });
});

describe('buildDigestMarkdown', () => {
  it('includes the title as a top-level heading', () => {
    const md = buildDigestMarkdown([], 'Sélection du 2026-08-14');
    expect(md).toContain('# Sélection du 2026-08-14');
  });

  it('includes an export timestamp line', () => {
    const md = buildDigestMarkdown([], 'Titre');
    expect(md).toMatch(/_Exporté le .+_/);
  });

  it('numbers articles sequentially starting at 1', () => {
    const md = buildDigestMarkdown([makeArticle({ title: 'A' }), makeArticle({ title: 'B' })], 'T');
    expect(md).toContain('## 1. A');
    expect(md).toContain('## 2. B');
  });

  it('includes source, date and score in the meta line', () => {
    const md = buildDigestMarkdown([makeArticle()], 'T');
    expect(md).toContain('**Source :** example.com');
    expect(md).toContain('**Date :** 2026-08-13');
    expect(md).toContain('**Score :** 80');
  });

  it('includes tags joined by comma', () => {
    const md = buildDigestMarkdown([makeArticle({ tags: ['AI', 'Java', 'RAG'] })], 'T');
    expect(md).toContain('**Tags :** AI, Java, RAG');
  });

  it('omits tags line when tags array is empty', () => {
    const md = buildDigestMarkdown([makeArticle({ tags: [] })], 'T');
    expect(md).not.toContain('**Tags :**');
  });

  it('does not crash when tags is missing entirely from the payload', () => {
    // Le backend est source de verite runtime, pas le typage TS : un champ
    // reellement absent d'une reponse JSON doit rester gere sans crash.
    const art = makeArticle();
    delete (art as any).tags;
    const md = buildDigestMarkdown([art], 'T');
    expect(md).not.toContain('**Tags :**');
  });

  it('does not crash when links is missing entirely from the payload', () => {
    const art = makeArticle();
    delete (art as any).links;
    const md = buildDigestMarkdown([art], 'T');
    expect(md).toContain('Lire la source');
  });

  it('includes the summary body', () => {
    const md = buildDigestMarkdown([makeArticle({ summary: 'Un contenu unique XYZ.' })], 'T');
    expect(md).toContain('Un contenu unique XYZ.');
  });

  it('includes why_it_matters when present', () => {
    const md = buildDigestMarkdown([makeArticle({ why_it_matters: 'Raison ABC' })], 'T');
    expect(md).toContain("**Pourquoi c'est important :** Raison ABC");
  });

  it('omits why_it_matters line when empty', () => {
    const md = buildDigestMarkdown([makeArticle({ why_it_matters: '' })], 'T');
    expect(md).not.toContain("Pourquoi c'est important");
  });

  it('includes relevance_rationale when present', () => {
    const md = buildDigestMarkdown([makeArticle({ relevance_rationale: 'Justification XYZ' })], 'T');
    expect(md).toContain('**Retenu car :** Justification XYZ');
  });

  it('omits relevance_rationale line when null', () => {
    const md = buildDigestMarkdown([makeArticle({ relevance_rationale: null })], 'T');
    expect(md).not.toContain('Retenu car');
  });

  it('includes a link to the source article', () => {
    const md = buildDigestMarkdown([makeArticle({ url: 'https://a.example/x' })], 'T');
    expect(md).toContain('[Lire la source](https://a.example/x)');
  });

  it('includes complementary links when present', () => {
    const md = buildDigestMarkdown(
      [makeArticle({ links: [{ title: 'Doc officielle', url: 'https://docs.example' }] })],
      'T',
    );
    expect(md).toContain('- [Doc officielle](https://docs.example)');
  });

  it('falls back to the url as link label when title is missing', () => {
    const md = buildDigestMarkdown(
      [makeArticle({ links: [{ title: '', url: 'https://docs.example' }] })],
      'T',
    );
    expect(md).toContain('- [https://docs.example](https://docs.example)');
  });

  it('omits score line when final_score is null', () => {
    const md = buildDigestMarkdown([makeArticle({ final_score: null })], 'T');
    expect(md).not.toContain('**Score :**');
  });

  it('omits source line when source is empty', () => {
    const md = buildDigestMarkdown([makeArticle({ source: '' })], 'T');
    expect(md).not.toContain('**Source :**');
  });

  it('omits date line when published_date is empty', () => {
    const md = buildDigestMarkdown([makeArticle({ published_date: '' })], 'T');
    expect(md).not.toContain('**Date :**');
  });

  it('omits the whole meta line when source, date and score are all absent', () => {
    const md = buildDigestMarkdown(
      [makeArticle({ source: '', published_date: '', final_score: null })],
      'T',
    );
    expect(md).not.toContain('**Source :**');
    expect(md).not.toContain('**Date :**');
    expect(md).not.toContain('**Score :**');
  });

  it('separates multiple articles with a horizontal rule', () => {
    const md = buildDigestMarkdown([makeArticle(), makeArticle()], 'T');
    expect(md.match(/^---$/gm)?.length).toBe(2);
  });

  it('returns just the header for an empty article list', () => {
    const md = buildDigestMarkdown([], 'Vide');
    expect(md).toContain('# Vide');
    expect(md).not.toContain('##');
  });

  it('does not crash on markdown-special characters in the title', () => {
    const md = buildDigestMarkdown([makeArticle({ title: '[Test] *bold* _italic_' })], 'T');
    expect(md).toContain('## 1. [Test] *bold* _italic_');
  });
});

describe('downloadMarkdown', () => {
  let createObjectURLSpy: jest.SpyInstance;
  let revokeObjectURLSpy: jest.SpyInstance;
  let clickSpy: jest.SpyInstance;

  beforeEach(() => {
    // jsdom n'implemente pas createObjectURL/revokeObjectURL : on les
    // polyfille avant de les espionner (jest.spyOn exige que la propriete existe deja).
    if (!URL.createObjectURL) {
      (URL as any).createObjectURL = () => '';
    }
    if (!URL.revokeObjectURL) {
      (URL as any).revokeObjectURL = () => {};
    }

    createObjectURLSpy = jest
      .spyOn(URL, 'createObjectURL')
      .mockReturnValue('blob:mock-url');
    revokeObjectURLSpy = jest.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {});
    clickSpy = jest.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it('creates an object URL from a Blob', () => {
    downloadMarkdown('test.md', '# content');
    expect(createObjectURLSpy).toHaveBeenCalledTimes(1);
    const blobArg = createObjectURLSpy.mock.calls[0][0] as Blob;
    expect(blobArg.type).toContain('text/markdown');
  });

  it('sets the anchor download attribute to the given filename', () => {
    let capturedAnchor: HTMLAnchorElement | null = null;
    const appendSpy = jest
      .spyOn(document.body, 'appendChild')
      .mockImplementation((node) => {
        capturedAnchor = node as HTMLAnchorElement;
        return node;
      });
    jest.spyOn(document.body, 'removeChild').mockImplementation((node) => node);

    downloadMarkdown('mon-fichier.md', 'contenu');

    expect(capturedAnchor).not.toBeNull();
    expect(capturedAnchor!.download).toBe('mon-fichier.md');
    appendSpy.mockRestore();
  });

  it('triggers a click on the anchor', () => {
    downloadMarkdown('test.md', 'contenu');
    expect(clickSpy).toHaveBeenCalledTimes(1);
  });

  it('revokes the object URL after triggering the download', () => {
    downloadMarkdown('test.md', 'contenu');
    expect(revokeObjectURLSpy).toHaveBeenCalledWith('blob:mock-url');
  });
});
