import argparse
from collections import defaultdict

def read_files(files):
    data = defaultdict(list)
    for i, file in enumerate(files, start=1):
        print(f"READING: {file}")
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
                    word, pages = line.strip().split(': ')
                    if ',' in pages or '-' in pages:
                        pages = f"{i}-({pages})"
                    else:
                        pages = f"{i}-{pages}"
                    data[word].append(pages)
                
                print(f"    ENTRIES: {count}")
        except Exception as e:
            print(f"    Error opening file: {e}")
    
    return data

def print_pages(pages):
    return ", ".join(sorted(set(pages)))

def format_index(index):
    output = []
    grouped = defaultdict(list)

    for w, page_list in index.items():
        grouped[w[0].upper()].append((w, page_list))

    # -------------------------
    # OUTPUT
    # -------------------------
    for letter in sorted(grouped):
        output.append(f"\n[{letter}]")

        # sort
        combined = sorted(grouped[letter], key=lambda x: x[0])

        header = combined[0]
        output.append(f"{header[0]}: {print_pages(header[1])}")
        for t in combined[1:]:
            text = t[0]
            pages = t[1]

            # check duplicates
            if text == header[0]:
                continue
            
            # check if text fits header
            if header[0].split(" ")[0] == text.split(" ")[0]:
                output.append(f"    {text}: {print_pages(pages)}")
            else:
                header = t
                output.append(f"{header[0]}: {print_pages(header[1])}")

    return "\n".join(output)

# -------------------------
# MAIN
# -------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Merge multiple index files.")

    parser.add_argument("files", nargs="+", help="Index TXT files in numerical order.")
    parser.add_argument("-o", "--output", help="Output file.")
    args = parser.parse_args()

    combined = read_files(args.files)
    print(f"TOTAL ENTRIES: {len(combined)}")
    print("Merging...")

    output = format_index(combined)
    print(f"MERGED SIZE: {output.count("\n")+1}")

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(output)

    print(f"Index written to: {args.output}")

