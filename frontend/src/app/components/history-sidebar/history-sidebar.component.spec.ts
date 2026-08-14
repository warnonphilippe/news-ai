import { ComponentFixture, TestBed } from '@angular/core/testing';
import { HistorySidebarComponent } from './history-sidebar.component';
import { CustomSearchSummary, HistoryDay } from '../../models/article.model';

function makeSummary(overrides: Partial<CustomSearchSummary> = {}): CustomSearchSummary {
  return {
    id: 1,
    query: 'q',
    created_at: '2026-08-14T10:00:00',
    count: 0,
    ...overrides,
  };
}

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

  describe('renommage', () => {
    it('titles the day list "Conseils du jour"', () => {
      fixture.detectChanges();
      const titles: string[] = Array.from(
        fixture.nativeElement.querySelectorAll('.sidebar__title'),
      ).map((h) => (h as HTMLElement).textContent!.trim());
      expect(titles).toContain('Conseils du jour');
      expect(titles).not.toContain('Historique');
    });
  });

  describe('rubrique des recherches personnalisees', () => {
    function customItems(root: HTMLElement): HTMLElement[] {
      return Array.from(root.querySelectorAll('.sidebar__list--custom .sidebar__item'));
    }

    it('is hidden while nothing has been searched', () => {
      component.searches = [];
      component.pendingQuery = null;
      fixture.detectChanges();
      expect(customItems(fixture.nativeElement)).toHaveLength(0);
      expect(fixture.nativeElement.textContent).not.toContain('Recherches personnalisées');
    });

    it('lists every stored search, not only the last one', () => {
      component.searches = [
        makeSummary({ id: 3, query: 'troisieme', count: 4 }),
        makeSummary({ id: 2, query: 'deuxieme', count: 9 }),
        makeSummary({ id: 1, query: 'premiere', count: 0 }),
      ];
      fixture.detectChanges();

      const items = customItems(fixture.nativeElement);
      expect(items).toHaveLength(3);
      expect(items.map((i) => i.querySelector('.sidebar__query')!.textContent!.trim())).toEqual([
        'troisieme',
        'deuxieme',
        'premiere',
      ]);
      expect(items[1].querySelector('.sidebar__count')!.textContent).toContain('9');
    });

    it('shows the in-flight search above the stored ones with a placeholder count', () => {
      component.searches = [makeSummary({ id: 1, query: 'stockee' })];
      component.pendingQuery = 'en cours';
      fixture.detectChanges();

      const items = customItems(fixture.nativeElement);
      expect(items).toHaveLength(2);
      expect(items[0].querySelector('.sidebar__query')!.textContent).toContain('en cours');
      expect(items[0].querySelector('.sidebar__count')!.textContent).toContain('…');
      // Une recherche encore en vol n'est pas supprimable : rien a supprimer.
      expect(items[0].querySelector('.sidebar__delete')).toBeNull();
    });

    it('marks the displayed search as active', () => {
      component.searches = [makeSummary({ id: 1 }), makeSummary({ id: 2 })];
      component.customActive = true;
      component.activeSearchId = 2;
      fixture.detectChanges();

      const items = customItems(fixture.nativeElement);
      expect(items[0].classList).not.toContain('sidebar__item--active');
      expect(items[1].classList).toContain('sidebar__item--active');
    });

    it('marks the in-flight search as active while it has no id yet', () => {
      component.pendingQuery = 'en cours';
      component.customActive = true;
      component.activeSearchId = null;
      fixture.detectChanges();
      expect(customItems(fixture.nativeElement)[0].classList).toContain(
        'sidebar__item--active',
      );
    });

    it('marks nothing as active while a digest is displayed', () => {
      component.searches = [makeSummary({ id: 1 })];
      component.pendingQuery = 'en cours';
      component.customActive = false;
      component.activeSearchId = 1;
      fixture.detectChanges();

      for (const item of customItems(fixture.nativeElement)) {
        expect(item.classList).not.toContain('sidebar__item--active');
      }
    });

    it('emits pickCustom with the clicked search id', () => {
      component.searches = [makeSummary({ id: 42 })];
      fixture.detectChanges();
      const emitSpy = jest.spyOn(component.pickCustom, 'emit');

      customItems(fixture.nativeElement)[0].click();

      expect(emitSpy).toHaveBeenCalledWith(42);
    });

    it('emits deleteCustom when the cross is clicked', () => {
      component.searches = [makeSummary({ id: 42 })];
      fixture.detectChanges();
      const emitSpy = jest.spyOn(component.deleteCustom, 'emit');

      const cross: HTMLButtonElement = fixture.nativeElement.querySelector('.sidebar__delete');
      cross.click();

      expect(emitSpy).toHaveBeenCalledWith(42);
    });

    it('clicking the cross does not also select the search', () => {
      component.searches = [makeSummary({ id: 42 })];
      fixture.detectChanges();
      const pickSpy = jest.spyOn(component.pickCustom, 'emit');

      const cross: HTMLButtonElement = fixture.nativeElement.querySelector('.sidebar__delete');
      cross.click();

      expect(pickSpy).not.toHaveBeenCalled();
    });

    it('exposes one cross per stored search', () => {
      component.searches = [makeSummary({ id: 1 }), makeSummary({ id: 2 })];
      fixture.detectChanges();
      expect(fixture.nativeElement.querySelectorAll('.sidebar__delete')).toHaveLength(2);
    });
  });
});
