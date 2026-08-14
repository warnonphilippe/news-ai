import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ExportButtonComponent } from './export-button.component';
import * as markdownExport from '../../utils/markdown-export';
import { Article } from '../../models/article.model';

function makeArticle(): Article {
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
  };
}

describe('ExportButtonComponent', () => {
  let fixture: ComponentFixture<ExportButtonComponent>;
  let component: ExportButtonComponent;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ExportButtonComponent],
    }).compileComponents();
    fixture = TestBed.createComponent(ExportButtonComponent);
    component = fixture.componentInstance;
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it('disables the button when the article list is empty', () => {
    component.articles = [];
    component.contextLabel = 'Test';
    fixture.detectChanges();
    const button: HTMLButtonElement = fixture.nativeElement.querySelector('button');
    expect(button.disabled).toBe(true);
  });

  it('enables the button when there is at least one article', () => {
    component.articles = [makeArticle()];
    component.contextLabel = 'Test';
    fixture.detectChanges();
    const button: HTMLButtonElement = fixture.nativeElement.querySelector('button');
    expect(button.disabled).toBe(false);
  });

  it('calls buildDigestMarkdown and downloadMarkdown with the right arguments on click', () => {
    const buildSpy = jest.spyOn(markdownExport, 'buildDigestMarkdown').mockReturnValue('# md');
    const downloadSpy = jest.spyOn(markdownExport, 'downloadMarkdown').mockImplementation(() => {});
    const articles = [makeArticle()];

    component.articles = articles;
    component.contextLabel = 'Sélection du 2026-08-14';
    fixture.detectChanges();

    component.onExport();

    expect(buildSpy).toHaveBeenCalledWith(articles, 'Sélection du 2026-08-14');
    expect(downloadSpy).toHaveBeenCalledWith('selection-du-2026-08-14.md', '# md');
  });

  it('clicking the button triggers the export', () => {
    const exportSpy = jest.spyOn(component, 'onExport').mockImplementation(() => {});
    component.articles = [makeArticle()];
    component.contextLabel = 'Test';
    fixture.detectChanges();

    fixture.nativeElement.querySelector('button').click();
    expect(exportSpy).toHaveBeenCalled();
  });
});
