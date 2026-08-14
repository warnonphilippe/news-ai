import { ComponentFixture, TestBed } from '@angular/core/testing';
import { CustomSearchResultsComponent } from './custom-search-results.component';
import { Article } from '../../models/article.model';

function makeArticle(overrides: Partial<Article> = {}): Article {
  return {
    id: null,
    run_date: null,
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

describe('CustomSearchResultsComponent', () => {
  let fixture: ComponentFixture<CustomSearchResultsComponent>;
  let component: CustomSearchResultsComponent;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [CustomSearchResultsComponent],
    }).compileComponents();
    fixture = TestBed.createComponent(CustomSearchResultsComponent);
    component = fixture.componentInstance;
  });

  it('renders the query in the title', () => {
    component.query = 'RAG avec pgvector';
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.digest__title').textContent).toContain(
      'Recherche : « RAG avec pgvector »',
    );
  });

  it('shows the loading message while loading', () => {
    component.loading = true;
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.digest__status').textContent).toContain(
      'Recherche en cours…',
    );
    expect(fixture.nativeElement.querySelector('.digest__loading')).not.toBeNull();
  });

  it('shows the error message when an error is set', () => {
    component.loading = false;
    component.error = 'La recherche a échoué.';
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.digest__status').textContent).toContain(
      'La recherche a échoué.',
    );
  });

  it('shows the article count when done without error', () => {
    component.loading = false;
    component.error = null;
    component.articles = [makeArticle(), makeArticle()];
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.digest__status').textContent).toContain(
      '2 article(s)',
    );
  });

  it('shows the empty message when done with no articles and no error', () => {
    component.loading = false;
    component.error = null;
    component.articles = [];
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.digest__empty')).not.toBeNull();
    expect(fixture.nativeElement.textContent).toContain('Aucun article ne correspond à ce critère');
  });

  it('hides the empty message while loading, even with an empty article list', () => {
    component.loading = true;
    component.articles = [];
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.digest__empty')).toBeNull();
  });

  it('hides the empty message when there is an error', () => {
    component.loading = false;
    component.error = 'boom';
    component.articles = [];
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.digest__empty')).toBeNull();
  });

  it('renders one digest-card per article', () => {
    component.articles = [makeArticle(), makeArticle(), makeArticle()];
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelectorAll('app-digest-card').length).toBe(3);
  });

  it('emits clear when the "back" button is clicked', () => {
    fixture.detectChanges();
    const emitSpy = jest.spyOn(component.clear, 'emit');

    const button: HTMLButtonElement = Array.from(
      fixture.nativeElement.querySelectorAll('button'),
    ).find((b: HTMLButtonElement) => b.textContent?.includes('Revenir')) as HTMLButtonElement;
    button.click();

    expect(emitSpy).toHaveBeenCalled();
  });

  it('renders the export button', () => {
    component.query = 'test';
    component.articles = [makeArticle()];
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('app-export-button')).not.toBeNull();
  });
});
