import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Subject, Subscription, of, throwError } from 'rxjs';
import * as rxjs from 'rxjs';

import { AppComponent } from './app.component';
import { DigestService } from './services/digest.service';
import {
  Article,
  CustomSearchResponse,
  CustomSearchSummary,
  DigestResponse,
  HistoryDay,
} from './models/article.model';

function makeDigestResponse(overrides: Partial<DigestResponse> = {}): DigestResponse {
  return { run_date: '2026-08-14', status: 'done', articles: [], ...overrides };
}

function makeSearchResponse(overrides: Partial<CustomSearchResponse> = {}): CustomSearchResponse {
  return {
    id: 1,
    query: 'q',
    created_at: '2026-08-14T10:00:00',
    count: 0,
    articles: [],
    ...overrides,
  };
}

function makeSummary(overrides: Partial<CustomSearchSummary> = {}): CustomSearchSummary {
  return {
    id: 1,
    query: 'q',
    created_at: '2026-08-14T10:00:00',
    count: 0,
    ...overrides,
  };
}

/** Lit l'abonnement de polling prive du composant (verifie juste sa presence :
 * la mecanique de `interval()`/`switchMap()` elle-meme est un comportement
 * RxJS deja fiable, hors perimetre de ce composant). */
function getPollSub(c: AppComponent): Subscription | undefined {
  return (c as unknown as { poll?: Subscription }).poll;
}

describe('AppComponent', () => {
  let fixture: ComponentFixture<AppComponent>;
  let component: AppComponent;
  let svc: {
    getToday: jest.Mock;
    getByDate: jest.Mock;
    getHistory: jest.Mock;
    run: jest.Mock;
    searchCustom: jest.Mock;
    listSearches: jest.Mock;
    getSearch: jest.Mock;
    deleteSearch: jest.Mock;
  };

  beforeEach(async () => {
    svc = {
      getToday: jest.fn().mockReturnValue(of(makeDigestResponse())),
      getByDate: jest.fn().mockReturnValue(of(makeDigestResponse())),
      getHistory: jest.fn().mockReturnValue(of({ days: [] as HistoryDay[] })),
      run: jest
        .fn()
        .mockReturnValue(of({ run_date: '2026-08-14', status: 'running', action: 'started' })),
      searchCustom: jest.fn().mockReturnValue(of(makeSearchResponse())),
      listSearches: jest.fn().mockReturnValue(of({ searches: [] as CustomSearchSummary[] })),
      getSearch: jest.fn().mockReturnValue(of(makeSearchResponse())),
      deleteSearch: jest.fn().mockReturnValue(of({ deleted: 1 })),
    };

    await TestBed.configureTestingModule({
      imports: [AppComponent],
      providers: [{ provide: DigestService, useValue: svc }],
    }).compileComponents();

    fixture = TestBed.createComponent(AppComponent);
    component = fixture.componentInstance;
  });

  afterEach(() => {
    component.ngOnDestroy();
  });

  describe('ngOnInit', () => {
    it('loads the today digest and sets today/selectedDate/status/articles', () => {
      const art = { title: 'A' } as Article;
      svc.getToday.mockReturnValue(
        of(makeDigestResponse({ run_date: '2026-08-10', status: 'done', articles: [art] })),
      );
      fixture.detectChanges();

      expect(component.today).toBe('2026-08-10');
      expect(component.selectedDate).toBe('2026-08-10');
      expect(component.status).toBe('done');
      expect(component.articles).toEqual([art]);
    });

    it('loads the history index', () => {
      const days: HistoryDay[] = [{ run_date: '2026-08-10', status: 'done', count: 3 }];
      svc.getHistory.mockReturnValue(of({ days }));
      fixture.detectChanges();
      expect(component.history).toEqual(days);
    });

    it('starts polling when today is already running', () => {
      svc.getToday.mockReturnValue(of(makeDigestResponse({ status: 'running' })));
      fixture.detectChanges();
      expect(getPollSub(component)).toBeDefined();
      expect(getPollSub(component)!.closed).toBe(false);
    });

    it('does not start polling when today is already done', () => {
      svc.getToday.mockReturnValue(of(makeDigestResponse({ status: 'done' })));
      fixture.detectChanges();
      expect(getPollSub(component)).toBeUndefined();
    });
  });

  describe('isToday', () => {
    it('is true when selectedDate is null', () => {
      component.selectedDate = null;
      expect(component.isToday).toBe(true);
    });

    it('is true when selectedDate equals today', () => {
      component.today = '2026-08-14';
      component.selectedDate = '2026-08-14';
      expect(component.isToday).toBe(true);
    });

    it('is false for a date other than today', () => {
      component.today = '2026-08-14';
      component.selectedDate = '2026-08-10';
      expect(component.isToday).toBe(false);
    });
  });

  describe('selectDate', () => {
    it('switches back to daily mode and fetches the requested date', () => {
      fixture.detectChanges();
      component.mode = 'custom';
      const art = { title: 'Past' } as Article;
      svc.getByDate.mockReturnValue(
        of(makeDigestResponse({ run_date: '2026-08-10', status: 'done', articles: [art] })),
      );

      component.selectDate('2026-08-10');

      expect(component.mode).toBe('daily');
      expect(svc.getByDate).toHaveBeenCalledWith('2026-08-10');
      expect(component.selectedDate).toBe('2026-08-10');
      expect(component.articles).toEqual([art]);
    });

    it('lets an in-flight custom search finish in the background', () => {
      fixture.detectChanges();
      const subject = new Subject<CustomSearchResponse>();
      svc.searchCustom.mockReturnValue(subject.asObservable());

      component.runCustomSearch('recherche en cours');
      expect(component.customLoading).toBe(true);

      component.selectDate('2026-08-10');
      const late = { title: 'Arrive apres la bascule' } as Article;
      subject.next(makeSearchResponse({ query: 'recherche en cours', count: 1, articles: [late] }));

      // Naviguer d'une rubrique a l'autre ne doit rien perdre.
      expect(component.customResults).toEqual([late]);
      expect(component.customLoading).toBe(false);
      expect(component.mode).toBe('daily');
    });

    it('starts polling if the selected date is today and still running', () => {
      fixture.detectChanges();
      svc.getByDate.mockReturnValue(of(makeDigestResponse({ status: 'running' })));

      component.selectDate(component.today);

      expect(getPollSub(component)).toBeDefined();
      expect(getPollSub(component)!.closed).toBe(false);
    });

    it('does not start polling for a past date even if reported as running', () => {
      fixture.detectChanges();
      svc.getByDate.mockReturnValue(of(makeDigestResponse({ status: 'running' })));

      component.selectDate('2020-01-01'); // different from component.today

      expect(getPollSub(component)).toBeUndefined();
    });

    it('stops any active polling when switching to a non-today date', () => {
      svc.getToday.mockReturnValue(of(makeDigestResponse({ status: 'running' })));
      fixture.detectChanges();
      expect(getPollSub(component)!.closed).toBe(false);

      svc.getByDate.mockReturnValue(of(makeDigestResponse({ status: 'done' })));
      component.selectDate('2020-01-01');

      expect(getPollSub(component)!.closed).toBe(true);
    });
  });

  describe('onSearch (barre de recherche unique)', () => {
    it('routes a non-empty criterion to the custom search', () => {
      fixture.detectChanges();
      component.onSearch('RAG avec pgvector');
      expect(svc.searchCustom).toHaveBeenCalledWith('RAG avec pgvector');
      expect(svc.run).not.toHaveBeenCalled();
      expect(component.mode).toBe('custom');
    });

    it('routes an empty criterion to the daily search', () => {
      fixture.detectChanges();
      component.onSearch('');
      expect(svc.run).toHaveBeenCalled();
      expect(svc.searchCustom).not.toHaveBeenCalled();
      expect(component.mode).toBe('daily');
    });
  });

  describe('searchPending', () => {
    it('is false when nothing is running', () => {
      fixture.detectChanges();
      expect(component.searchPending).toBe(false);
    });

    it('is true while a custom search is loading', () => {
      fixture.detectChanges();
      component.customLoading = true;
      expect(component.searchPending).toBe(true);
    });

    it('is true while today is running', () => {
      svc.getToday.mockReturnValue(of(makeDigestResponse({ status: 'running' })));
      fixture.detectChanges();
      expect(component.searchPending).toBe(true);
    });

    it('is false when a past date is running (le run du jour n\'est pas concerne)', () => {
      fixture.detectChanges();
      svc.getByDate.mockReturnValue(of(makeDigestResponse({ status: 'running' })));
      component.selectDate('2020-01-01');
      expect(component.searchPending).toBe(false);
    });
  });

  describe('triggerRun', () => {
    it('sets status to running immediately', () => {
      fixture.detectChanges();
      component.triggerRun();
      expect(component.status).toBe('running');
    });

    it('calls the run service', () => {
      fixture.detectChanges();
      component.triggerRun();
      expect(svc.run).toHaveBeenCalled();
    });

    it('starts polling once the run request is acknowledged', () => {
      fixture.detectChanges();
      component.triggerRun();
      expect(getPollSub(component)).toBeDefined();
      expect(getPollSub(component)!.closed).toBe(false);
    });

    it('switches back to the daily view on today', () => {
      fixture.detectChanges();
      component.mode = 'custom';
      component.selectedDate = '2020-01-01';

      component.triggerRun();

      expect(component.mode).toBe('daily');
      expect(component.selectedDate).toBe(component.today);
    });

    it('re-displays the existing selection without polling when the run is skipped', () => {
      fixture.detectChanges();
      const art = { title: 'Deja fait' } as Article;
      svc.run.mockReturnValue(
        of({ run_date: component.today, status: 'done', action: 'skipped' }),
      );
      svc.getByDate.mockReturnValue(
        of(makeDigestResponse({ status: 'done', articles: [art] })),
      );

      component.triggerRun();

      expect(component.status).toBe('done');
      expect(component.articles).toEqual([art]);
      expect(getPollSub(component)).toBeUndefined();
    });
  });

  describe('poll tick behavior (interval mocked to avoid virtual-timer flakiness)', () => {
    it('updates status/articles on each tick and keeps polling while running', () => {
      const ticks = new Subject<number>();
      jest.spyOn(rxjs, 'interval').mockReturnValue(ticks.asObservable());
      svc.getToday.mockReturnValue(of(makeDigestResponse({ status: 'running' })));
      fixture.detectChanges(); // demarre le polling avec l'intervalle mocke

      const art = { title: 'Poll result' } as Article;
      svc.getToday.mockReturnValue(of(makeDigestResponse({ status: 'running', articles: [art] })));
      ticks.next(0);

      expect(component.articles).toEqual([art]);
      expect(component.status).toBe('running');
      expect(getPollSub(component)!.closed).toBe(false);

      jest.restoreAllMocks();
    });

    it('stops polling and refreshes history once a tick reports non-running status', () => {
      const ticks = new Subject<number>();
      jest.spyOn(rxjs, 'interval').mockReturnValue(ticks.asObservable());
      svc.getToday.mockReturnValue(of(makeDigestResponse({ status: 'running' })));
      fixture.detectChanges();

      svc.getHistory.mockClear();
      svc.getToday.mockReturnValue(of(makeDigestResponse({ status: 'done' })));
      ticks.next(0);

      expect(component.status).toBe('done');
      expect(getPollSub(component)!.closed).toBe(true);
      expect(svc.getHistory).toHaveBeenCalled();

      jest.restoreAllMocks();
    });
  });

  describe('runCustomSearch', () => {
    it('switches to custom mode and marks loading immediately', () => {
      fixture.detectChanges();
      const subject = new Subject<CustomSearchResponse>();
      svc.searchCustom.mockReturnValue(subject.asObservable());

      component.runCustomSearch('ma requete');

      expect(component.mode).toBe('custom');
      expect(component.customQuery).toBe('ma requete');
      expect(component.customLoading).toBe(true);
      expect(component.customResults).toEqual([]);
      expect(component.customError).toBeNull();
    });

    it('populates results and clears loading on success', () => {
      fixture.detectChanges();
      const articles = [{ title: 'A' } as Article];
      svc.searchCustom.mockReturnValue(of(makeSearchResponse({ count: 1, articles })));

      component.runCustomSearch('q');

      expect(component.customResults).toEqual(articles);
      expect(component.customLoading).toBe(false);
    });

    it('sets the server-provided error detail and clears loading on failure', () => {
      fixture.detectChanges();
      svc.searchCustom.mockReturnValue(
        throwError(() => ({ error: { detail: 'critere invalide' } })),
      );

      component.runCustomSearch('q');

      expect(component.customError).toBe('critere invalide');
      expect(component.customLoading).toBe(false);
    });

    it('falls back to a generic message when no error detail is provided', () => {
      fixture.detectChanges();
      svc.searchCustom.mockReturnValue(throwError(() => new Error('network down')));

      component.runCustomSearch('q');

      expect(component.customError).toBe('La recherche a échoué. Réessayez.');
    });

    it('cancels a previous in-flight search so a late response cannot overwrite a newer one', () => {
      fixture.detectChanges();
      const first = new Subject<CustomSearchResponse>();
      const second = new Subject<CustomSearchResponse>();
      svc.searchCustom
        .mockReturnValueOnce(first.asObservable())
        .mockReturnValueOnce(second.asObservable());

      component.runCustomSearch('premiere');
      component.runCustomSearch('seconde');

      second.next(makeSearchResponse({ id: 2, query: 'seconde', count: 1, articles: [{ title: 'B' } as Article] }));
      first.next(makeSearchResponse({ id: 1, query: 'premiere', count: 1, articles: [{ title: 'A (perimee)' } as Article] }));

      expect(component.customResults).toEqual([{ title: 'B' }]);
    });
  });

  describe('showCustom / exitCustomMode (navigation entre rubriques)', () => {
    it('exitCustomMode returns to the digest while keeping the custom search', () => {
      fixture.detectChanges();
      const results = [{ title: 'X' } as Article];
      component.mode = 'custom';
      component.customQuery = 'q';
      component.customResults = results;

      component.exitCustomMode();

      expect(component.mode).toBe('daily');
      expect(component.customQuery).toBe('q');
      expect(component.customResults).toBe(results);
    });

    it('showCustom re-reads a stored search without re-running it', () => {
      fixture.detectChanges();
      const results = [{ title: 'X' } as Article];
      svc.getSearch.mockReturnValue(
        of(makeSearchResponse({ id: 7, query: 'stockee', count: 1, articles: results })),
      );

      component.showCustom(7);

      expect(component.mode).toBe('custom');
      expect(component.activeSearchId).toBe(7);
      expect(component.customQuery).toBe('stockee');
      expect(component.customResults).toEqual(results);
      expect(svc.getSearch).toHaveBeenCalledWith(7);
      // Aucune nouvelle recherche : pas d'appel aux moteurs ni au LLM.
      expect(svc.searchCustom).not.toHaveBeenCalled();
    });

    it('showCustom shows the known query while the articles are loading', () => {
      fixture.detectChanges();
      component.searches = [makeSummary({ id: 4, query: 'deja connue' })];
      svc.getSearch.mockReturnValue(new Subject<CustomSearchResponse>().asObservable());

      component.showCustom(4);

      expect(component.customQuery).toBe('deja connue');
      expect(component.customLoading).toBe(true);
    });

    it('showCustom reports an error when the stored search is gone', () => {
      fixture.detectChanges();
      svc.getSearch.mockReturnValue(throwError(() => new Error('404')));

      component.showCustom(9);

      expect(component.customError).toBe('Cette recherche n’est plus disponible.');
      expect(component.customLoading).toBe(false);
    });

    it('showCustom cancels an in-flight search so its late response cannot leak in', () => {
      fixture.detectChanges();
      const pending = new Subject<CustomSearchResponse>();
      svc.searchCustom.mockReturnValue(pending.asObservable());
      component.runCustomSearch('en cours');

      svc.getSearch.mockReturnValue(
        of(makeSearchResponse({ id: 5, query: 'stockee', count: 1, articles: [{ title: 'Stockee' } as Article] })),
      );
      component.showCustom(5);
      pending.next(makeSearchResponse({ id: 6, articles: [{ title: 'Trop tard' } as Article] }));

      expect(component.customResults).toEqual([{ title: 'Stockee' }]);
      expect(component.activeSearchId).toBe(5);
    });
  });

  describe('persistance des recherches', () => {
    it('loads the stored searches on init', () => {
      const searches = [makeSummary({ id: 2, query: 'anterieure', count: 3 })];
      svc.listSearches.mockReturnValue(of({ searches }));
      fixture.detectChanges();
      expect(component.searches).toEqual(searches);
    });

    it('keeps every search: a new one does not replace the previous ones', () => {
      fixture.detectChanges();
      svc.searchCustom.mockReturnValue(of(makeSearchResponse({ id: 2, query: 'nouvelle' })));
      svc.listSearches.mockReturnValue(
        of({
          searches: [
            makeSummary({ id: 2, query: 'nouvelle' }),
            makeSummary({ id: 1, query: 'ancienne' }),
          ],
        }),
      );

      component.runCustomSearch('nouvelle');

      expect(component.searches.map((s) => s.query)).toEqual(['nouvelle', 'ancienne']);
      expect(component.activeSearchId).toBe(2);
    });

    it('does not refresh the list when the search failed', () => {
      fixture.detectChanges();
      svc.listSearches.mockClear();
      svc.searchCustom.mockReturnValue(throwError(() => new Error('KO')));

      component.runCustomSearch('q');

      expect(svc.listSearches).not.toHaveBeenCalled();
      expect(component.activeSearchId).toBeNull();
    });

    it('marks the in-flight search as active until the server assigns an id', () => {
      fixture.detectChanges();
      svc.searchCustom.mockReturnValue(new Subject<CustomSearchResponse>().asObservable());

      component.runCustomSearch('en cours');

      expect(component.activeSearchId).toBeNull();
      expect(component.customLoading).toBe(true);
    });
  });

  describe('deleteSearch', () => {
    it('removes the search from the list', () => {
      fixture.detectChanges();
      component.searches = [makeSummary({ id: 1 }), makeSummary({ id: 2 })];

      component.deleteSearch(1);

      expect(svc.deleteSearch).toHaveBeenCalledWith(1);
      expect(component.searches.map((s) => s.id)).toEqual([2]);
    });

    it('returns to the digest when the displayed search is deleted', () => {
      fixture.detectChanges();
      svc.getSearch.mockReturnValue(of(makeSearchResponse({ id: 3 })));
      component.showCustom(3);
      expect(component.mode).toBe('custom');

      component.deleteSearch(3);

      expect(component.mode).toBe('daily');
    });

    it('stays on the displayed search when another one is deleted', () => {
      fixture.detectChanges();
      svc.getSearch.mockReturnValue(of(makeSearchResponse({ id: 3 })));
      component.showCustom(3);
      component.searches = [makeSummary({ id: 3 }), makeSummary({ id: 8 })];

      component.deleteSearch(8);

      expect(component.mode).toBe('custom');
      expect(component.activeSearchId).toBe(3);
      expect(component.searches.map((s) => s.id)).toEqual([3]);
    });

    it('keeps the list unchanged when the deletion fails', () => {
      fixture.detectChanges();
      component.searches = [makeSummary({ id: 1 })];
      svc.deleteSearch.mockReturnValue(throwError(() => new Error('KO')));

      component.deleteSearch(1);

      expect(component.searches.map((s) => s.id)).toEqual([1]);
    });
  });

  describe('ngOnDestroy', () => {
    it('unsubscribes the poll and custom search subscriptions if active', () => {
      fixture.detectChanges();
      const pollUnsub = jest.fn();
      const customUnsub = jest.fn();
      (component as unknown as { poll: { unsubscribe: () => void } }).poll = {
        unsubscribe: pollUnsub,
      };
      (component as unknown as { customSub: { unsubscribe: () => void } }).customSub = {
        unsubscribe: customUnsub,
      };

      component.ngOnDestroy();

      expect(pollUnsub).toHaveBeenCalled();
      expect(customUnsub).toHaveBeenCalled();
    });

    it('does not throw when no subscriptions were ever created', () => {
      fixture.detectChanges();
      expect(() => component.ngOnDestroy()).not.toThrow();
    });
  });
});
