import re
from urllib.parse import urlparse, urljoin, urlunparse, parse_qsl, urlencode
from bs4 import BeautifulSoup
from collections import Counter, defaultdict
from bs4.element import Comment
import hashlib
import unicodedata


seen_hashes = set()  # For exact duplicate detection
seen_simhashes = set()  # For near-duplicate detection

page_hashes = set()
page_shingles = []
longest_page = ("", 0)
word_counter = Counter()
subdomain_counts = defaultdict(int)
report_urls = set()

LOW_INFO_MIN = 30
MAX_BYTES = 5_000_000

STOPWORDS = frozenset({
    'i', 'me', 'my', 'myself', 'we', 'our', 'ours', 'ourselves', 'you',
    "you're", "you've", "you'll", "you'd", 'your', 'yours', 'yourself',
    'yourselves', 'he', 'him', 'his', 'himself', 'she', "she's", 'her',
    'hers', 'herself', 'it', "it's", 'its', 'itself', 'they', 'them',
    'their', 'theirs', 'themselves', 'what', 'which', 'who', 'whom',
    'this', 'that', "that'll", 'these', 'those', 'am', 'is', 'are', 'was',
    'were', 'be', 'been', 'being', 'have', 'has', 'had', 'having', 'do',
    'does', 'did', 'doing', 'a', 'an', 'the', 'and', 'but', 'if', 'or',
    'because', 'as', 'until', 'while', 'of', 'at', 'by', 'for', 'with',
    'about', 'against', 'between', 'into', 'through', 'during', 'before',
    'after', 'above', 'below', 'to', 'from', 'up', 'down', 'in', 'out',
    'on', 'off', 'over', 'under', 'again', 'further', 'then', 'once',
    'here', 'there', 'when', 'where', 'why', 'how', 'all', 'any', 'both',
    'each', 'few', 'more', 'most', 'other', 'some', 'such', 'no', 'nor',
    'not', 'only', 'own', 'same', 'so', 'than', 'too', 'very', 's', 't',
    'can', 'will', 'just', 'don', "don't", 'should', "should've", 'now',
    'd', 'll', 'm', 'o', 're', 've', 'y', 'ain', 'aren', "aren't",
    'couldn', "couldn't", 'didn', "didn't", 'doesn', "doesn't", 'hadn',
    "hadn't", 'hasn', "hasn't", 'haven', "haven't", 'isn', "isn't",
    'ma', 'mightn', "mightn't", 'mustn', "mustn't", 'needn', "needn't",
    'shan', "shan't", 'shouldn', "shouldn't", 'wasn', "wasn't", 'weren',
    "weren't", 'won', "won't", 'wouldn', "wouldn't"
})

seen_hashes = set()


def scraper(url, resp):
    links = extract_next_links(url, resp)
    return [link for link in links if is_valid(link)]


def extract_next_links(url, resp):
    global longest_page

    if resp.status != 200 or resp.raw_response is None or resp.raw_response.content is None:
        return []
    
    content = resp.raw_response.content
    if content is None or len(content) == 0:
        return []
    if len(content) > MAX_BYTES:
        return []

    content_type = resp.raw_response.headers.get("Content-Type", "").lower()
    if "html" not in content_type:
        head = content[:256].lstrip().lower()
        if not (head.startswith(b"<!doctype") and b"html" in head) and not head.startswith(b"<html"):
            return []

    try:
        soup = BeautifulSoup(resp.raw_response.content, "lxml")
    except Exception:
        soup = BeautifulSoup(resp.raw_response.content, "html.parser")

    texts = soup.find_all(string=True)
    visible_texts = (t.strip() for t in texts if _tag_visible(t))
    text_content = " ".join(t for t in visible_texts if t)
    text_content = unicodedata.normalize("NFKC", text_content)

    page_hash = compute_page_hash(text_content)
    dup_exact = False
    if page_hash in seen_hashes:
        print(f"Skipping exact duplicate: {url}")
        dup_exact = True
    else:
        seen_hashes.add(page_hash)

    words = _extract_words(soup)
    simhash = compute_simhash(words)
    dup_near = False
    for old_hash in seen_simhashes:
        if hamming_distance(simhash, old_hash) < 5:
            print(f"Skipping near-duplicate: {url}")
            dup_near = True
            break
    if not dup_near:
        seen_simhashes.add(simhash)

    canonical = normalize_url(resp.url or url)
    report_urls.add(report_key(resp.url or url))
    first_time = canonical not in report_urls
    report_urls.add(canonical)

    count = len(words)
    
    if not dup_exact and not dup_near and count >= LOW_INFO_MIN:
        word_counter.update(w for w in words if w not in STOPWORDS)
        if count > longest_page[1]:
            longest_page = (canonical, count)

    if first_time:
        host = urlparse(canonical).netloc.lower()
        if host.endswith(".uci.edu"):
            subdomain_counts[host] += 1
    else:
        host = urlparse(canonical).netloc.lower()

    raw_links = []
    for link in soup.find_all("a", href=True):
        href = link.get("href").strip()
        try:
            abs_link = urljoin(resp.url or url, href)
        except Exception:
            continue
        raw_links.append(abs_link)

    # --- Adaptive Trap Detection Logic ---
    pages_seen = subdomain_counts.get(host, 0)
    link_limit = 400 + pages_seen * 10          # increase limit gradually
    same_host_limit = 250 + pages_seen * 5      # increase host-link limit gradually

    # 1. Too many outlinks, likely a trap
    if len(raw_links) > link_limit:
        print(f"[Trap] {canonical} has {len(raw_links)} outlinks (limit {link_limit}) — skipping.")
        return []

    # 2. Repetitive pattern trap (calendar, numeric loops)
    def pattern_for(u):
        try:
            p = urlparse(u)
            path = re.sub(r"\d+", "{d}", p.path)
            query = re.sub(r"\d+", "{d}", p.query)
            return f"{p.netloc}{path}?{query}"
        except Exception:
            return ""
    
    patterns = Counter(pattern_for(u) for u in raw_links)
    if patterns:
        most_common, freq = patterns.most_common(1)[0]
        if freq > 80 and freq / len(raw_links) > 0.6:
            print(f"[Trap] {canonical} repeating pattern {most_common} — limiting.")
            raw_links = list({u for u in raw_links if pattern_for(u) != most_common})[:50]

    # 3. Overly concentrated in one host → self-loop or redirect trap
    host_counts = Counter(urlparse(u).netloc.lower() for u in raw_links)
    if host_counts and host_counts.most_common(1)[0][1] > same_host_limit:
        print(f"[Trap] {canonical} has >{same_host_limit} links to same host — trimming.")
        allowed_hosts = {h for h, _ in host_counts.most_common(10)}
        raw_links = [u for u in raw_links if urlparse(u).netloc.lower() in allowed_hosts][:same_host_limit]
    # --- End Adaptive Trap Detection ---

    extracted_links = set()
    for link in raw_links:
        normalized = normalize_url(link)
        if is_valid(normalized):
            extracted_links.add(normalized)

    write_metrics()
    write_subdomain_counts()
    return list(extracted_links)


# Key values in query that are not relevant to the content of a web page
TRACKING_PARAMS = frozenset({
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "gclid", "dclid",
    "fbclid", "igshid",
    "_hsenc", "_hsmi",
    "session", "phpsessid", "jsessionid", "ref", "refsrc", "source",
    "mc_cid", "mc_eid", "trk", "campaignid", "adgroupid"
})


def normalize_url(url: str):
    """Normalize URLs by removing fragments, standardizing hostname, handling ports, and cleaning query parameters."""

    # Add scheme if missing
    if not re.match(r"^https?://", url):
        url = "https://" + url

    parsed = urlparse(url)

    # Scheme
    scheme = parsed.scheme.lower()

    # Hostname: lowercase, remove trailing dots, remove www.
    hostname = (parsed.hostname or "").rstrip(".").lower()
    if hostname.startswith("www."):
        hostname = hostname[4:]

    # Port: keep non-default ports
    port = parsed.port
    netloc = hostname
    if port and port not in (80, 443):
        netloc = f"{hostname}:{port}"

    # Path normalization
    path = parsed.path.replace("//", "/")
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")

    # Query normalization: remove tracking params and sort
    order_query = sorted(parse_qsl(parsed.query, keep_blank_values=True))
    params = [(k, v) for k, v in order_query if k.lower() not in TRACKING_PARAMS]
    clean_query = urlencode(params, doseq=True)

    # Rebuild URL
    new_parsed = parsed._replace(
        scheme=scheme,
        netloc=netloc,
        path=path,
        query=clean_query,
        fragment=""  # Remove fragment
    )
    return urlunparse(new_parsed)


DISALLOWED_TAGS = frozenset({"style", "script", "head", "title", "meta", "[document]"})


def _tag_visible(el, _disallowed=DISALLOWED_TAGS):
    """Use tag name to identify if text is visible to user"""
    # Retrieve current HTML tag from the current text node
    parent = getattr(el, "parent", None)
    if not parent:  # Safeguard against malformed URLs
        return False
    if parent.name in _disallowed:  # Omit tags not visible to user
        return False
    if isinstance(el, Comment):  # Filter out comments that cannot be seen by the user
        return False
    s = str(el).strip()
    return bool(s)


# Regex patterm that matches sequences of one or more alphabetic character(s), ensuring there is a word boundary
_word_re = re.compile(r"\b[a-zA-Z0-9]+\b")


def _extract_words(soup):
    """Extract words visible words to user on given URL page"""
    texts = soup.find_all(string=True)
    vis = [t.strip() for t in texts if _tag_visible(t)]
    text = " ".join(vis)
    return _word_re.findall(text.lower())


FILETYPE_PATTERN = re.compile(
    r"\.(css|js|bmp|gif|jpe?g|ico|png|tiff?|mid|mp2|mp3|mp4|"
    r"wav|avi|mov|mpeg|ram|m4v|mkv|ogg|ogv|pdf|ps|eps|tex|ppt|pptx|"
    r"doc|docx|xls|xlsx|names|data|dat|exe|bz2|tar|msi|bin|7z|psd|"
    r"dmg|iso|epub|dll|cnf|tgz|sha1|thmx|mso|arff|rtf|jar|csv|"
    r"rm|smil|wmv|swf|wma|zip|rar|gz)$"
)

VALID_SCHEMES = frozenset({"https", "http"})


def compute_page_hash(content):
    """Compute a SHA256 hash of the page text for exact duplicate detection."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def compute_simhash(words):
    """Compute a simple simhash value for near-duplicate detection."""
    hash_bits = [0] * 64
    for word, freq in Counter(words).items():
        h = int(hashlib.md5(word.encode("utf-8")).hexdigest(), 16)
        for i in range(64):
            bit = (h >> i) & 1
            hash_bits[i] += freq if bit else -freq
    fingerprint = 0
    for i, bit_sum in enumerate(hash_bits):
        if bit_sum > 0:
            fingerprint |= 1 << i
    return fingerprint


def hamming_distance(x, y):
    """Compute the Hamming distance between two simhash values."""
    return bin(x ^ y).count("1")


def is_valid(url):
    try:
        if not url or len(url) > 2000:
            return False

        parsed = urlparse(url)
        scheme = parsed.scheme.lower()
        netloc = parsed.netloc.lower()
        path = parsed.path or ""
        query = parsed.query or ""

        if scheme not in VALID_SCHEMES:
            return False
        if not re.search(r"(ics\.uci\.edu|cs\.uci\.edu|informatics\.uci\.edu|stat\.uci\.edu)$", netloc):
            return False
        if FILETYPE_PATTERN.search(path.lower()):
            return False
        if len(query) > 120 or path.count("/") > 15:
            return False
        if re.search(r"/\d{4}/\d{2}/\d{2}", path):
            return False
        if re.search(r"(page|p)=\d{3,}", query):
            return False
        if query:
            if query.count("&") + 1 > 8:
                return False
        segments = [seg for seg in path.strip("/").split("/") if seg]
        if len(segments) > 3 and len(set(segments)) < len(segments) / 2:
            return False
        if re.search(r"(sessionid|jsessionid|phpsessid|sid|token|ref)=\w+", query, re.IGNORECASE):
            return False
        if re.search(r"(session|login|logout)[=/]?", path, re.IGNORECASE):
            return False
        if len(netloc.split(".")) > 6:
            return False
        if any(len(seg) > 100 for seg in segments):
            return False
        
        path_lower = path.lower()
        query_lower = query.lower()

        #isg.ics calendar trap
        if netloc == "isg.ics.uci.edu" and (path_lower.startswith("/events/") or path_lower.startswith("/event/")):
            return False

        #WICS / NGS calendar pages only (keep rest of the site)
        if netloc in {"wics.ics.uci.edu", "ngs.ics.uci.edu"} and path_lower.startswith("/events/"):
            return False

        #doku.php wiki trees
        if "doku.php" in path_lower:
            return False

        # gitlab commit/page explosion
        if netloc == "gitlab.ics.uci.edu":
            return False

        # large image galleries with very low text value
        if "/~eppstein/pix" in path_lower:
            return False

        # grape reported as an infinite trap
        if netloc == "grape.ics.uci.edu":
            return False

        # fano rules tree
        if netloc == "fano.ics.uci.edu" and path_lower.startswith("/ca/rules/"):
            return False

        # generic calendar engines mentioned (ical / tribe / wp-json)
        if "ical" in path_lower or "ical" in query_lower:
            return False
        if "tribe_event" in query_lower or "/tribe/" in path_lower:
            return False
        if "wp-json" in path_lower:
            return False
        
        return True
    except (TypeError, ValueError):
        return False
    

def write_metrics():
    """Log metrics in file metrics.txt
        1. Number of unique pages
        2. Longest page in terms of words
        3. Top 50 Most Common Words"""
    with open("metrics.txt", "w", encoding="utf-8") as f:
        try:
            f.write("=== 1) Unique Pages ===\n")
            f.write(f"Total unique pages: {len(report_urls)}\n\n")
            f.write("=== 2) Longest Page ===\n")
            f.write(f"Longest page in terms of words: {longest_page[0]}, {longest_page[1]} words\n\n")
            f.write("=== 3) 50 Most Common Words ===\n")
            for word, count in word_counter.most_common(50):
                f.write(f"{word}, {count}\n")
        except NameError as e:
            print(f"Error occurred with retrieving metrics - {e}")
        except Exception as e:
            print(f"Exception occurred: {e}")


def write_subdomain_counts():
    """Log subdomains and number of unique pages per subdomain in file subdomain_counts.txt ordered alphabetically"""
    try:
        sorted_subdomains = sorted(subdomain_counts.items())
        with open("subdomain_counts.txt", "w", encoding="utf-8") as f:
            f.write("=== Subdomain Summary ===\n")
            for subdomain, count in sorted_subdomains:
                f.write(f"{subdomain}, {count}\n")
    except NameError as e:
            print(f"Error occurred with retrieving subdomain metrics - {e}")
    except Exception as e:
            print(f"Exception occurred: {e}")


def report_key(u: str) -> str:
    p = urlparse(u)
    # Same URL, fragment removed only
    return urlunparse((p.scheme, p.netloc, p.path, p.params, p.query, ""))
