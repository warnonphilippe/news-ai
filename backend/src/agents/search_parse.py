"""Parsing des reponses des serveurs MCP de recherche + normalisation d'URL.

Les serveurs MCP renvoient soit du JSON, soit du texte non structure
(format Exa : blocs "Title: ... / URL: ... / Published Date: ... / Text: ...").
Ces helpers ramenent tout a une liste de dicts homogenes :
    {title, url, published_date, source, snippet}
"""

import json
import re
from typing import Any, Dict, List
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

# Parametres de tracking a supprimer lors de la normalisation d'URL.
_TRACKING_PARAMS = re.compile(r"^(utm_|fbclid$|gclid$|mc_|ref$|ref_src$|igshid$)")


def normalize_url(url: str) -> str:
    """Normalise une URL pour la deduplication (cle stable).

    - schema/host en minuscules, retire 'www.'
    - supprime le fragment (#...)
    - retire les parametres de tracking et trie les parametres restants
    - retire un slash final
    """
    if not url:
        return ""
    try:
        p = urlparse(url.strip())
    except ValueError:
        return url.strip().lower()

    scheme = (p.scheme or "https").lower()
    host = (p.netloc or "").lower()
    if host.startswith("www."):
        host = host[4:]

    path = p.path.rstrip("/")

    query_pairs = [
        (k, v)
        for k, v in parse_qsl(p.query, keep_blank_values=True)
        if not _TRACKING_PARAMS.match(k)
    ]
    query = urlencode(sorted(query_pairs))

    return urlunparse((scheme, host, path, "", query, ""))


def domain_of(url: str) -> str:
    """Retourne le domaine (sans www) d'une URL — utilise comme 'source'."""
    try:
        host = urlparse(url).netloc.lower()
        return host[4:] if host.startswith("www.") else host
    except ValueError:
        return ""


def _coerce_json_records(data: Any) -> List[Dict[str, Any]]:
    """Extrait une liste de records depuis une structure JSON variable."""
    if isinstance(data, list):
        return [r for r in data if isinstance(r, dict)]
    if isinstance(data, dict):
        for key in ("results", "data", "items"):
            if isinstance(data.get(key), list):
                return [r for r in data[key] if isinstance(r, dict)]
        # Un seul objet
        return [data]
    return []


def _record_to_article(rec: Dict[str, Any], provider: str) -> Dict[str, Any]:
    url = rec.get("url") or rec.get("link") or rec.get("id") or ""
    title = rec.get("title") or rec.get("name") or url
    published = (
        rec.get("publishedDate")
        or rec.get("published_date")
        or rec.get("published")
        or rec.get("date")
        or rec.get("age")
        or ""
    )
    snippet = (
        rec.get("text")
        or rec.get("snippet")
        or rec.get("description")
        or rec.get("summary")
        or rec.get("content")
        or ""
    )
    return {
        "title": (title or "").strip(),
        "url": (url or "").strip(),
        "published_date": str(published).strip(),
        "source": domain_of(url),
        "snippet": (snippet or "").strip()[:4000],
        "provider": provider,
    }


# Detection generique d'une ligne "Label: valeur".
_FIELD_RE = re.compile(r"^([A-Za-z][A-Za-z ]{0,24}?)\s*:\s*(.*)$")

# Mapping des libelles (minuscules) vers nos cles canoniques.
# Exa / Brave utilisent des libelles variables (Published, Description, Snippet...).
_LABEL_MAP = {
    "title": "title",
    "url": "url",
    "link": "url",
    "published date": "published_date",
    "published": "published_date",
    "date": "published_date",
    "age": "published_date",
    "text": "text",
    "description": "text",
    "snippet": "text",
    "summary": "text",
    "content": "text",
    "highlights": "text",
    "highlight": "text",
}
# Libelles connus qu'on ignore silencieusement (bruit).
_IGNORED_LABELS = {"author", "score", "image", "favicon", "id"}


def _parse_text_blocks(text: str, provider: str) -> List[Dict[str, Any]]:
    """Parse un format texte 'Title: .. / URL: .. / Description: ..' robuste."""
    articles: List[Dict[str, Any]] = []
    current: Dict[str, str] = {}
    current_key = None

    def clean(value: str) -> str:
        value = (value or "").strip()
        return "" if value.upper() in ("N/A", "NONE", "NULL") else value

    def flush():
        if current.get("url") or current.get("title"):
            url = clean(current.get("url", ""))
            articles.append(
                {
                    "title": clean(current.get("title", "")) or url,
                    "url": url,
                    "published_date": clean(current.get("published_date", "")),
                    "source": domain_of(url),
                    "snippet": clean(current.get("text", ""))[:4000],
                    "provider": provider,
                }
            )

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        m = _FIELD_RE.match(stripped)
        if m:
            label = m.group(1).strip().lower()
            value = m.group(2)
            if label == "title" and current:
                flush()
                current = {}
                current_key = None
            if label in _IGNORED_LABELS:
                current_key = None
                continue
            key = _LABEL_MAP.get(label)
            if key:
                current[key] = (current.get(key, "") + " " + value).strip()
                current_key = key
                continue
            # Libelle inconnu : on le rattache au texte courant.
            if current_key:
                current[current_key] += " " + stripped
            continue
        # Ligne sans libelle : continuation du dernier champ.
        if current_key:
            current[current_key] += " " + stripped

    flush()
    return articles


def parse_mcp_text(raw_text: str, provider: str) -> List[Dict[str, Any]]:
    """Parse le contenu texte renvoye par un tool MCP (JSON ou format texte)."""
    if not raw_text:
        return []
    stripped = raw_text.strip()
    if stripped.startswith("[") or stripped.startswith("{"):
        try:
            return [
                _record_to_article(r, provider)
                for r in _coerce_json_records(json.loads(stripped))
            ]
        except json.JSONDecodeError:
            pass
    return _parse_text_blocks(stripped, provider)
