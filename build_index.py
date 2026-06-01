from collections import defaultdict
import argparse
import re
from io import BytesIO

from pdfminer.high_level import extract_text as pdfminer_extract_text

import nltk
nltk.download('averaged_perceptron_tagger_eng', quiet=True)
nltk.download('words', quiet=True)
from nltk.corpus import words as nltk_words

from wordfreq import zipf_frequency

class WordFilter:
    """
    Configurable word validation system.

    Words are validated against a sequence of filter rules.
    Each rule maps to a corresponding internal filter method.
    """
    # load names
    NAMES = set()
    with open("wordlists/names.txt", "r", encoding="utf-8") as f:
        NAMES = set(line.strip() for line in f)

    # load pronouns
    PRONOUNS = set()
    with open("wordlists/pronouns.txt", "r", encoding="utf-8") as f:
        PRONOUNS = set(line.strip() for line in f)
    
    # load calendar words
    CALENDAR = set()
    with open("wordlists/calendar.txt", "r", encoding="utf-8") as f:
        CALENDAR = set(line.strip() for line in f)

    # load words
    WORDS = set(word for word in nltk_words.words() if word.islower())

    # contraction filter
    CONTRACTION_SUFFIXES = ("'re", "'ve", "'ll", "'d", "n't", "'m")

    # filter mapping
    PREFILTER_SWITCH = 0
    POSTFILTER_SWITCH = 1
    PREFILTER_ARG = 2
    POSTFILTER_ARG = 3
    FILTERS = {
        "c": {"name": "Contractions", "func": "filter_contractions", "type": PREFILTER_SWITCH, "priority": 9, "info": "Filter out WORD tokens ending in a common contraction suffix"},
        "C": {"name": "Calendar", "func": "filter_calendar", "type": PREFILTER_SWITCH, "priority": 3, "info": "Filter out WORD tokens that match a day or month name"},
        "E": {"name": "Email", "func": "filter_emails", "type": PREFILTER_SWITCH, "priority": 10, "info": "Filter out WORD tokens that match email address format"},
        "H": {"name": "Hex", "func": "filter_hex", "type": PREFILTER_SWITCH, "priority": 6, "info": "Filter out WORD tokens that match hex number format"},
        "l": {"name": "Min Length", "func": "min_length", "type": PREFILTER_ARG, "priority": 0, "info": "Filter out ALL tokens shorter than N characters"},
        "L": {"name": "Max Length", "func": "max_length", "type": PREFILTER_ARG, "priority": 0, "info": "Filter out ALL tokens longer than N characters"},
        "m": {"name": "MITRE", "func": "filter_mitre", "type": PREFILTER_SWITCH, "priority": 11, "info": "Filter out WORD tokens that match MITRE ATT&CK code format"},
        "n": {"name": "Non-alpha", "func": "filter_nonalpha", "type": PREFILTER_SWITCH, "priority": 1, "info": "Filter out ALL tokens that have zero alphabet characters"},
        "N": {"name": "Names", "func": "filter_names", "type": PREFILTER_SWITCH, "priority": 4, "info": "Filter out WORD tokens matching a name in wordlists/names.txt (titlecase)\nFilter out PHRASE tokens that contain two consecutive WORD tokens that match (any case)"},
        "p": {"name": "Possessives", "func": "filter_possessives", "type": PREFILTER_SWITCH, "priority": 8, "info": "Filter out WORD tokens ending in \'s or s\'"},
        "P": {"name": "Pronouns", "func": "filter_pronouns", "type": PREFILTER_SWITCH, "priority": 2, "info": "Filter out WORD tokens that match a pronoun"},
        "t": {"name": "Twitter/X Handles", "func": "filter_handles", "type": PREFILTER_SWITCH, "priority": 5, "info": "Filter out WORD tokens that match a Twitter/X handle format"},
        "u": {"name": "URLs", "func": "filter_urls", "type": PREFILTER_SWITCH, "priority": 7, "info": "Filter out WORD tokens that match URL format"},
        "U": {"name": "UNCs", "func": "filter_uncs", "type": PREFILTER_SWITCH, "priority": 12, "info": "Filter out WORD tokens that match UNC format"},
        "f": {"name": "Min Frequency", "func": "min_frequency", "type": POSTFILTER_ARG, "priority": 0, "info": "Filter out ALL tokens appearing on less than N pages"},
        "F": {"name": "Max Frequency", "func": "max_frequency", "type": POSTFILTER_ARG, "priority": 0, "info": "Filter out ALL tokens appearing on more than N pages"},
        "r": {"name": "Regex", "func": "regex", "type": POSTFILTER_ARG, "priority": 0, "info": "Filter out ALL tokens that fail to match the specified regex"},
        "D": {"name": "Dictionary", "func": "filter_dictionary", "type": POSTFILTER_SWITCH, "priority": 1, "info": "Filter out lowercase WORD tokens that match a dictionary word"},
        "M": {"name": "Modifiers", "func": "filter_modifiers", "type": POSTFILTER_SWITCH, "priority": 2, "info": "Filter out WORD tokens that are not a noun or verb"},
        "z": {"name": "Zipf Score", "func": "zipf", "type": POSTFILTER_ARG, "priority": 0, "info": "Filter out ALL tokens with a Zipf Score > N\nZipf Scores are a Log 10 scale:\n1  Very Rare         ~1 in 100,000,000 words\n3  Uncommon          ~1 in 1,000,000 words\n5  Common            ~1 in 10,000 words\n6  Very Common       ~1 in 1,000 words\n7  Extremely Common  ~1 in 100 words"}
    }

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
        self.stats = defaultdict(int)

    def __str__(self):
        """
        Return a formatted string representation of configured filters.

        Returns:
            str: Sorted list of filter names and parameters.
        """
        result = f"{' '*self.indent}Pre-filters:\n" if len(self.pre_filters) > 0 else ""
        for filter_func, filter_param in sorted(self.pre_filters):
            f = next(v for v in self.FILTERS.values() if v["func"] == filter_func)
            result += f"{' '*self.indent}    {f["name"]}: {filter_param if filter_param is not None else True}\n"

        result += f"{' '*self.indent}Post-filters:\n" if len(self.pre_filters) > 0 else ""
        for filter_func, filter_param in sorted(self.post_filters):
            f = next(v for v in self.FILTERS.values() if v["func"] == filter_func)
            result += f"{' '*self.indent}    {f["name"]}: {filter_param if filter_param is not None else True}\n"
        return result.strip('\n')

    @classmethod
    def get_keys(cls, type:int) -> list:
        """
        Return filter keys matching the given filter type.

        Args:
            type (int): Filter type identifier.

        Returns:
            list: Matching filter keys.
        """
        return [k for k, v in cls.FILTERS.items() if v["type"] == type]

    @classmethod
    def get_filter_info(cls) -> str:
        """
        Build and return formatted help text describing available filters.

        Returns:
            str: Filter documentation.
        """
        max_pre_arg = max([len(v["name"]) for v in cls.FILTERS.values() if v["type"] == cls.PREFILTER_ARG])
        max_pre_switch = max([len(v["name"]) for v in cls.FILTERS.values() if v["type"] == cls.PREFILTER_SWITCH])
        max_post_arg = max([len(v["name"]) for v in cls.FILTERS.values() if v["type"] == cls.POSTFILTER_ARG])
        max_post_switch = max([len(v["name"]) for v in cls.FILTERS.values() if v["type"] == cls.POSTFILTER_SWITCH])
        nli_s = 15 # switch newline indent
        nli_a = 11 # arg nl indent
        return "\n".join([
            "Filtering:",
            "    Pre-filters are applied to tokens as the index is built. ",
            "    Pre-filters that require args are applied first. They are disabled by default unless an arg is provided."
            ] + [f"        {v["name"] + " "*(max_pre_arg - len(v["name"]))} : {v["info"].replace("\n", "\n"+" "*(nli_a + max_pre_arg))}" for k, v in sorted(cls.FILTERS.items(), key=lambda x: x[0].lower()) if v["type"] == cls.PREFILTER_ARG] + [
            "",
            "    Switch pre-filters can be managed with -d and -e. They are enabled by default."
            ] + [f"        {k} - {v["name"] + " "*(max_pre_switch - len(v["name"]))} : {v["info"].replace("\n", "\n"+" "*(nli_s + max_pre_switch))}" for k, v in sorted(cls.FILTERS.items(), key=lambda x: x[0].lower()) if v["type"] == cls.PREFILTER_SWITCH] + [
            f"",
            f"    Post-filters are applied to tokens after the index is built. ",
            f"    Post-filters that require args are applied first. They are disabled by default unless an arg is provided."
            ] + [f"        {v["name"] + " "*(max_post_arg - len(v["name"]))} : {v["info"].replace("\n", "\n"+" "*(nli_a + max_post_arg))}" for k, v in sorted(cls.FILTERS.items(), key=lambda x: x[0].lower()) if v["type"] == cls.POSTFILTER_ARG] + [
            f"",
            f"    Switch Post-filters can be managed with -d and -e. They are enabled by default."
            ] + [f"        {k} - {v["name"] + " "*(max_post_switch - len(v["name"]))} : {v["info"].replace("\n", "\n"+" "*(nli_s + max_post_switch))}" for k, v in sorted(cls.FILTERS.items(), key=lambda x: x[0].lower()) if v["type"] == cls.POSTFILTER_SWITCH]
        )

    def build_from_argparse_args(self, args):
        """
        Build filter configuration from parsed argparse arguments.

        Args:
            args: Parsed argparse namespace containing filter options.
        """
        self.pre_filters = []
        self.post_filters = []

        # get enabled switch filters
        filters = set(k for k, v in self.FILTERS.items() if v["type"] in [self.PREFILTER_SWITCH, self.POSTFILTER_SWITCH])
        if args.disable:
            for f in args.disable:
                if f == "*":
                    filters = set()
                    break
                elif f in self.FILTERS and self.FILTERS[f]["type"] in [self.PREFILTER_SWITCH, self.POSTFILTER_SWITCH]:
                    filters.remove(f)
                else:
                    raise ValueError(f"Unknown filter: {f}")
        if args.enable:
            filters = set()
            for f in args.enable:
                if f == "*":
                    filters = set(k for k, v in self.FILTERS.items() if v["type"] in [self.PREFILTER_SWITCH, self.POSTFILTER_SWITCH])
                    break
                elif f in self.FILTERS and self.FILTERS[f]["type"] in [self.PREFILTER_SWITCH, self.POSTFILTER_SWITCH]:
                    filters.add(f)
                else:
                    raise ValueError(f"Unknown filter: {f}")

        # pre args
        for f in [v for v in self.FILTERS.values() if v["type"]  == self.PREFILTER_ARG]:
            f_ptr = getattr(args, f["func"], None)
            if f_ptr:
                self.pre_filters.insert(f["priority"], (f["func"], f_ptr))

        # post args
        for f in [v for v in self.FILTERS.values() if v["type"]  == self.POSTFILTER_ARG]:
            f_ptr = getattr(args, f["func"], None)
            if f_ptr:
                self.post_filters.insert(f["priority"], (f["func"], f_ptr))

        # switches
        for k in filters:
            f = self.FILTERS[k]
            if f["type"] == self.PREFILTER_SWITCH:
                self.pre_filters.insert(f["priority"], (f["func"], None))
            else:
                self.post_filters.insert(f["priority"], (f["func"], None))

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
                raise ValueError(f"Unknown filter: <{filter_name}>")

            if filter_param is None:
                if not func(word):
                    self.stats[filter_name] += 1
                    return False
            else:
                if not func(word, filter_param):
                    self.stats[filter_name] += 1
                    return False

        return True

    def postfilter(self, index: defaultdict[set]) -> defaultdict[set]:
        """
        Apply all configured post-processing filters to the index.

        Each post-filter is looked up by name and executed in sequence.

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
        result = defaultdict(set)
        for word, pages in index.items():
            valid = True
            for filter_name, filter_param in self.post_filters:
                func = getattr(self, f"_{filter_name.lower()}", None)

                if func is None:
                    raise ValueError(f"Unknown filter: {filter_name}")

                if filter_param is None:
                    if not func((word, pages)):
                        self.stats[filter_name] += 1
                        valid = False
                        break
                else:
                    if not func((word, pages), filter_param):
                        self.stats[filter_name] += 1
                        valid = False
                        break
            if valid:
                result[word] = pages
            
        return result

    def remove(self, filter_name: str) -> bool:
        """
        Remove a filter from either the pre-filter or post-filter list.

        The search is case-insensitive and will remove the first matching
        filter found in either collection.

        Args:
            filter_name (str): Name of the filter to remove.

        Returns:
            bool: True if a filter was found and removed, False otherwise.
        """
        found = None
        for name, args in self.pre_filters:
            if name.lower() == filter_name.lower():
                found = (name, args)
                break
        if found:
            self.pre_filters.remove(found)
            return True

        for name, args in self.post_filters:
            if name.lower() == filter_name.lower():
                found = (name, args)
                break
        if found:
            self.post_filters.remove(found)
            return True
        
        return False

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

    def _filter_mitre(self, word: str) -> bool:
        """
        Reject MITRE ATT&CK technique identifiers.

        Args:
            word (str): Token to check.

        Returns:
            bool: True if the token is not a MITRE identifier.
        """
        return not re.match(r'^(t|ta|T|TA)[0-9]{4}', word)

    def _filter_handles(self, word: str) -> bool:
        """
        Reject Twitter/X-style usernames and mentions.

        Filters tokens beginning with '@' followed by one or more
        word characters.

        Args:
            word (str): Token to check.

        Returns:
            bool: True if the token is not a Twitter/X-style mention.
        """
        return not word.startswith('@')

    def _filter_emails(self, word: str) -> bool:
        """
        Reject email addresses.

        Args:
            word (str): Token to check.

        Returns:
            bool: True if the token is not an email address.
        """
        return not re.fullmatch(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}', word)

    def _filter_nonalpha(self, word: str) -> bool:
        """
        Reject tokens that do not contain any alphabetic characters.

        Args:
            word (str): Token to evaluate.

        Returns:
            bool: True if the token contains at least one letter.
        """
        return re.search(r'[a-zA-Z]', word)

    def _filter_names(self, word: str) -> bool:
        """
        Reject title-cased words that match known first or last names.

        Args:
            word (str): Token to evaluate.

        Returns:
            bool: True if the token is not a detected name.
        """
        words = word.split()
        if len(words) > 1:
            pairs = list(zip(words, words[1:]))
            for first, last in pairs:
                if first.title() in self.NAMES and last.title() in self.NAMES:
                    return False
            return True
        else:
            return not (word in self.NAMES and word.lower() not in self.WORDS)

    def _filter_possessives(self, word: str) -> bool:
        """
        Filter out possessive forms of words.

        Returns False if the word ends in a possessive marker ('s or s'),
        otherwise True.
        """
        return not re.search(r"(?:'s|s')$", word, re.IGNORECASE)
    
    def _filter_contractions(self, word: str) -> bool:
        """
        Filter out contraction forms of words.

        Returns False if the word ends with a known contraction suffix, otherwise True.

        Args:
            word (str): Input token to check.

        Returns:
            bool: True if word is not a contraction, False otherwise.
        """
        return not word.lower().endswith(self.CONTRACTION_SUFFIXES)

    def _filter_pronouns(self, word: str) -> bool:
        """
        Filter out pronouns.

        Args:
            word (str): Input token.

        Returns:
            bool: True if not a pronoun, False otherwise.
        """
        return not word.lower() in self.PRONOUNS
    
    def _filter_calendar(self, word: str) -> bool:
        """
        Filter out calendar-related terms such as days of the week and months.

        Args:
            word (str): Input token.

        Returns:
            bool: True if not a calendar term, False otherwise.
        """
        return not word.lower() in self.CALENDAR

    # post-filters
    def _min_frequency(self, item:tuple[str, set], frequency:int) -> bool:
        """
        Filter items by minimum occurrence frequency.

        Args:
            item (tuple[str, set]): A (word, pages) pair.
            frequency (int): Minimum number of pages required.

        Returns:
            bool: True if the item appears in at least N pages.
        """
        pages = item[1]
        return len(pages) >= frequency
    
    def _max_frequency(self, item:tuple[str, set], frequency:int) -> bool:
        """
        Filter items by maximum occurrence frequency.

        Args:
            item (tuple[str, set]): A (word, pages) pair.
            frequency (int): Maximum number of pages allowed.

        Returns:
            bool: True if the item appears in no more than N pages.
        """
        pages = item[1]
        return len(pages) <= frequency

    def _filter_modifiers(self, item: tuple[str, set]) -> bool:
        """
        Keep only noun or verb tokens; allow all multi-word phrases.

        Args:
            item (tuple[str, set]): (word, pages)

        Returns:
            bool: True if word is a noun/verb or a phrase, False otherwise.
        """
        word = item[0]

        # skip phrases
        if " " in word:
            return True

        pos = nltk.pos_tag([word])[0][1]

        return pos.startswith("NN") or pos.startswith("VB")

    def _filter_dictionary(self, item: tuple[str, set]) -> bool:
        """
        Filter out valid dictionary words.

        Args:
            item (tuple[str, set]): (word, pages)

        Returns:
            bool: True if the word should be kept, False if it is a valid
            dictionary word and should be filtered out.
        """
        word = item[0]
        return not word in self.WORDS

    def _regex(self, item: tuple[str, set], regex:str) -> bool:
        """
        Apply a regex filter to a token.

        Args:
            item (tuple[str, set]): (word, pages)
            regex (str): Regular expression used for full-string matching.

        Returns:
            bool: True if the word does NOT match the regex, False otherwise.
        """
        word = item[0]
        return not re.fullmatch(regex, word) is None

    def _zipf(self, item: tuple[str, set], score:float) -> bool:
        """
        Filter words using their zipf score.

        Args:
            item (tuple[str, set]): (word, pages)
            score (float): Min score

        Returns:
            bool: True if the word frequency is < score, otherwise False.
        """
        word = item[0]
        if " " in word:
            return True
        return zipf_frequency(word, "en") < score

class Tokenizer:
    """
    Tokenizes text input and indexes words and phrases by page number.
    """
    WORD_SPECIAL = {'\\', '/', '-', '_', '&', '.', '@', '%', ':', '?', "=", "\'"} # special chars that can be part of a word
    PAGE_DIVIDER = '\f' # signifies end of page
    PHRASE_CONNECTORS = {"of","the","and","&","or","in","on","for","to","by","with","as","at","from","a","an","vs","via"} # used to connect words in phrases (not start/end)
    PHRASE_SEPARATORS = {",", ";", ":", "–", "•", ".", "!", "?"} # special chars that end a phrase
    
    # load middle
    PHRASE_MIDDLE = set() # may only be found in the middle of phrase, else discarded
    with open("wordlists/junk.txt", "r", encoding="utf-8") as f:
        PHRASE_MIDDLE = set(line.strip() for line in f)

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

    @classmethod
    def get_tokenizer_info(cls) -> str:
        """
        Build and return formatted help text describing Tokenizer.

        Returns:
            str: Tokenizer documentation.
        """
        return "\n".join([
            "Tokenization:",
            "    TXT files are split into pages using the form feed character (0x0C).",
            "    Text is tokenized into WORD and PHRASE tokens.",
            "    WORD tokens do not include spaces.",
            "    PHRASE tokens are built if one or more consecutive WORD tokens meets any of the following criteria:",
            "        1. Contains a capital letter and is not found in wordlists/junk.txt (First WORD only)",
            "        2. Inside double quotes",
            "        3. Inside parentheses",
            "\n"
        ])

    def _has_capital(self, word:str)->bool:
        """
        Check whether a word contains at least one uppercase letter.

        Args:
            word (str): Word to check.

        Returns:
            bool: True if the word contains an uppercase letter.
        """
        return not re.search(r'[A-Z]', word) is None

    def _add_phrase(self, phrase:str, page:int):
        """
        Add a phrase occurrence to the phrase index.

        If a filter is configured, the phrase is first checked using the pre-filter
        before being added to the index.

        Args:
            phrase (str): The phrase to index.
            page (int): The page number where the phrase occurs.
        """
        p = phrase.lower()
        if self.filter:
            if self.filter.prefilter(phrase):
                self.phrases[p].add(page)
        else:
            self.phrases[p].add(page)

    def _process_word_char(self, b: str) -> bool:
        """
        Process characters that may belong to a word.

        Returns:
            bool: True if the character was consumed.
        """

        # add to word buffer
        if re.fullmatch(r'[a-z0-9]', b, re.IGNORECASE):
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
        
        # special char exception for @handles
        elif b == "@" and not self.word and not self.word_spec:
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

            self._process_quote_word(self.word)
            self._process_paren_word(self.word)
            self._process_phrase_word(self.word)

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
            if w not in self.PHRASE_CONNECTORS and w.lower() not in self.PHRASE_MIDDLE:
                self.parens += f" {w}" if self.parens else w

    def _process_phrase_word(self, w: str):
        """
        Process phrase construction logic for a word.
        """
        if self._has_capital(w):
            if self.phrase and self.phrase_conn:
                self.phrase += f" {self.phrase_conn}"
                self.phrase_conn = ""

            if self.phrase and w.lower() in self.PHRASE_MIDDLE:
                self.phrase_conn += f" {w}" if self.phrase_conn else w

            elif w.lower() not in self.PHRASE_CONNECTORS and w.lower() not in self.PHRASE_MIDDLE:
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
            self.paren_depth = 0
            self.quoting = False

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

        # PDF
        elif self.mode == 1:
            for b in pdfminer_extract_text(BytesIO(data)).encode():
                self._process_byte(b)

        self._process_byte(0x00) # flush buffer



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
        print(f"    [!] Error reading {filename}: {e}")
    
    return data

def compress_pages(pages:list) -> str:
    """
    Compress page numbers into ranges.

    Args:
        pages: Iterable of page numbers.

    Returns:
        Comma-separated string of pages/ranges.
    """
    pages = sorted(set(pages))
    if not pages:
        return ""

    ranges = []
    start = prev = pages[0]

    for p in pages[1:]:
        if p == prev + 1:
            prev = p
        else:
            ranges.append((start, prev))
            start = prev = p

    ranges.append((start, prev))

    return ", ".join(
        str(a) if a == b else f"{a}-{b}"
        for a, b in ranges
    )

def format(*indexes:defaultdict[set]) -> str:
    """
    Format one or more indexes into a grouped alphabetical string.

    Args:
        *indexes: Dictionaries mapping words/phrases to page-number sets.

    Returns:
        Formatted index string.
    """
    output = []
    grouped = defaultdict(list)

    for index in indexes:
        for w, pages in index.items():
            grouped[w[0].upper()].append((w, pages))

    for i, letter in enumerate(sorted(grouped)):
        if i > 0:
            output.append(f"\n[{letter}]")
        else:
            output.append(f"[{letter}]")

        # sort
        combined = sorted(grouped[letter], key=lambda x: x[0])

        header = combined[0]
        output.append(f"{header[0]}: {compress_pages(header[1])}")
        for t in combined[1:]:
            text = t[0]
            pages = t[1]

            # check duplicates
            if text == header[0]:
                continue
            
            # check if text fits header
            if header[0].split(" ")[0] == text.split(" ")[0]:
                output.append(f"    {text}: {compress_pages(pages)}")
            else:
                header = t
                output.append(f"{header[0]}: {compress_pages(header[1])}")

    return "\n".join(output)

def print_status(verbose:bool, *args, **kwargs):
    """
    Conditional print.

    Args:
        verbose (bool): True if status should be printed
        *args: Passed to print()
        **kwargs: Passed to print()
    """
    if verbose:
        print(*args, **kwargs)

########################
# MAIN
########################
def main():
    # parse args
    epilog = Tokenizer.get_tokenizer_info() + WordFilter.get_filter_info()
    parser = argparse.ArgumentParser(description="Build index from TXT or PDF file.", epilog=epilog, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("input", help="Input TXT/PDF file")
    parser.add_argument("output", help="Output TXT/PDF file")

    available_filters = "".join(sorted(WordFilter.get_keys(WordFilter.PREFILTER_SWITCH) + WordFilter.get_keys(WordFilter.POSTFILTER_SWITCH)))
    parser.add_argument("-v", "--verbose", action="store_true", help="Print verbose output")
    parser.add_argument("-o", "--offset", type=int, default=0, help="Page number offset. Pages before offset are skipped (default: 0)")
    parser.add_argument("-d", "--disable", metavar=available_filters, type=str, default=None, help="Disable specified filters")
    parser.add_argument("-e", "--enable", metavar=available_filters, type=str, default=None, help="Enable only specified filters (Overrides -d)")

    # prefilters
    pre = parser.add_argument_group("pre-filter options")
    pre.add_argument("-l", "--min-length", type=int, default=None, help="Skip ALL tokens less than N characters")
    pre.add_argument("-L", "--max-length", type=int, default=None, help="Skip ALL tokens greater than N characters")

    # postfilters
    post = parser.add_argument_group("post-filter options")
    post.add_argument("-f", "--min-frequency", type=int, default=None, help="Filter out ALL tokens appearing on less than N pages")
    post.add_argument("-F", "--max-frequency", type=int, default=None, help="Filter out ALL tokens appearing on more than N pages")
    post.add_argument("-r", "--regex", type=str, default=None, help="Filter out ALL tokens that do not match regex")
    post.add_argument("-z", "--zipf", type=float, default=None, help="Filter out ALL tokens with a Zipf Score > N.")

    args = parser.parse_args()

    input_file = args.input
    output_file = args.output
    verbose = args.verbose
    offset = args.offset

    # read file
    if not verbose:
        print(f"Indexing: {input_file}")
    print_status(verbose, f"[+] Reading        : {input_file}")
    filetype = 1 if input_file.upper().endswith("PDF") else 0
    data = read_file(filename=input_file)
    print_status(verbose, f"    Mode           : {["TXT", "PDF"][filetype]}")
    print_status(verbose, f"    Size (Bytes)   : {len(data)}\n")

    # prepare filter
    print_status(verbose, f"    [+] Preparing Filters")
    word_filter = WordFilter()
    word_filter.build_from_argparse_args(args)
    print_status(verbose, f"{word_filter}\n")

    # tokenize
    print_status(verbose, f"    [+] Tokenizing")
    tokenizer = Tokenizer(page_offset=offset, filter=word_filter, mode=filetype)
    tokenizer.tokenize(data)
    print_status(verbose, f"        Words      : {len(tokenizer.words)}")
    print_status(verbose, f"        Phrases    : {len(tokenizer.phrases)}\n")

    print_status(verbose, f"        Pre-filter Hits:")
    for f_func, _ in tokenizer.filter.pre_filters:
        if tokenizer.filter.stats[f_func] > 0:
            f = next(v for v in WordFilter.FILTERS.values() if v["func"] == f_func)
            print_status(verbose, f"            {f["name"]}: {tokenizer.filter.stats[f_func]}")
    print_status(verbose, "")

    # post-filter
    print_status(verbose, f"    [+] Cleaning")
    tokenizer.words = word_filter.postfilter(tokenizer.words)
    d = tokenizer.filter.remove("filter_dictionary") # do not apply to phrases
    tokenizer.phrases = word_filter.postfilter(tokenizer.phrases)
    print_status(verbose, f"        Words      : {len(tokenizer.words)}")
    print_status(verbose, f"        Phrases    : {len(tokenizer.phrases)}\n")

    print_status(verbose, f"        Post-filter Hits:")
    for f_func, _ in tokenizer.filter.post_filters + [("filter_dictionary", None)] if d else []:
        if tokenizer.filter.stats[f_func] > 0:
            f = next(v for v in WordFilter.FILTERS.values() if v["func"] == f_func)
            print_status(verbose, f"            {f["name"]}: {tokenizer.filter.stats[f_func]}")
    print_status(verbose, "")

    # write output
    print_status(verbose, f"    [+] Writing    : {output_file}")
    result = format(tokenizer.words, tokenizer.phrases)
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(result)
    print_status(verbose, f"        Lines      : {result.count("\n") + 1}")

    if not verbose:
        print(f"{result.count("\n") + 1} Lines writen to: {output_file}")


if __name__ == "__main__":
    main()