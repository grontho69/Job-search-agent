"""
extract_resume.py
Extracts all text from the resume PDF and prints it in full.
"""
import sys
import os
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PDF_PATH = "mahathir mohammad resume1.pdf"

# Try pdfplumber first (best layout preservation)
try:
    import pdfplumber
    print("=== RESUME TEXT (pdfplumber) ===\n")
    with pdfplumber.open(PDF_PATH) as pdf:
        for i, page in enumerate(pdf.pages, 1):
            text = page.extract_text()
            if text:
                print(f"--- Page {i} ---")
                print(text)
                print()
    print("\n=== END OF RESUME ===")
except Exception as e:
    print(f"pdfplumber failed: {e}")
    # Fallback to PyPDF2
    try:
        import PyPDF2
        print("=== RESUME TEXT (PyPDF2) ===\n")
        with open(PDF_PATH, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for i, page in enumerate(reader.pages, 1):
                text = page.extract_text()
                print(f"--- Page {i} ---")
                print(text)
                print()
        print("\n=== END OF RESUME ===")
    except Exception as e2:
        print(f"PyPDF2 also failed: {e2}")
