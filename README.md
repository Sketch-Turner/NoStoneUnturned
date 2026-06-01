# NoStoneUnturned
Automatic Index Builder

## Overview

Build indexes from PDF or TXT files. 

Casts a wide net but it gets everything. Could be a good option for any open-book with index test.

---
## Dependencies

### Python 3.13
- nltk
- pdfminer.six
- pypdf
- wordfreq

Install Python dependencies:

```bash
pip install nltk pdfminer.six pypdf wordfreq
```
---
## Workflow

1. Decrypt PDFs (as required)
```bash
qpdf --password=<PASSWORD> --decrypt raw.pdf raw_decrypted.pdf
```

2. Extract text (optional)
```bash
pdftotext raw_decrypted.pdf raw.txt
```
pdftotext from poppler generally gives better results than extracting from the raw PDF.
However, PDF layout is lost during conversion to text and multi-column elements may be reordered incorrectly.

3. Build index
```bash
build_index.py -v -o 2 -l 2 -L 50 -F 10 -z 4.0 -r '[a-zA-Z0-9 :.&_-]+' raw.txt index.txt
```
Recommended Settings:
- `-v`  
  Verbose output (does not affect index)
- `-o 2`  
  PDF page numbering starts on the second page
- `-l 2`  
  Minimum token length for items added to the index
- `-L 50`  
  Maximum token length for items added to the index
- `-F 10`  
  Exclude words appearing on more than 10 pages
- `-z 4.0`  
  Exclude words with a Zipf score > 4.0
- `-r`  
  Regex filter for accepted tokens

4. Merge indexes
```bash
index_merge.py -o merged_index.txt index1.txt index2.txt index3.txt
```


