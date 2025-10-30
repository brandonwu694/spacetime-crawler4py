import re
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup 
from collections import Counter, defaultdict
from bs4.element import Comment

seen_urls = set()
longest_page = ("", 0)
word_counter = Counter()
subdomain_counts = defaultdict(int)

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

def scraper(url, resp):
    links = extract_next_links(url, resp)
    return [link for link in links if is_valid(link)]

def extract_next_links(url, resp):
    # Implementation required.
    # url: the URL that was used to get the page
    # resp.url: the actual url of the page
    # resp.status: the status code returned by the server. 200 is OK, you got the page. Other numbers mean that there was some kind of problem.
    # resp.error: when status is not 200, you can check the error here, if needed.
    # resp.raw_response: this is where the page actually is. More specifically, the raw_response has two parts:
    #         resp.raw_response.url: the url, again
    #         resp.raw_response.content: the content of the page!
    # Return a list with the hyperlinks (as strings) scrapped from resp.raw_response.content
    extracted_links = set()
    if resp.status != 200 or resp.raw_response is None or resp.raw_response.content is None:
        return []
    
    soup = BeautifulSoup(resp.raw_response.content, "lxml") # Consider swtiching to a more efficient HTML parser

    # Track unique page and longest page by word count 
    canonical = normalize_url(resp.url or url)

    # See the first time we see a page
    first_time = canonical not in seen_urls

    seen_urls.add(canonical)
    words = _extract_words(soup)

    # Update word counter while not in the stopwords
    word_counter.update(w for w in words if w not in STOPWORDS)

    count = len(words)
    global longest_page
    if count > longest_page[1]:
        longest_page = (canonical, count)

    if first_time:
        host = urlparse(canonical).netloc.lower()
        if host.endswith(".uci.edu"):
            subdomain_counts[host] += 1

    # Find all <a> tags with a hypertext reference (href) attribute
    for link in soup.find_all("a", href=True): 
        href = link.get("href")
        href = href.strip() # Remove any whitespaces the URL may have
        absolute_url = urljoin(url, href) # Convert relative URLs to absolute URLs
        extracted_links.add(normalize_url(absolute_url)) # Defragment link and add to set of extracted links

    return list(extracted_links)

def normalize_url(url: str):
    """"Remove fragment and port number from URL"""
    parsed = urlparse(url)
    return parsed._replace(netloc=parsed.netloc.split(":", 1)[0].rstrip("."), fragment="").geturl()

DISALLOWED_TAGS = frozenset({"style", "script", "head", "title", "meta", "[document]"})

def _tag_visible(el, _disallowed=DISALLOWED_TAGS):
    """Use tag name to identify if text is visible to user"""
    # Retrieve current HTML tag from the current text node
    parent = getattr(el, "parent", None)
    if not parent: # Safeguard against malformed URLs 
        return False
    if parent.name in _disallowed: # Omit tags not visible to user
        return False
    if isinstance(el, Comment): # Filter out comments that cannot be seen by the user
        return False
    s = str(el).strip()
    return bool(s)

# Regex patterm that matches sequences of one or more alphabetic character(s), ensuring there is a word boundary
_word_re = re.compile(r"\b[a-zA-Z]+\b")

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

def is_valid(url: str, _pattern=FILETYPE_PATTERN, _valid_schemes=VALID_SCHEMES) -> bool:
    """Ensures that crawled URLs are HTTP or HTTPs protocol and within the specified domain"""
    try:
        parsed = urlparse(url)
        if parsed.scheme.lower() not in _valid_schemes:
            return False
        path = parsed.path
        if path and _pattern.search(path.lower()):
            return False
        if not re.search(r"(ics\.uci\.edu|cs\.uci\.edu|informatics\.uci\.edu|stat\.uci\.edu)$", parsed.netloc.lower()):
            return False
        return True
    except TypeError:
        print ("TypeError for ", parsed)
        raise
