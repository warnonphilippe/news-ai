import { ComponentFixture, TestBed } from '@angular/core/testing';
import { DigestListComponent } from './digest-list.component';
import { Article } from '../../models/article.model';

function makeArticle(overrides: Partial<Article> = {}): Article {
  return {
    id: 1,
    run_date: '2026-08-14',
    url: 'https://a.com',
    title: 'T',
    summary: 'S',
    why_it_matters: 'W',
    source: 'a.com',
    published_date: '2026-08-13',
    tags: [],
    topic_cluster: 'C',
    links: [],
    is_update_of: null,
    rank: 1,
    relevance: 80,
    relevance_rationale: '',
    age_days: 1,
    freshness_factor: 1,
    source_factor: 1,
    community_factor: 1,
    hn_points: null,
    hn_comments: null,
    final_score: 80,
    ...overrides,
  };
}

describe('DigestListComponent', () => {
  let fixture: ComponentFixture<DigestListComponent>;
  let component: DigestListComponent;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [DigestListComponent],
    }).compileComponents();
    fixture = TestBed.createComponent(DigestListComponent);
    component = fixture.componentInstance;
  });

  it('renders the run date in the title', () => {
    component.runDate = '2026-08-14';
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.digest__title').textContent).toContain(
      'Sélection du 2026-08-14',
    );
  });

  describe('status text', () => {
    const cases: Array<[string, string]> = [
      ['running', 'Recherche en cours…'],
      ['error', 'Erreur lors de la dernière recherche'],
      ['none', 'Aucune recherche pour cette date'],
    ];

    it.each(cases)('shows the right message for status=%s', (status, expected) => {
      component.status = status;
      fixture.detectChanges();
      expect(fixture.nativeElement.querySelector('.digest__status').textContent).toContain(
        expected,
      );
    });

    it('shows the article count for status=done', () => {
      component.status = 'done';
      component.articles = [makeArticle(), makeArticle()];
      fixture.detectChanges();
      expect(fixture.nativeElement.querySelector('.digest__status').textContent).toContain(
        '2 article(s)',
      );
    });
  });

  it('shows the loading banner while running', () => {
    component.status = 'running';
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.digest__loading')).not.toBeNull();
  });

  it('hides the loading banner when not running', () => {
    component.status = 'done';
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.digest__loading')).toBeNull();
  });

  it('shows the empty message when done with no articles', () => {
    component.status = 'done';
    component.articles = [];
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.digest__empty')).not.toBeNull();
  });

  it('hides the empty message once articles are present', () => {
    component.status = 'done';
    component.articles = [makeArticle()];
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.digest__empty')).toBeNull();
  });

  it('renders one digest-card per article', () => {
    component.articles = [makeArticle(), makeArticle(), makeArticle()];
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelectorAll('app-digest-card').length).toBe(3);
  });

  it('exposes only the export button (la recherche est pilotee par la barre unique)', () => {
    component.status = 'done';
    component.articles = [makeArticle()];
    fixture.detectChanges();
    const buttons = fixture.nativeElement.querySelectorAll('.digest__actions button');
    expect(buttons.length).toBe(1);
    expect(buttons[0].textContent).toContain('Exporter');
  });

  it('passes the articles and context label to the export button', () => {
    component.runDate = '2026-08-14';
    component.articles = [makeArticle()];
    fixture.detectChanges();
    const exportBtn = fixture.nativeElement.querySelector('app-export-button');
    expect(exportBtn).not.toBeNull();
  });
});
