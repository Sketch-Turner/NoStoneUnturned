import argparse
from collections import defaultdict
import re

def read_files(files):
    """
    Read and merge files

    Args:
        files (list[str]): Filenames

    Returns:
        defaultdict[list]: File contents.
    """
    data = defaultdict(list)
    for i, file in enumerate(files, start=1):
        print(f"[+] Reading: {file}")
        try:
            with open(file, 'rt', encoding='utf-8') as f:
                count = 0
                for line in f.readlines():
                    # discard headers
                    if line.startswith("["):
                        continue
                    # discard empty lines
                    if line == "\n":
                        continue
                    count += 1
                    # process line
                    word, pages = line.strip().rsplit(':', 1)
                    pages = pages[1:]
                    if ',' in pages or '-' in pages:
                        pages = f"{i}-({pages})"
                    else:
                        pages = f"{i}-{pages}"
                    data[word].append(pages)
                
                print(f"    Entries: {count}")
        except Exception as e:
            print(f"    Error opening {file}: {e}")
    
    return data

def print_pages(pages):
    """
    Page number printing helper
    """
    return ", ".join(sorted(set(pages)))

def count_pages(pages):
    """
    Count number of pages using formatted page range.
    """
    total = 0

    entries = re.findall(r'(\d+)-(\([^)]*\)|\d+)', pages)

    for _, pages in entries:
        if pages.startswith('('):
            pages = pages[1:-1]
            for item in map(str.strip, pages.split(',')):
                if '-' in item:
                    start, end = map(int, item.split('-'))
                    total += end - start + 1
                else:
                    total += 1
        else:
            total += 1

    return total

def format_index(index, min_freq=None, max_freq=None):
    """
    Format one or more indexes into a grouped alphabetical string.

    Args:
        *indexes: Dictionaries mapping words/phrases to page-number sets.

    Returns:
        Formatted index string.
    """
    output = []
    grouped = defaultdict(list)

    for w, page_list in index.items():
        grouped[w[0].upper()].append((w, page_list))

    for i, letter in enumerate(sorted(grouped)):
        if i > 0:
            output.append(f"\n[{letter}]")
        else:
            output.append(f"[{letter}]")

        # sort
        combined = sorted(grouped[letter], key=lambda x: x[0])

        header = combined[0]
        pages = print_pages(header[1])
        count = count_pages(pages)
        if ((min_freq is None or count >= min_freq) and (max_freq is None or count <= max_freq)):
            output.append(f"{header[0]}: {pages}")

        for t in combined[1:]:
            text = t[0]
            pages = print_pages(t[1])
            count = count_pages(pages)

            # check frequency
            if (not ((min_freq is None or count >= min_freq) and (max_freq is None or count <= max_freq))):
                continue

            # check duplicates
            if text == header[0]:
                continue
            
            # check if text fits header
            if header[0].split(" ")[0] == text.split(" ")[0]:
                output.append(f"    {text}: {pages}")
            else:
                header = t
                pages = print_pages(header[1])
                output.append(f"{header[0]}: {pages}")

    return "\n".join(output)

# -------------------------
# MAIN
# -------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Merge multiple index files.")

    parser.add_argument("files", nargs="+", help="Index TXT files in numerical order.")
    parser.add_argument("-o", "--output", help="Output file.")
    parser.add_argument("-f", "--min-frequency", type=int, default=None, help="Filter out ALL tokens appearing on less than N pages in total")
    parser.add_argument("-F", "--max-frequency", type=int, default=None, help="Filter out ALL tokens appearing on more than N pages in total")
    args = parser.parse_args()

    combined = read_files(args.files)
    print(f"\n    Total Entries: {len(combined)}\n")
    print("[+] Merging")

    output = format_index(combined, min_freq=args.min_frequency, max_freq=args.max_frequency)
    print(f"    Merged Size: {output.count("\n")+1}")

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(output)

    print(f"    Index written to: {args.output}")