from collections import defaultdict
import argparse

class Tokenizer:
    """
    Tokenizes text input and indexes words and phrases by page number.
    """
    WORD_SPECIAL = ['\\', '/', '-', '_', '&', '.'] # special chars that can be part of a word
    PAGE_DIVIDER = '\f' # signifies end of page
    PHRASE_CONNECTORS = ["of","the","and","&","or","in","on","for","to","by","with","as","at","from","a","an","vs"] # used to connect words in phrases (not start/end)
    PHRASE_SEPARATORS = [",", ";", ":", "–", "•", ".", "!", "?"]

    def __init__(self, page_offset):
        """
        Tokenizer Constructor.

        Args:
            page_offset (int): Starting page offset.
        """
        # current
        self.word = ""
        self.word_spec = ""
        self.quote = ""
        self.quoting = False
        self.parens = ""
        self.paren_depth = 0
        self.phrase = ""
        self.phrase_conn = ""
        self.page = 1 - page_offset

        # storage
        self.words = defaultdict(set) # word: pages
        self.phrases = defaultdict(set) # phrase: pages

    def _has_capital(self, word:str)->bool:
        """
        Check whether a word contains at least one uppercase letter.

        Args:
            word (str): Word to check.

        Returns:
            bool: True if the word contains an uppercase letter.
        """
        for w in word:
            if w.isupper():
                return True
        return False

    def _process_word_char(self, b: str) -> bool:
        """
        Process characters that may belong to a word.

        Returns:
            bool: True if the character was consumed.
        """

        # add to word buffer
        if b.isalnum():
            if self.word_spec:
                self.word += self.word_spec
                self.word_spec = ""

            self.word += b
            return True

        # special char, add to spec buffer
        elif b in self.WORD_SPECIAL and self.word and not self.word_spec:
            self.word_spec += b
            return True

        return False

    def _flush_word(self):
        """
        Flush the current word buffer into indexes and phrase buffers.
        """
        if not self.word:
            return

        if self.page > 0:
            w = self.word.lower()

            # add to words
            self.words[w].add(self.page)

            self._process_quote_word(w)
            self._process_paren_word(w)
            self._process_phrase_word(w)

        self.word = ""
        self.word_spec = ""

    def _process_quote_word(self, w: str):
        """
        Add a word to the active quote buffer.
        """
        if self.quoting:
            self.quote += f" {w}" if self.quote else w

    def _process_paren_word(self, w: str):
        """
        Add a word to the active parenthetical buffer.
        """
        if self.paren_depth > 0:
            if w not in self.PHRASE_CONNECTORS:
                self.parens += f" {w}" if self.parens else w

    def _process_phrase_word(self, w: str):
        """
        Process phrase construction logic for a word.
        """
        if self._has_capital(self.word):
            if self.phrase and self.phrase_conn:
                self.phrase += f" {self.phrase_conn}"
                self.phrase_conn = ""

            if w not in self.PHRASE_CONNECTORS:
                self.phrase += f" {w}" if self.phrase else w

        elif self.phrase and w in self.PHRASE_CONNECTORS:
            self.phrase_conn += f" {w}" if self.phrase_conn else w

        else:
            self._flush_phrase()

    def _flush_phrase(self):
        """
        Flush the current phrase buffer.
        """
        if self.phrase:
            self.phrases[self.phrase].add(self.page)

        self.phrase = ""
        self.phrase_conn = ""

    def _process_quotes(self, b: str):
        """
        Process quote state transitions.
        """
        if b != "\"":
            return

        # end quote
        if self.quoting:
            self.quoting = False

            if self.quote:
                if self.page > 0:
                    self.phrases[self.quote.lower()].add(self.page)

                self.quote = ""

        # start quote
        else:
            self.quoting = True

    def _process_parens(self, b: str):
        """
        Process parenthetical state transitions.
        """
        if b == "(":
            self.paren_depth += 1

        elif b == ")":
            self.paren_depth -= 1

            # flush paren buffer (end)
            if self.parens and self.paren_depth == 0:
                if self.page > 0:
                    self.phrases[self.parens.lower()].add(self.page)

                self.parens = ""

        elif b == "," and self.paren_depth > 0:
            # flush paren buffer (comma)
            if self.parens:
                if self.page > 0:
                    self.phrases[self.parens.lower()].add(self.page)

                self.parens = ""

    def _process_phrase_separator(self, b: str):
        """
        Flush phrase buffer on separator characters.
        """
        if self.phrase and b in self.PHRASE_SEPARATORS:
            if self.page > 0:
                self.phrases[self.phrase].add(self.page)

            self.phrase = ""
            self.phrase_conn = ""

    def _process_page(self, b: str):
        """
        Process page divider characters.
        """
        if b == self.PAGE_DIVIDER:
            self.page += 1

    def process(self, b: int):
        """
        Process a single character of input.

        Args:
            b (int): Byte to process.
        """
        b = chr(b)

        if self._process_word_char(b):
            return

        self._flush_word()

        self._process_quotes(b)
        self._process_parens(b)
        self._process_phrase_separator(b)
        self._process_page(b)



def read_file(filename)->bytes:
    """
    Read a file into memory.

    Args:
        filename (str): Path to the file.

    Returns:
        bytes: File contents.
    """
    data = []
    try:
        with open(filename, "rb") as f:
            data = f.read()

    except Exception as e:
        print(f"    [!] Error reading file.")
    
    return data


########################
# MAIN
########################
def main():
    # parse args
    parser = argparse.ArgumentParser(description="Build index from TXT file.")
    parser.add_argument("input", help="Input TXT file")
    parser.add_argument("output", help="Output TXT file")
    parser.add_argument("-o", "--offset", type=int, default=0, help="Page number offset (default: 0)")
    parser.add_argument("-f", "--max-frequency", type=int, default=None, help="Skip terms appearing on more than N pages")
    parser.add_argument("-l", "--max-length", type=int, default=None, help="Skip terms greater than N characters")
    args = parser.parse_args()

    input_file = args.input
    output_file = args.output
    offset = args.offset
    max_frequency = args.max_frequency
    max_len = args.max_length

    # read file
    print(f"[+] Reading        : {input_file}")
    data = read_file(filename=input_file)
    print(f"    Size (Bytes)   : {len(data)}\n")

    # tokenize
    print(f"    [+] Tokenizing")
    tokenizer = Tokenizer(page_offset=offset)
    for b in data:
        tokenizer.process(b)
    print(f"        Words      : {len(tokenizer.words)}")
    print(f"        Phrases    : {len(tokenizer.phrases)}")


    # TESTING
    # for w in sorted(tokenizer.words.items()):
    #     print(w)
    for p in sorted(tokenizer.phrases.items()):
        print(p)
        
if __name__ == "__main__":
    main()