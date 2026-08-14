import { ComponentFixture, TestBed } from '@angular/core/testing';
import { HistorySidebarComponent } from './history-sidebar.component';
import { HistoryDay } from '../../models/article.model';

describe('HistorySidebarComponent', () => {
  let fixture: ComponentFixture<HistorySidebarComponent>;
  let component: HistorySidebarComponent;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [HistorySidebarComponent],
    }).compileComponents();
    fixture = TestBed.createComponent(HistorySidebarComponent);
    component = fixture.componentInstance;
  });

  it('shows the empty hint when there are no days', () => {
    component.days = [];
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Aucun jour enregistré');
  });

  it('renders one item per day', () => {
    const days: HistoryDay[] = [
      { run_date: '2026-08-14', status: 'done', count: 5 },
      { run_date: '2026-08-13', status: 'done', count: 3 },
    ];
    component.days = days;
    fixture.detectChanges();
    const items = fixture.nativeElement.querySelectorAll('.sidebar__item');
    expect(items.length).toBe(2);
  });

  it('displays the date and count for each item', () => {
    component.days = [{ run_date: '2026-08-14', status: 'done', count: 5 }];
    fixture.detectChanges();
    const item = fixture.nativeElement.querySelector('.sidebar__item');
    expect(item.querySelector('.sidebar__date').textContent).toContain('2026-08-14');
    expect(item.querySelector('.sidebar__count').textContent).toContain('5');
  });

  it('marks the selected day as active', () => {
    component.days = [
      { run_date: '2026-08-14', status: 'done', count: 5 },
      { run_date: '2026-08-13', status: 'done', count: 3 },
    ];
    component.selected = '2026-08-13';
    fixture.detectChanges();
    const items: NodeListOf<HTMLElement> = fixture.nativeElement.querySelectorAll('.sidebar__item');
    expect(items[0].classList.contains('sidebar__item--active')).toBe(false);
    expect(items[1].classList.contains('sidebar__item--active')).toBe(true);
  });

  it('no item is active when selected does not match any day', () => {
    component.days = [{ run_date: '2026-08-14', status: 'done', count: 5 }];
    component.selected = '2020-01-01';
    fixture.detectChanges();
    const item: HTMLElement = fixture.nativeElement.querySelector('.sidebar__item');
    expect(item.classList.contains('sidebar__item--active')).toBe(false);
  });

  it('emits pick with the clicked day\'s run_date', () => {
    component.days = [{ run_date: '2026-08-14', status: 'done', count: 5 }];
    fixture.detectChanges();
    const emitSpy = jest.spyOn(component.pick, 'emit');

    const item: HTMLElement = fixture.nativeElement.querySelector('.sidebar__item');
    item.click();

    expect(emitSpy).toHaveBeenCalledWith('2026-08-14');
  });

  describe('custom search rubric', () => {
    function customItem(root: HTMLElement): HTMLElement | null {
      return root.querySelector('.sidebar__list--custom .sidebar__item');
    }

    it('is hidden while no custom search has been run', () => {
      component.customQuery = null;
      fixture.detectChanges();
      expect(customItem(fixture.nativeElement)).toBeNull();
      expect(fixture.nativeElement.textContent).not.toContain('Recherche personnalisée');
    });

    it('shows the memorised query and its result count', () => {
      component.customQuery = 'RAG avec pgvector';
      component.customCount = 7;
      fixture.detectChanges();
      const item = customItem(fixture.nativeElement)!;
      expect(item.querySelector('.sidebar__query')!.textContent).toContain('RAG avec pgvector');
      expect(item.querySelector('.sidebar__count')!.textContent).toContain('7');
    });

    it('shows a placeholder count while the search is still running', () => {
      component.customQuery = 'RAG';
      component.customLoading = true;
      fixture.detectChanges();
      expect(customItem(fixture.nativeElement)!.querySelector('.sidebar__count')!.textContent)
        .toContain('…');
    });

    it('is shown as active when the custom rubric is the one displayed', () => {
      component.customQuery = 'RAG';
      component.customActive = true;
      fixture.detectChanges();
      expect(customItem(fixture.nativeElement)!.classList).toContain('sidebar__item--active');
    });

    it('is not active when a date is displayed instead', () => {
      component.customQuery = 'RAG';
      component.customActive = false;
      fixture.detectChanges();
      expect(customItem(fixture.nativeElement)!.classList).not.toContain('sidebar__item--active');
    });

    it('emits pickCustom when clicked', () => {
      component.customQuery = 'RAG';
      fixture.detectChanges();
      const emitSpy = jest.spyOn(component.pickCustom, 'emit');

      customItem(fixture.nativeElement)!.click();

      expect(emitSpy).toHaveBeenCalled();
    });

    it('renders an empty-string query as a real rubric (recherche du jour exclue)', () => {
      // customQuery n'est jamais '' en pratique (la barre route les criteres
      // vides vers la recherche du jour) : on verifie juste que le garde est
      // bien `!== null` et non une simple verite booleenne.
      component.customQuery = '';
      fixture.detectChanges();
      expect(customItem(fixture.nativeElement)).not.toBeNull();
    });
  });
});
