# NoStoneUnturned
Automatic Index Builder

## Contents

- [Overview](#overview)
- [Requirements](#requirements)
  - [Optional 3rd Party Accessories](#optional-3rd-party-accessories)
  - [Python 3.13](#python-313)
- [Workflow (Linux)](#workflow-linux)
  - [3rd Party Installs](#3rd-party-installs)
  - [Python Environment Setup](#python-environment-setup)
  - [Index Building](#index-building)
    - [1. Decrypt PDFs (as required)](#1-decrypt-pdfs-as-required)
    - [2. Extract text from images (as required)](#2-extract-text-from-images-as-required)
    - [3. Convert to TXT (optional)](#3-convert-to-txt-optional)
    - [4. Build index](#4-build-index)
    - [5. Merge indexes](#5-merge-indexes)
- [Workflow (Windows)](#workflow-windows)
  - [3rd Party Installs](#3rd-party-installs-1)
  - [Python Environment Setup](#python-environment-setup-1)
  - [Index Building](#index-building-1)
    - [1. Decrypt PDFs (as required)](#1-decrypt-pdfs-as-required-1)
    - [2. Extract text from images (as required)](#2-extract-text-from-images-as-required-1)
    - [3. Convert to TXT (optional)](#3-convert-to-txt-optional-1)
    - [4. Build index](#4-build-index-1)
    - [5. Merge indexes](#5-merge-indexes-1)

## Overview

Build indexes from PDF or TXT files. 

Casts a wide net but it gets everything. Could be a good option for any open-book with index test.

![Workflow](./workflow.png)

---
## Requirements

### Optional 3rd Party Accessories
 - qpdf
 - pdftotext

### Python 3.13
 - PyMuPDF
 - Pillow
 - numpy
 - python-doctr
 - torch
 - torchvision
 - pdfminer.six
 - pypdf
 - wordfreq
 - nltk
 - tqdm

---
## Workflow (Linux)

### 3rd Party Installs

```bash
sudo apt update
sudo apt install qpdf poppler-utils
```

### Python Environment Setup

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

### Index Building

#### 1. Decrypt PDFs (as required)
```bash
qpdf --password='PASSWORD' --decrypt book_n.pdf decrypted_n.pdf
```

#### 2. Extract text from images (as required)
```bash
.venv/bin/python extract_img_text.py decrypted_n.pdf processed_n.pdf
```
This is a time-consuming step that is not required for most PDFs.
Even some PDF that look like they contain images are actually composed of text elements only.

#### 3. Convert to TXT (optional)
```bash
pdftotext processed_n.pdf text_n.txt
```
pdftotext generally gives slightly better results than extracting from the raw PDF.
However, PDF layout is lost during conversion to text and multi-column elements may be reordered incorrectly.

#### 4. Build index
```bash
.venv/bin/python build_index.py -v -o 2 -l 2 -L 50 -F 10 -z 4.0 -r '[a-zA-Z0-9 :.&_-]+' text_n.txt index_n.txt
```
Recommended Settings:
- `-v`  
  Verbose output (does not affect index content)
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

#### 5. Merge indexes
```bash
.venv/bin/python index_merge.py -o index.txt -F 10 index_1.txt index_2.txt index_n.txt
```
Recommended Settings:
- `-F 10`  
  Exclude words appearing on more than 10 pages total 

---
## Workflow (Windows)

### 3rd Party Installs

Install the following tools and ensure they are available on your `PATH`:

- **qpdf**
- **Poppler for Windows** (provides `pdftotext`)

Using Winget:

```powershell
winget install QPDF.QPDF
winget install oschwartz10612.Poppler
```

Or download manually:

- QPDF: https://qpdf.sourceforge.io/
- Poppler: https://github.com/oschwartz10612/poppler-windows/releases

### Python Environment Setup

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### Index Building

#### 1. Decrypt PDFs (as required)
```powershell
qpdf --password="PASSWORD" --decrypt book_n.pdf decrypted_n.pdf
```

#### 2. Extract text from images (as required)
```powershell
.\.venv\Scripts\python.exe extract_img_text.py decrypted_n.pdf processed_n.pdf
```

This is a time-consuming step that is not required for most PDFs.
Even some PDFs that appear to contain images are actually composed entirely of searchable text.

#### 3. Convert to TXT (optional)
```powershell
pdftotext processed_n.pdf text_n.txt
```

pdftotext generally produces slightly better results than extracting text directly from the PDF.
However, PDF layout is lost during conversion and multi-column content may be reordered incorrectly.

#### 4. Build index
```powershell
.\.venv\Scripts\python.exe build_index.py -v -o 2 -l 2 -L 50 -F 10 -z 4.0 -r "[a-zA-Z0-9 :.&_-]+" text_n.txt index_n.txt
```

Recommended Settings:

- `-v`  
  Verbose output (does not affect index content)

- `-o 2`  
  PDF page numbering starts on the second page

- `-l 2`  
  Minimum token length for items added to the index

- `-L 50`  
  Maximum token length for items added to the index

- `-F 10`  
  Exclude words appearing on more than 10 pages

- `-z 4.0`  
  Exclude words with a Zipf score greater than 4.0

- `-r`  
  Regex filter for accepted tokens

#### 5. Merge indexes
```powershell
.\.venv\Scripts\python.exe index_merge.py -o index.txt -F 10 index_1.txt index_2.txt index_n.txt
```

Recommended Settings:

- `-F 10`  
  Exclude words appearing on more than 10 pages across all input indexes.