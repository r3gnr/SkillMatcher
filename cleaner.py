from bs4 import BeautifulSoup
import html
class TextCleaner:
    def clean_html(self, text: str) -> str:
        if not text:
            return ""
        text = html.unescape(text)
        soup = BeautifulSoup(text, "html.parser")
        return soup.get_text(separator=" ")
