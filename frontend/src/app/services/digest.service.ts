import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import {
  CustomSearchResponse,
  CustomSearchSummary,
  DigestResponse,
  HistoryDay,
  RunResponse,
} from '../models/article.model';

@Injectable({ providedIn: 'root' })
export class DigestService {
  private readonly base = '/api';

  constructor(private http: HttpClient) {}

  getToday(): Observable<DigestResponse> {
    return this.http.get<DigestResponse>(`${this.base}/digest/today`);
  }

  getByDate(date: string): Observable<DigestResponse> {
    return this.http.get<DigestResponse>(`${this.base}/digest/${date}`);
  }

  getHistory(): Observable<{ days: HistoryDay[] }> {
    return this.http.get<{ days: HistoryDay[] }>(`${this.base}/history`);
  }

  run(force = false): Observable<RunResponse> {
    return this.http.post<RunResponse>(
      `${this.base}/run${force ? '?force=true' : ''}`,
      {},
    );
  }

  searchCustom(query: string): Observable<CustomSearchResponse> {
    return this.http.post<CustomSearchResponse>(`${this.base}/search`, { query });
  }

  listSearches(): Observable<{ searches: CustomSearchSummary[] }> {
    return this.http.get<{ searches: CustomSearchSummary[] }>(`${this.base}/searches`);
  }

  getSearch(id: number): Observable<CustomSearchResponse> {
    return this.http.get<CustomSearchResponse>(`${this.base}/searches/${id}`);
  }

  deleteSearch(id: number): Observable<{ deleted: number }> {
    return this.http.delete<{ deleted: number }>(`${this.base}/searches/${id}`);
  }
}
