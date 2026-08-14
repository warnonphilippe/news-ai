export interface Link {
  title: string;
  url: string;
}

export interface Article {
  /** null pour un article de recherche personnalisee (jamais persiste). */
  id: number | null;
  run_date: string | null;
  url: string;
  title: string;
  summary: string;
  why_it_matters: string;
  source: string;
  published_date: string;
  tags: string[];
  topic_cluster: string;
  links: Link[];
  is_update_of: number | null;
  rank: number;

  /** Composantes du score de sélection (auditabilité). */
  relevance: number | null;
  relevance_rationale: string | null;
  age_days: number | null;
  freshness_factor: number | null;
  source_factor: number | null;
  community_factor: number | null;
  hn_points: number | null;
  hn_comments: number | null;
  final_score: number | null;
}

export interface DigestResponse {
  run_date: string;
  status: 'none' | 'running' | 'done' | 'error';
  articles: Article[];
}

export interface HistoryDay {
  run_date: string;
  status: string;
  count: number;
}

export interface RunResponse {
  run_date: string;
  status: string;
  action: string;
}

/** Entrée de la liste des recherches mémorisées (sans les articles). */
export interface CustomSearchSummary {
  id: number;
  query: string;
  created_at: string;
  count: number;
}

export interface CustomSearchResponse extends CustomSearchSummary {
  articles: Article[];
}
