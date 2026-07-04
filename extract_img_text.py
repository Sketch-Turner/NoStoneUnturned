import io
import argparse
import fitz
import numpy as np
import tqdm
from doctr.models import ocr_predictor
from PIL import Image, ImageEnhance


# -------------------------
# OCR setup 
# -------------------------
ocr = ocr_predictor(
    det_arch="db_resnet50",
    reco_arch="parseq",
    pretrained=True,
)

def preprocess(image:Image.Image):
    """
    Preprocess an image to improve OCR accuracy.

    The image is converted to RGB, optionally upscaled if its width is
    below 1800 pixels, and given a slight contrast enhancement. 

    Args:
        image (PIL.Image.Image):
            The input image.

    Returns:
        PIL.Image.Image:
            The preprocessed image ready for OCR.
    """
    image = image.convert("RGB")

    # enlarge small images
    if image.width < 1800:
        image = image.resize(
            (image.width * 2, image.height * 2),
            Image.Resampling.LANCZOS,
        )

    image = ImageEnhance.Contrast(image).enhance(1.3)

    return image

def extract_images(page:"fitz.Page", doc:"fitz.Document", tolerance:float=0.1)->list[list[tuple[fitz.Rect, Image.Image]]]:
    """
    Extract and group images from a PDF page.

    Images that are split into multiple horizontal bands are automatically
    reassembled by grouping adjacent image fragments with matching horizontal
    bounds.

    Args:
        page (fitz.Page):
            The PDF page from which to extract images.
        doc (fitz.Document):
            The parent PDF document.
        tolerance (float, optional):
            Maximum allowed difference (in PDF points) when comparing image
            boundaries for grouping. Defaults to 0.1.

    Returns:
        list[list[tuple[fitz.Rect, PIL.Image.Image]]]:
            A list of image groups. Each group contains tuples of the form
            ``(rect, image)``, where ``rect`` is the image's location on the
            page and ``image`` is the extracted PIL image. Images within a
            group are ordered from top to bottom.
    """
    entries = []

    for img in page.get_images(full=True):
        xref = img[0]

        for rect in page.get_image_rects(xref):
            image_bytes = doc.extract_image(xref)["image"]
            image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

            entries.append((rect, image))

    # top-to-bottom
    entries.sort(key=lambda x: (x[0].x0, x[0].y0))

    groups = []

    for rect, image in entries:

        for group in groups:
            last_rect, last_image = group[-1]

            if (
                abs(rect.x0 - last_rect.x0) <= tolerance
                and abs(rect.x1 - last_rect.x1) <= tolerance
                and abs(rect.y0 - last_rect.y1) <= tolerance
            ):
                group.append((rect, image))
                break
        else:
            groups.append([(rect, image)])

    return groups

def build_image(group:list[tuple[fitz.Rect, Image.Image]])->Image.Image:
    """
    Reassemble a grouped image from its constituent bands.

    Image fragments are sorted from top to bottom using their PDF placement
    rectangles and stitched together into a single image. This is primarily
    used to reconstruct images that have been split into multiple horizontal
    bands within the PDF.

    Args:
        group (list[tuple[fitz.Rect, PIL.Image.Image]]):
            A list of ``(rect, image)`` tuples representing the image bands
            belonging to a single logical image.

    Returns:
        PIL.Image.Image:
            The reconstructed image formed by vertically stitching the image
            bands together.
    """
    group.sort(key=lambda x: x[0].y0)

    width = max(img.width for _, img in group)
    height = sum(img.height for _, img in group)

    stitched = Image.new("RGB", (width, height))

    y = 0

    for _, img in group:
        stitched.paste(img, (0, y))
        y += img.height

    return stitched

def run_ocr(image:Image.Image)->str:
    """
    Extract text from an image using the DocTR OCR pipeline.

    The input image is converted to a NumPy array and passed to the OCR
    predictor. Recognized words are reconstructed into lines while
    preserving the document's detected reading order. Blocks are separated
    by blank lines in the returned text.

    Args:
        image (PIL.Image.Image):
            The preprocessed image to analyze.

    Returns:
        str:
            The extracted text. Returns an empty string if no text is
            recognized.
    """
    arr = np.array(image)

    result = ocr([arr])

    lines = []

    for page in result.pages:
        for block in page.blocks:
            for line in block.lines:
                words = [word.value for word in line.words]

                if words:
                    lines.append(" ".join(words))

    return "\n\n".join(lines).strip()

def main(input_file: str, output_file: str):
    """
    Extract images from a PDF, perform OCR, and replace each image with its
    recognized text.

    Args:
        input_file (str):
            Path to the input PDF.
        output_file (str):
            Path where the modified PDF will be written.
    """
    print(f"[+] Reading: {input_file}\n")

    doc = fitz.open(input_file)

    total_images = 0
    total_words = 0

    for page in tqdm.tqdm(doc, total=len(doc), unit="page"):
        groups = extract_images(page, doc)

        for group in groups:
            image = build_image(group)
            image = preprocess(image)

            text = run_ocr(image)
            if not text:
                continue

            total_words += len(text.split())
            total_images += len(group)

            # rectangle covering the whole stitched image
            rect = fitz.Rect(group[0][0])

            for r, _ in group[1:]:
                rect |= r

            # remove the image
            page.add_redact_annot(
                rect,
                fill=(1, 1, 1),  # white background
            )

            page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_REMOVE)

            # replace with OCR text
            page.insert_textbox(
                rect,
                text,
                fontsize=4,
                fontname="helv",
                overlay=True,
            )

    print(f"\n    Images processed: {total_images}")
    print(f"    Words extracted: {total_words}")

    doc.save(output_file)
    doc.close()

    print(f"[+] Written to: {output_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Extract OCR text from images in a PDF and inject into PDF."
    )

    parser.add_argument("input", help="Input PDF file")
    parser.add_argument("output", help="Output PDF file")

    args = parser.parse_args()

    main(args.input, args.output)