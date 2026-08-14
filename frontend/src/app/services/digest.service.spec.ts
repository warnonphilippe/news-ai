import { TestBed } from '@angular/core/testing';
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing';
import { provideHttpClient } from '@angular/common/http';

import { DigestService } from './digest.service';
import { CustomSearchResponse, DigestResponse, RunResponse } from '../models/article.model';

describe('DigestService', () => {
  let service: DigestService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(DigestService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  describe('getToday', () => {
    it('issues a GET to /api/digest/today', () => {
      const mockResponse: DigestResponse = { run_date: '2026-08-14', status: 'done', articles: [] };

      service.getToday().subscribe((res) => expect(res).toEqual(mockResponse));

      const req = httpMock.expectOne('/api/digest/today');
      expect(req.request.method).toBe('GET');
      req.flush(mockResponse);
    });
  });

  describe('getByDate', () => {
    it('issues a GET to /api/digest/{date}', () => {
      const mockResponse: DigestResponse = { run_date: '2026-08-10', status: 'done', articles: [] };

      service.getByDate('2026-08-10').subscribe((res) => expect(res).toEqual(mockResponse));

      const req = httpMock.expectOne('/api/digest/2026-08-10');
      expect(req.request.method).toBe('GET');
      req.flush(mockResponse);
    });
  });

  describe('getHistory', () => {
    it('issues a GET to /api/history', () => {
      const mockResponse = { days: [{ run_date: '2026-08-10', status: 'done', count: 5 }] };

      service.getHistory().subscribe((res) => expect(res).toEqual(mockResponse));

      const req = httpMock.expectOne('/api/history');
      expect(req.request.method).toBe('GET');
      req.flush(mockResponse);
    });
  });

  describe('run', () => {
    it('issues a POST to /api/run without force by default', () => {
      const mockResponse: RunResponse = { run_date: '2026-08-14', status: 'running', action: 'started' };

      service.run().subscribe((res) => expect(res).toEqual(mockResponse));

      const req = httpMock.expectOne('/api/run');
      expect(req.request.method).toBe('POST');
      expect(req.request.body).toEqual({});
      req.flush(mockResponse);
    });

    it('appends ?force=true when force is requested', () => {
      const mockResponse: RunResponse = { run_date: '2026-08-14', status: 'running', action: 'started' };

      service.run(true).subscribe((res) => expect(res).toEqual(mockResponse));

      const req = httpMock.expectOne('/api/run?force=true');
      expect(req.request.method).toBe('POST');
      req.flush(mockResponse);
    });

    it('does not append the force param when explicitly false', () => {
      service.run(false).subscribe();
      const req = httpMock.expectOne('/api/run');
      req.flush({ run_date: '', status: '', action: '' });
    });
  });

  describe('searchCustom', () => {
    it('issues a POST to /api/search with the query body', () => {
      const mockResponse: CustomSearchResponse = {
        query: 'RAG avec pgvector',
        count: 1,
        articles: [],
      };

      service
        .searchCustom('RAG avec pgvector')
        .subscribe((res) => expect(res).toEqual(mockResponse));

      const req = httpMock.expectOne('/api/search');
      expect(req.request.method).toBe('POST');
      expect(req.request.body).toEqual({ query: 'RAG avec pgvector' });
      req.flush(mockResponse);
    });
  });
});
