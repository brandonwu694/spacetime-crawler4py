import string
import unicodedata
from bs4 import BeautifulSoup 

ALLOWED = frozenset(string.ascii_letters + string.digits + "-")

# Copy list of stopwords from nltk library. Downloading the set of stopwords from internet at runtime may cause issues with the autograder
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

def _process_delimiters(word: str) -> str:
    """Replace non-alphanumeric in the given word with '-' and convert word to lowercase"""
    if not isinstance(word, str):
        return ""
    
    allowed = ALLOWED # Initialize local reference to reduce overhead of global lookup
    chars = [ch if ch in allowed else "-" for ch in word]
    return "".join(chars).casefold() # Utilize casefold() method to handle multilingual text

def _process_word(word: str) -> str:
    """Normalize accents and replace non-alphanumeric characters to '-'"""
    if not isinstance(word, str):
        return ""
    
    normalize_accents = unicodedata.normalize("NFKD", word) # Break all characters into base + accent
    remove_accents = "".join(ch for ch in normalize_accents if not unicodedata.combining(ch)) # Filter out accent marks
    return _process_delimiters(remove_accents)

def tokenize(html_parser: BeautifulSoup, stopwords=STOPWORDS) -> list[str]:
    """Reads in text file and returns list of tokens within that file"""
    all_text = html_parser.get_text(separator=" ", strip=True).lower()
    all_text = all_text.split()
    tokens = []
    for word in all_text:
        word = _process_word(word)
        word_lst = word.split("-")
        tokens.extend(word for word in word_lst if word and word not in stopwords)
    return tokens

def compute_word_frequencies(token_lst: list[str]) -> dict[str, int]:
    """Counts the number of occurrences of each token in the token list"""
    freqs = {}
    for token in token_lst:
        freqs[token] = freqs.get(token, 0) + 1
    return freqs

def print_frequencies(freqs: dict[str, int]) -> None:
    """Prints out the word frequency count onto the screen, ordered by decreasing frequency"""
    sorted_freqs = sorted(freqs.items(), key=lambda x: (-x[1], x[0]))
    for pair in sorted_freqs:
        print(f"{pair[0]} - {pair[1]}")
