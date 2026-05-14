from collections import defaultdict
import argparse

class Tokenizer:
    """
    Tokenizes text input and indexes words and phrases by page number.
    """
    WORD_SPECIAL = ['\\', '/', '-', '_', '&', '.'] # special chars that can be part of a word
    PAGE_DIVIDER = '\f' # signifies end of page

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
        self.parens = ""
        self.phrase = ""
        self.page = 1 - page_offset

        # storage
        self.words = defaultdict(list) # word: pages
        self.phrases = defaultdict(list) # phrase: pages

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
        
        # new page
        if b == self.PAGE_DIVIDER:
            self.page += 1

        # flush word buffer
        if self.word:
            if self.page > 0:
                self.words[self.word.lower()].append(self.page)
            self.word = ""
            self.word_spec = ""






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
    print(f"    [+] Tokenizing:")
    tokenizer = Tokenizer(page_offset=offset)
    for b in data:
        tokenizer.process(b)
    print(f"        Words      : {len(tokenizer.words)}")


    print(sorted(tokenizer.words.items())[:20])
        
if __name__ == "__main__":
    main()