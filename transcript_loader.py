import pdfplumber
import re
from typing import IO

def load_txt(file: IO) -> str:
    return file.read().decode("utf-8")

def load_pdf(file: IO) -> str:
    text = ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            text += page.extract_text() + "\n"
    return text

def load_srt(file: IO) -> str:
    content = file.read().decode("utf-8")
    # Remove index numbers and timestamps
    text = re.sub(r"\d+\n\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}", "", content)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()

def load_transcript(file: IO) -> str:
    filename = file.name.lower()
    if filename.endswith(".txt"):
        return load_txt(file)
    elif filename.endswith(".pdf"):
        return load_pdf(file)
    elif filename.endswith(".srt"):
        return load_srt(file)
    else:
        raise ValueError("Unsupported file format.")
