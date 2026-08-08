import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import {
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
}
