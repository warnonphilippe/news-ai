import { ComponentFixture, TestBed } from '@angular/core/testing';
import { DigestCardComponent } from './digest-card.component';
import { Article } from '../../models/article.model';

function makeArticle(overrides: Partial<Article> = {}): Article {
  return {
    id: 1,
    run_date: '2026-08-14',
    url: 'https://example.com/article',
    title: 'Titre de test',
    summary: 'Un resume.',
    why_it_matters: 'Ca compte.',
    source: 'example.com',
    published_date: '2026-08-13',
    tags: ['AI'],
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

describe('DigestCardComponent', () => {
  let fixture: ComponentFixture<DigestCardComponent>;
  let component: DigestCardComponent;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [DigestCardComponent],
    }).compileComponents();
    fixture = TestBed.createComponent(DigestCardComponent);
    component = fixture.componentInstance;
  });

  function setArticle(article: Article): void {
    component.article = article;
    fixture.detectChanges();
  }

  describe('ageLabel', () => {
    it('returns empty string when age is null and no published_date', () => {
      component.article = makeArticle({ age_days: null, published_date: '' });
      expect(component.ageLabel).toBe('');
    });

    it('returns "date inconnue" when age is null but a published_date exists', () => {
      component.article = makeArticle({ age_days: null, published_date: '2026-08-01' });
      expect(component.ageLabel).toBe('date inconnue');
    });

    it('returns "aujourd\'hui" for age 0', () => {
      component.article = makeArticle({ age_days: 0 });
      expect(component.ageLabel).toBe("aujourd'hui");
    });

    it('treats a negative age as today (defensive floor)', () => {
      component.article = makeArticle({ age_days: -1 });
      expect(component.ageLabel).toBe("aujourd'hui");
    });

    it('returns "hier" for age 1', () => {
      component.article = makeArticle({ age_days: 1 });
      expect(component.ageLabel).toBe('hier');
    });

    it('returns "il y a N jours" for age > 1', () => {
      component.article = makeArticle({ age_days: 5 });
      expect(component.ageLabel).toBe('il y a 5 jours');
    });
  });

  describe('scoreDetail', () => {
    it('formats all components when present', () => {
      component.article = makeArticle({
        relevance: 80,
        freshness_factor: 0.9,
        source_factor: 1.1,
        community_factor: 1.05,
        final_score: 92.4,
      });
      expect(component.scoreDetail).toBe(
        'pertinence 80 × fraîcheur 0.9 × source 1.1 × communauté 1.05 = 92.4',
      );
    });

    it('uses "?" placeholders for null components', () => {
      component.article = makeArticle({
        relevance: null,
        freshness_factor: null,
        source_factor: null,
        community_factor: null,
        final_score: null,
      });
      expect(component.scoreDetail).toBe('pertinence ? × fraîcheur ? × source ? × communauté ? = ?');
    });
  });

  describe('hnUrl', () => {
    it('builds an Algolia HN search URL with the encoded article URL', () => {
      component.article = makeArticle({ url: 'https://a.com/x?y=1&z=2' });
      expect(component.hnUrl).toBe(
        `https://hn.algolia.com/?query=${encodeURIComponent('https://a.com/x?y=1&z=2')}&type=story`,
      );
    });
  });

  describe('template rendering', () => {
    it('renders the article title as a link', () => {
      setArticle(makeArticle({ title: 'Mon titre', url: 'https://x.com' }));
      const link: HTMLAnchorElement = fixture.nativeElement.querySelector('.card__title');
      expect(link.textContent).toContain('Mon titre');
      expect(link.href).toBe('https://x.com/');
    });

    it('shows the "complete un sujet precedent" badge when is_update_of is set', () => {
      setArticle(makeArticle({ is_update_of: 42 }));
      const badge = fixture.nativeElement.querySelector('.card__badge');
      expect(badge).not.toBeNull();
      expect(badge.textContent).toContain('Complète un sujet précédent');
    });

    it('hides the badge when is_update_of is null', () => {
      setArticle(makeArticle({ is_update_of: null }));
      expect(fixture.nativeElement.querySelector('.card__badge')).toBeNull();
    });

    it('shows the score badge when final_score is not null', () => {
      setArticle(makeArticle({ final_score: 88 }));
      const score = fixture.nativeElement.querySelector('.card__score');
      expect(score).not.toBeNull();
      expect(score.textContent).toContain('88');
    });

    it('hides the score badge when final_score is null', () => {
      setArticle(makeArticle({ final_score: null }));
      expect(fixture.nativeElement.querySelector('.card__score')).toBeNull();
    });

    it('shows the HN badge when hn_points is truthy', () => {
      setArticle(makeArticle({ hn_points: 42, hn_comments: 5 }));
      const hn = fixture.nativeElement.querySelector('.card__hn');
      expect(hn).not.toBeNull();
      expect(hn.textContent).toContain('42');
    });

    it('hides the HN badge when hn_points is null', () => {
      setArticle(makeArticle({ hn_points: null }));
      expect(fixture.nativeElement.querySelector('.card__hn')).toBeNull();
    });

    it('hides the HN badge when hn_points is zero', () => {
      setArticle(makeArticle({ hn_points: 0 }));
      expect(fixture.nativeElement.querySelector('.card__hn')).toBeNull();
    });

    it('renders the "why it matters" paragraph when present', () => {
      setArticle(makeArticle({ why_it_matters: 'Raison X' }));
      expect(fixture.nativeElement.querySelector('.card__why').textContent).toContain('Raison X');
    });

    it('omits the "why it matters" paragraph when empty', () => {
      setArticle(makeArticle({ why_it_matters: '' }));
      expect(fixture.nativeElement.querySelector('.card__why')).toBeNull();
    });

    it('renders the rationale block when present', () => {
      setArticle(makeArticle({ relevance_rationale: 'Justification Y' }));
      expect(fixture.nativeElement.querySelector('.card__rationale').textContent).toContain(
        'Justification Y',
      );
    });

    it('omits the rationale block when null', () => {
      setArticle(makeArticle({ relevance_rationale: null }));
      expect(fixture.nativeElement.querySelector('.card__rationale')).toBeNull();
    });

    it('renders one tag element per tag', () => {
      setArticle(makeArticle({ tags: ['AI', 'Java', 'RAG'] }));
      const tags = fixture.nativeElement.querySelectorAll('.tag');
      expect(tags.length).toBe(3);
    });

    it('renders no tags container content when tags is empty', () => {
      setArticle(makeArticle({ tags: [] }));
      expect(fixture.nativeElement.querySelectorAll('.tag').length).toBe(0);
    });

    it('renders one link per complementary resource', () => {
      setArticle(
        makeArticle({
          links: [
            { title: 'Doc', url: 'https://d.com' },
            { title: 'Blog', url: 'https://b.com' },
          ],
        }),
      );
      // 1 lien "Lire la source" + 2 liens complementaires = 3 liens dans .card__links
      const links = fixture.nativeElement.querySelectorAll('.card__links a');
      expect(links.length).toBe(3);
    });
  });
});
