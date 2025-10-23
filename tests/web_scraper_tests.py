import unittest
import sys
import os
from bs4 import BeautifulSoup

# NOTE The tests directory needs to be removed before submission

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scraper
import tokenizer

# NOTE: URLs used are solely for test purposes, I'm not sure if it's a good idea to visit them
class TestDefragmentURL(unittest.TestCase):
    def test_defragment_url(self):
        # Test most common use case of defragment_url
        raw_url = "https://en.wikipedia.org/wiki/Python_(programming_language)#History"
        defragmented_url = "https://en.wikipedia.org/wiki/Python_(programming_language)"
        self.assertEqual(scraper.defragment_url(raw_url), defragmented_url)

        # Trailing '/' after domain name
        raw_url = "https://example.com/#frag"
        defragmented_url = "https://example.com/"
        self.assertEqual(scraper.defragment_url(raw_url), defragmented_url)

        # URL containing unicode characters
        raw_url = "https://exämple.org/über#Käse"
        defragmented_url = "https://exämple.org/über"
        self.assertEqual(scraper.defragment_url(raw_url), defragmented_url)

    def test_different_schemes(self):
        raw_url = "file:///Users/u/readme.txt#L10"
        defragmented_url = "file:///Users/u/readme.txt"
        self.assertEqual(scraper.defragment_url(raw_url), defragmented_url)

        raw_url = "data:text/plain;base64,SGk=#frag"
        defragmented_url = "data:text/plain;base64,SGk="
        self.assertEqual(scraper.defragment_url(raw_url), defragmented_url)

        raw_url = "mailto:alice@example.com#sig"
        defragmented_url = "mailto:alice@example.com"
        self.assertEqual(scraper.defragment_url(raw_url), defragmented_url)

        raw_url = "ftp://host/file#part"
        defragmented_url = "ftp://host/file"
        self.assertEqual(scraper.defragment_url(raw_url), defragmented_url)

    def test_no_fragment_link(self):
        # Verify that defragment_link() keeps already defragmented links as-is
        raw_url = "https://en.wikipedia.org/wiki/Python_(programming_language)"
        defragmented_url = "https://en.wikipedia.org/wiki/Python_(programming_language)"
        self.assertEqual(scraper.defragment_url(raw_url), defragmented_url)

        raw_url = "data:text/plain;base64,SGk=#frag"
        defragmented_url = "data:text/plain;base64,SGk="

    def test_dangling_fragment(self):
        # Verify that standalone fragment in URL is removed
        raw_url = "https://en.wikipedia.org/wiki/Python_(programming_language)#"
        defragmented_url = "https://en.wikipedia.org/wiki/Python_(programming_language)"
        self.assertEqual(scraper.defragment_url(raw_url), defragmented_url)

    def test_tricky_separators(self):
        # Ensure that defragment_link does not misidentify symbols such as '%' as a fragment
        raw_url = "https://example.com/?q=C%23"
        defragmented_url = "https://example.com/?q=C%23"
        self.assertEqual(scraper.defragment_url(raw_url), defragmented_url)

    def test_preserve_query(self):
        # Verify that defragment_link removes the fragment, but preserves the query portion of the URL
        raw_url = "https://example.com/search?q=python#top"
        defragmented_url = "https://example.com/search?q=python"
        self.assertEqual(scraper.defragment_url(raw_url), defragmented_url)

class TestTokenizer(unittest.TestCase):
    def test_tokenizer(self):
        html = """
        <html>
        <head><title>Example Page</title></head>
        <body>
            <h1>Welcome to My Site</h1>
            <p>This site has links and text content.</p>
            <a href="/a">About</a>
            <a href="https://example.com/b?x=1#frag">Contact</a>
        </body>
        </html>
        """

        soup = BeautifulSoup(html, "html.parser")
        token_lst = tokenizer.tokenize(soup)
        for token in token_lst:
            if token.isalpha():
                self.assertTrue(token.islower())
            self.assertTrue(token.isalnum())

        freqs = tokenizer.compute_word_frequencies(token_lst)
        tokenizer.print_frequencies(freqs)

    def test_omit_stopwords(self):
        html = """
        <html>
        <head><title>Me, Myself, and I</title></head>
        <body>
            <h1>Just don't and won't</h1>
            <p>Shouldn't, shan't, wouldn't, and couldn't.</p>
            <a href="/a">Once</a>
            <a href="https://example.com/b?x=1#frag">HiMsElF</a>
        </body>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")
        token_lst = tokenizer.tokenize(soup)
        freqs = tokenizer.compute_word_frequencies(token_lst)
        self.assertEqual(freqs, {})

if __name__ == "__main__":
    unittest.main()
