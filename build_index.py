from collections import defaultdict
import argparse

class Tokenizer:
    """
    Tokenizes text input and indexes words and phrases by page number.
    """
    WORD_SPECIAL = ['\\', '/', '-', '_', '&', '.'] # special chars that can be part of a word
    PAGE_DIVIDER = '\f' # signifies end of page
    PHRASE_CONNECTORS = {"of","the","and","&","or","in","on","for","to","by","with","as","at","from","a","an","vs"} # used to connect words in phrases (not start/end)

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
        self.page = 1 - page_offset

        # storage
        self.words = defaultdict(set) # word: pages
        self.phrases = defaultdict(set) # phrase: pages

    def process(self, b:chr):
        """
        Process a single character of input.

        Args:
            b (chr): Character to process.
        """
        b = chr(b)

        # add to word buffer
        if b.isalnum():
            if self.word_spec:
                self.word += self.word_spec
                self.word_spec = ""
            self.word += b
            return

        # special char, add to spec buffer
        elif b in self.WORD_SPECIAL and self.word and not self.word_spec:
            self.word_spec += b
            return
        
        # flush word buffer
        if self.word:
            if self.page > 0:
                w = self.word.lower()

                # add to words
                self.words[w].add(self.page)

                # add to quote
                if self.quoting:
                    self.quote += f" {w}" if self.quote else f"{w}"

                # add to paren
                if self.paren_depth > 0:
                    self.parens += f" {w}" if self.parens else f"{w}" if not w in self.PHRASE_CONNECTORS else ""

            self.word = ""
            self.word_spec = ""

        # quote
        if b == "\"":
            # end quote
            if self.quoting:
                self.quoting = False
                
                # flush quote buffer
                if self.quote:
                    if self.page > 0:
                        self.phrases[self.quote.lower()].add(self.page)

                    self.quote = ""

            # start quote
            else: 
                self.quoting = True

        # parens
        if b == "(":
            # start parens
            self.paren_depth += 1

        elif b == ")":
            # end parens
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

        # new page
        if b == self.PAGE_DIVIDER:
            self.page += 1






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