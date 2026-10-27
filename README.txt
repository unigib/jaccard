Document Similarity Checker
===========================

Run the app with:
    python -m pip install -r requirements.txt
    python app.py

The app uses Python's built-in Tkinter interface and compares entered or
extracted text with all UTF-8 .txt files in the corpus folder. Load .txt, .docx,
or text-based .pdf documents. Their extracted text appears in the input box;
use "Save text as .txt" to save it. Scanned PDFs that contain only page images
are not supported because OCR is not included. The default suspicion threshold
is 30%; the threshold can be adjusted in the app. A result at or above the
threshold is labelled "Suspect Plagiarism". This is an educational similarity
demo, not a conclusive plagiarism judgment.

The interface uses the University of Gibraltar branding and the accompanying
logo.png image. Keep logo.png in the same folder as app.py.

Algorithm
---------
1. Normalize: lowercase the text and replace punctuation with spaces.
2. Create trigrams: split into words and create every unique sequence of three
   consecutive words.
3. Compare: calculate |A intersect B| / |A union B| * 100 for each corpus file.
   The highest score is shown first, and shared trigrams are listed below.

The comparison uses sets, so repeated occurrences of the same trigram count
once. Similarity is based on overlap with each whole reference document, not a
claim that the source of matching text has been established.

During a check, the app reports four phases: normalizing the submission,
creating its trigrams, preparing reference trigrams, and calculating scores.
Reference trigrams are cached in memory for the current app session; changing
or adding corpus files is detected for the next check. The first check indexes
the corpus, while subsequent checks reuse the prepared data.

Demo inputs
-----------
Use demo_inputs/original.txt for a low-overlap example and
demo_inputs/suspect.txt for a high-overlap example based on article_1_climate.txt.

AI reflection prompts
---------------------
For the assignment reflection, describe the prompts and AI assistance you
actually used, and note any corrections you made while testing the output.
Do not treat this template as a record of personal experience.

Changing the n-gram size changes what the score measures. With N=1, individual
common words produce many matches, so unrelated documents can appear similar.
With N=10, matches require much longer exact sequences, making scores lower and
more sensitive to even small wording changes. This app fixes N at 3 so its
phrases are trigrams as required by the assignment.

Run the algorithm tests with:
    python -m unittest

Project Gutenberg corpus downloader
-----------------------------------
Run the optional downloader with:
    python gutenberg_downloader.py

Enter an inclusive start/end ID range; for example, ID 16328 downloads from
https://www.gutenberg.org/cache/epub/16328/pg16328.txt. Downloads are saved as
pg<ID>.txt in the selected folder, which defaults to corpus/. The downloader
waits one second between requests, limits a run to 1,000 IDs, skips files that
already exist, and allows cancellation. Gutenberg IDs may be missing or may
not have a plain-text file at this URL; those IDs are reported rather than
retried. Check each work's copyright and license terms for your jurisdiction
before reusing it. The downloader is for small, deliberate demo collections,
not bulk harvesting.
