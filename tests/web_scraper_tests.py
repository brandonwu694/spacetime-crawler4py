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
        for token in freqs:
            if token == "site":
                self.assertEqual(freqs[token], 2)
            else:
                self.assertEqual(freqs[token], 1)

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
        # Since all tokens are stop words, the dictionary should be empty
        freqs = tokenizer.compute_word_frequencies(token_lst)
        self.assertEqual(freqs, {})

class TestLinkValidation(unittest.TestCase):
    def test_http_and_https(self):
        # Ensure that only URLs using the http or https protocol are deemed as valid URL links
        valid_schemes = ["http://ics.uci.edu", "https://www.informatics.uci.edu/research"]
        for url in valid_schemes:
            self.assertEqual(scraper.is_valid(url), True)

    def test_invalid_protocols(self):
        invalid_schemes = ["ftp://ics.uci.edu/data", 
                           "sftp://ics.uci.edu/files", 
                           "ftps://cs.uci.edu/public", 
                           "file:///Users/brandon/Documents/index.html",
                           "file://localhost/etc/hosts" "file://C:/Users/brandon/Desktop/test.html"]
        for url in invalid_schemes:
            self.assertEqual(scraper.is_valid(url), False)

    def test_scrape_valid_domain(self):
        valid_ics_domains = ["https://www.ics.uci.edu/", 
                             "http://ics.uci.edu/about/", 
                             "https://faculty.ics.uci.edu/people", 
                             "https://www.ics.uci.edu/~fielding/pubs/dissertation/top.htm", 
                             "https://archive.ics.uci.edu/ml/index.php", 
                             "https://calendar.ics.uci.edu/events"]
        for url in valid_ics_domains:
            self.assertEqual(scraper.is_valid(url), True)

        valid_cs_domains = ["https://www.cs.uci.edu/", 
                            "http://cs.uci.edu/research/", 
                            "https://faculty.cs.uci.edu/projects/", 
                            "https://cs.uci.edu/grad/programs",
                            "https://www.cs.uci.edu/people/faculty"]
        for url in valid_cs_domains:
            self.assertEqual(scraper.is_valid(url), True)

        valid_informatics_domains = ["https://www.informatics.uci.edu/", 
                                     "http://informatics.uci.edu/about/", 
                                     "https://www.informatics.uci.edu/research/",
                                     "https://informatics.uci.edu/graduate-programs/", 
                                     "https://faculty.informatics.uci.edu/labs/"]
        for url in valid_informatics_domains:
            self.assertEqual(scraper.is_valid(url), True)

        valid_stats_domains = ["https://www.stat.uci.edu/", 
                               "http://stat.uci.edu/research", 
                               "https://www.stat.uci.edu/faculty", 
                               "https://faculty.stat.uci.edu/data-lab"]
        for url in valid_stats_domains:
            self.assertEqual(scraper.is_valid(url), True)

    def test_invalid_look_alikes(self):
        # URLs that seem like they may have a valid domain, but should be classified as an invalid URL to crawl
        look_alike_urls = ["https://uci.edu", 
                           "https://engineering.uci.edu", 
                           "https://ics.uci.edu.evil.com", 
                           "https://example.com/ics.uci.edu"]
        for url in look_alike_urls:
            self.assertEqual(scraper.is_valid(url), False)

    def test_invalid_file_attachments(self):
        documents_and_data_files = ["https://www.ics.uci.edu/files/syllabus.pdf", 
                                    "https://cs.uci.edu/data/export.csv", 
                                    "https://informatics.uci.edu/reports/summary.docx",
                                    "https://stat.uci.edu/files/grades.xlsx", 
                                    "https://faculty.cs.uci.edu/docs/final_paper.tex", 
                                    "https://www.stat.uci.edu/resources/template.rtf"]
        for url in documents_and_data_files:
            self.assertEqual(scraper.is_valid(url), False)

        archives_and_compressed_files = ["https://www.ics.uci.edu/downloads/project.tar",
                                         "https://informatics.uci.edu/data/archive.zip",
                                         "https://cs.uci.edu/backup/site.rar",
                                         "https://stat.uci.edu/datasets/sample.gz",
                                         "https://www.ics.uci.edu/files/compressed/backup.7z",
                                         "https://faculty.informatics.uci.edu/build/package.tgz"]
        for url in archives_and_compressed_files:
            self.assertEqual(scraper.is_valid(url), False)

        images_and_media = ["https://www.ics.uci.edu/images/logo.png",
                            "https://faculty.cs.uci.edu/images/banner.jpg",
                            "https://informatics.uci.edu/media/background.jpeg",
                            "https://www.stat.uci.edu/media/intro.mp4",
                            "https://cs.uci.edu/audio/lecture.mp3",
                            "https://ics.uci.edu/videos/promo.mov"]
        for url in images_and_media:
            self.assertEqual(scraper.is_valid(url), False)

        misc = ["https://cs.uci.edu/models/neuralnet.arff",
                "https://informatics.uci.edu/datasets/beta.epub",
                "https://ics.uci.edu/logs/output.dat",
                "https://www.stat.uci.edu/olddata/archive.bz2",
                "https://informatics.uci.edu/figures/diagram.ps",
                "https://ics.uci.edu/code/source.jar",
                "https://stat.uci.edu/research/presentation.pptx",
                "https://ics.uci.edu/documents/report.thmx"]
        for url in misc:
            self.assertEqual(scraper.is_valid(url), False)

    def test_edge_cases(self):
        # URLs that contain file attachments in the path name, but are not actual files, should be considered as valid URLs
        edge_cases = ["https://www.ics.uci.edu/docs/pdf-guide.html",
                     "https://cs.uci.edu/research/csv_analysis_page",
                     "https://informatics.uci.edu/data/excel.xlsx-overview",
                     "https://stat.uci.edu/datasets/archive.tar-info",
                     "https://faculty.ics.uci.edu/downloads/zip_helper_tool"]
        for url in edge_cases:
            self.assertEqual(scraper.is_valid(url), True)

if __name__ == "__main__":
    unittest.main()
