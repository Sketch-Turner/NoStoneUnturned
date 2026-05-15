from collections import defaultdict
import argparse
import re

class WordFilter:
    """
    Configurable word validation system.

    Words are validated against a sequence of filter rules.
    Each rule maps to a corresponding internal filter method.
    """
    def __init__(self, pre_filters=[], post_filters=[], indent=8):
        """
        Initialize filter configuration.

        Args:
            pre_filters (list[tuple[str, any]]]):
                Filters words before being added to index.
                Sequence of filter rules in the form:
                (filter_name, filter_parameter).
            post_filters (list[tuple[str, any]]]):
                Filters words after being added to index.
                Sequence of filter rules in the form:
                (filter_name, filter_parameter).
            indent (int):
                Number of spaces to indent when printing.
        """
        self.pre_filters = pre_filters
        self.post_filters = post_filters
        self.indent = indent

    def build_from_argparse_args(self, args):
        """
        Build filter configuration from parsed argparse arguments.

        Args:
            args: Parsed argparse namespace containing filter options.
        """
        self.pre_filters = []
        self.post_filters = []
        # pre
        if args.min_length:
            self.pre_filters.append(("min_length", args.min_length))
        if args.max_length:
            self.pre_filters.append(("max_length", args.max_length))
        if args.no_filter_urls:
            self.pre_filters.append(("filter_URLs", None))
        if args.no_filter_uncs:
            self.pre_filters.append(("filter_UNCs", None))
        if args.no_filter_hex:
            self.pre_filters.append(("filter_hex", None))
        # post
        if args.min_frequency:
            self.post_filters.append(("min_frequency", args.min_frequency))
        if args.max_frequency:
            self.post_filters.append(("max_frequency", args.max_frequency))

    def __str__(self):
        """
        Return a formatted string representation of configured filters.

        Returns:
            str: Sorted list of filter names and parameters.
        """
        result = f"{' '*self.indent}Pre-filters:\n" if len(self.pre_filters) > 0 else ""
        for filter_name, filter_param in sorted(self.pre_filters):
            result += f"{' '*self.indent}    {filter_name}: {filter_param if filter_param is not None else True}\n"

        result += f"{' '*self.indent}Post-filters:\n" if len(self.pre_filters) > 0 else ""
        for filter_name, filter_param in sorted(self.post_filters):
            result += f"{' '*self.indent}    {filter_name}: {filter_param if filter_param is not None else True}\n"

        return result.strip('\n')

    def prefilter(self, word: str) -> bool:
        """
        Check whether a word passes all configured pre-filters.

        Args:
            word (str): Word to validate.

        Returns:
            bool: True if the word passes all pre-filters.

        Raises:
            ValueError:
                If a configured filter name does not match any available filter method.
        """
        for filter_name, filter_param in self.pre_filters:
            func = getattr(self, f"_{filter_name.lower()}", None)

            if func is None:
                raise ValueError(f"Unknown filter: {filter_name}")

            if filter_param is None:
                if not func(word):
                    return False
            else:
                if not func(word, filter_param):
                    return False

        return True

    def postfilter(self, index: defaultdict[set]) -> defaultdict[set]:
        """
        Apply all configured post-processing filters to the index.

        Each post-filter is looked up by name and executed in sequence.
        Filters are expected to accept an index and return a modified index.

        Args:
            index (defaultdict[set]):
                The index structure mapping keys to sets of values.

        Returns:
            defaultdict[set]:
                The filtered/processed index after all post-filters have been applied.

        Raises:
            ValueError:
                If a configured filter name does not match any available filter method.
        """
        for filter_name, filter_param in self.post_filters:
            func = getattr(self, f"_{filter_name.lower()}", None)

            if func is None:
                raise ValueError(f"Unknown filter: {filter_name}")

            if filter_param is None:
                index = func(index)
            else:
                index = func(index, filter_param)
            
        return index

    # pre-filters
    def _min_length(self, word: str, length: int) -> bool:
        """
        Check whether a word meets the minimum length requirement.

        Args:
            word (str): Word to check.
            length (int): Minimum allowed length.

        Returns:
            bool: True if the word length is valid.
        """
        return len(word) >= length

    def _max_length(self, word: str, length: int) -> bool:
        """
        Check whether a word exceeds the maximum length limit.

        Args:
            word (str): Word to check.
            length (int): Maximum allowed length.

        Returns:
            bool: True if the word length is valid.
        """
        return len(word) <= length

    def _filter_urls(self, word: str) -> bool:
        """
        Determine whether a token should be rejected as a URL-like string.

        This filter returns True for words that are NOT valid URLs, and False
        for strings that match a URL pattern (e.g. http://, https://, www.).

        Args:
            word (str): Token to evaluate.

        Returns:
            bool: True if the token is NOT a URL, False if it matches a URL pattern.
        """
        return (re.fullmatch(r'(?:https?://|www\.)[a-zA-Z0-9.\-/_=?%]+', word) is None)

    def _filter_uncs(self, word: str) -> bool:
        """
        Reject UNC paths.

        Args:
            word (str): Token to check.

        Returns:
            bool: True if not a UNC path.
        """
        return not word.startswith("\\\\")

    def _filter_hex(self, word: str) -> bool:
        """
        Reject hexadecimal-like strings.

        Filters tokens that:
        - start with '0x' followed by hexadecimal characters
        - consist primarily of hexadecimal characters and are at least 4 characters long

        Args:
            word (str): Token to check.

        Returns:
            bool: True if the token is not hexadecimal-like.
        """
        return not (re.match(r'^0x[0-9a-fA-F]+', word) or (re.match(r'^[0-9a-fA-F]{4,}', word) and not word.isalpha()))

    # post-filters
    def _min_frequency(self, index: defaultdict[set], frequency:int) -> defaultdict[set]:
        """
        Removes words found on less than N pages.

        Args:
            index (defaultdict[set]):
                Mapping of words to set of pages.
            frequency (int):
                Minimum number of occurrences required to keep a word.

        Returns:
            defaultdict[set]:
                A filtered index containing only entries whose set size
                is greater than or equal to the given frequency.
        """
        result = defaultdict(set)
        for word, pages in index.items():
            if len(pages) >= frequency:
                result[word] = pages
        return result
    
    def _max_frequency(self, index: defaultdict[set], frequency:int) -> defaultdict[set]:
        """
        Removes words found on more than N pages.

        Args:
            index (defaultdict[set]):
                Mapping of words to set of pages.
            frequency (int):
                Maximum number of occurrences required to keep a word.

        Returns:
            defaultdict[set]:
                A filtered index containing only entries whose set size
                is greater than or equal to the given frequency.
        """
        result = defaultdict(set)
        for word, pages in index.items():
            if len(pages) <= frequency:
                result[word] = pages
        return result


class Tokenizer:
    """
    Tokenizes text input and indexes words and phrases by page number.
    """
    WORD_SPECIAL = ['\\', '/', '-', '_', '&', '.', '@', '%', ':', '?', "="] # special chars that can be part of a word
    PAGE_DIVIDER = '\f' # signifies end of page
    PHRASE_CONNECTORS = ["of","the","and","&","or","in","on","for","to","by","with","as","at","from","a","an","vs"] # used to connect words in phrases (not start/end)
    PHRASE_SEPARATORS = [",", ";", ":", "–", "•", ".", "!", "?"] # special chars that end a phrase

    def __init__(self, page_offset:int=0, filter:WordFilter=None, mode=0):
        """
        Tokenizer Constructor.

        Args:
            page_offset (int): Starting page offset.
            filter (WordFilter): Rules defining valid words.
            mode (int): Parsing mode based on file type.
                0: TXT
                1: PDF
        """
        # filter
        self.filter = filter

        # mode
        self.mode = mode

        # buffers
        self.word = ""
        self.word_spec = ""
        self.quote = ""
        self.quoting = False
        self.parens = ""
        self.paren_depth = 0
        self.phrase = ""
        self.phrase_conn = ""
        self.page = 1 - page_offset

        # words/phrases
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

    def _add_phrase(self, phrase:str, page:int):
        """
        Add a phrase occurrence to the phrase index.

        If a filter is configured, the phrase is first checked using the pre-filter
        before being added to the index.

        Args:
            phrase (str): The phrase to index.
            page (int): The page number where the phrase occurs.
        """
        if self.filter:
            if self.filter.prefilter(phrase):
                self.phrases[phrase].add(page)
        else:
            self.phrases[phrase].add(page)

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
        
        # special char exception for URLs
        elif b == "/" and self.word and self.word_spec == ":" or self.word_spec == ":/":
            self.word_spec += b
            return True
        
        # special char execptions for UNC paths
        elif b == "\\" and not self.word and (not self.word_spec or self.word_spec == "\\"):
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
            if self.filter:
                if self.filter.prefilter(self.word):
                    self.words[w].add(self.page)
            else:
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
            self._add_phrase(self.phrase, self.page)

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
                    self._add_phrase(self.quote.lower(), self.page)

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
                    self._add_phrase(self.parens.lower(), self.page)

                self.parens = ""

        elif b == "," and self.paren_depth > 0:
            # flush paren buffer (comma)
            if self.parens:
                if self.page > 0:
                    self._add_phrase(self.parens.lower(), self.page)

                self.parens = ""

    def _process_phrase_separator(self, b: str):
        """
        Flush phrase buffer on separator characters.
        """
        if self.phrase and b in self.PHRASE_SEPARATORS:
            if self.page > 0:
                self._add_phrase(self.phrase, self.page)

            self.phrase = ""
            self.phrase_conn = ""

    def _process_page(self, b: str):
        """
        Process page divider characters.
        """
        if b == self.PAGE_DIVIDER:
            self.page += 1

    def _process_byte(self, b: int):
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

    def tokenize(self, data:bytes):
        """
        Tokenize input data according to the configured document mode.

        Args:
            data (bytes): Raw document data to tokenize.
        """
        # TXT
        if self.mode == 0: 
            for b in data:
                self._process_byte(b)
            self._process_byte(0x00) # flush buffer

        # PDF
        elif self.mode == 1:
            #TODO
            pass


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
    parser.add_argument("-v", "--verbose", action="store_true", help="Print verbose output")
    parser.add_argument("-o", "--offset", type=int, default=0, help="Page number offset (default: 0)")
    # filters
    parser.add_argument("-f", "--min-frequency", type=int, default=None, help="Skip terms appearing on less than N pages")
    parser.add_argument("-F", "--max-frequency", type=int, default=None, help="Skip terms appearing on more than N pages")
    parser.add_argument("-l", "--min-length", type=int, default=None, help="Skip terms less than N characters")
    parser.add_argument("-L", "--max-length", type=int, default=None, help="Skip terms greater than N characters")
    parser.add_argument("-u", "--no-filter-urls", action="store_false", help="Don't remove URLs")
    parser.add_argument("-U", "--no-filter-uncs", action="store_false", help="Don't remove UNCs")
    parser.add_argument("-H", "--no-filter-hex", action="store_false", help="Don't remove hexidecimal strings")

    args = parser.parse_args()

    input_file = args.input
    output_file = args.output
    verbose_output = args.verbose
    offset = args.offset

    # read file
    print(f"[+] Reading        : {input_file}")
    filetype = 1 if input_file.upper().endswith("PDF") else 0
    data = read_file(filename=input_file)
    print(f"    Mode           : {["TXT", "PDF"][filetype]}")
    print(f"    Size (Bytes)   : {len(data)}\n")

    # prepare filter
    print(f"    [+] Preparing Filters")
    word_filter = WordFilter()
    word_filter.build_from_argparse_args(args)
    print(f"{word_filter}\n")

    # tokenize
    print(f"    [+] Tokenizing")
    tokenizer = Tokenizer(page_offset=offset, filter=word_filter, mode=filetype)
    tokenizer.tokenize(data)
    print(f"        Words      : {len(tokenizer.words)}")
    print(f"        Phrases    : {len(tokenizer.phrases)}\n")

    # post-filter
    print(f"    [+] Cleaning")
    tokenizer.words = word_filter.postfilter(tokenizer.words)
    tokenizer.phrases = word_filter.postfilter(tokenizer.phrases)
    print(f"        Words      : {len(tokenizer.words)}")
    print(f"        Phrases    : {len(tokenizer.phrases)}\n")


    # TESTING
    for w in sorted(tokenizer.words.items())[-10:]:
        print(w)
    print()
    for p in sorted(tokenizer.phrases.items())[-10:]:
        print(p)
        
if __name__ == "__main__":
    main()