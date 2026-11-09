"""Generate a wholly synthetic local DOCX for UI smoke testing. Not legal advice."""
from pathlib import Path
import argparse

from docx import Document


def build(path: Path):
    doc = Document()
    doc.add_heading("Mutual Non-Disclosure Agreement — SYNTHETIC TEST ONLY", 0)
    for text in [
        "The two fictional businesses, Example Alpha LLC and Example Beta LLC, enter this mutual NDA.",
        "Each party may be both a Disclosing Party and a Receiving Party of Confidential Information.",
        "Confidential Information includes nonpublic business information.",
        "The Recipient may use Confidential Information for any purpose.",
        "The obligation to protect Confidential Information shall continue perpetually.",
        "This Agreement is governed by the laws of the State of New York.",
        "This fictional document is not intended for signing, distribution or actual legal use.",
    ]:
        doc.add_paragraph(text)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=Path("./synthetic-mutual-nda.docx"))
    args = parser.parse_args()
    build(args.out)
    print("Synthetic document written:", args.out)
