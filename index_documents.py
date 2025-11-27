#!/usr/bin/env python
# index_documents.py
# סקריפט שמקבל קובץ (PDF או DOCX), מחלק אותו למקטעים,
# יוצר לכל מקטע embedding בעזרת Gemini ושומר הכול ב-PostgreSQL.

import os
import re
import argparse
from datetime import datetime

import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv
from PyPDF2 import PdfReader
import docx

from google import genai
from google.genai import types

# טוען משתני סביבה מקובץ .env (אם קיים)
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
POSTGRES_URL = os.getenv("POSTGRES_URL")

if not GEMINI_API_KEY:
    raise RuntimeError("חסר GEMINI_API_KEY (להגדיר בקובץ .env)")
if not POSTGRES_URL:
    raise RuntimeError("חסר POSTGRES_URL (להגדיר בקובץ .env)")

# יצירת לקוח ל-Gemini
client = genai.Client(api_key=GEMINI_API_KEY)


# ========= שלב 1: קריאת קובץ וחילוץ טקסט =========

def read_pdf(path):
    """קורא PDF ומחזיר טקסט אחד ארוך."""
    reader = PdfReader(path)
    pages_text = []
    for page in reader.pages:
        pages_text.append(page.extract_text() or "")
    return "\n".join(pages_text)


def read_docx(path):
    """קורא DOCX ומחזיר טקסט אחד ארוך."""
    document = docx.Document(path)
    paras = [p.text for p in document.paragraphs]
    return "\n".join(paras)


def load_text(path):
    """בודק את הסיומת וקורא את הקובץ בהתאם."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        text = read_pdf(path)
    elif ext in (".docx", ".doc"):
        text = read_docx(path)
    else:
        raise ValueError("נתמך רק PDF או DOCX")

    # קצת ניקוי בסיסי
    text = text.replace("\r", "\n")
    text = re.sub(r"\n{2,}", "\n\n", text)
    return text.strip()


# ========= שלב 2: חלוקת טקסט למקטעים =========

def chunk_fixed(text, chunk_size=800, overlap=200):
    """
    חלוקה לפי מספר תווים.
    כל מקטע באורך ~800 תווים עם חפיפה של 200 בין מקטע למקטע.
    """
    chunks = []
    start = 0
    length = len(text)

    while start < length:
        end = min(start + chunk_size, length)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        # חוזרים קצת אחורה כדי שתהיה חפיפה
        start = end - overlap
        if start < 0:
            start = 0

    return chunks


def chunk_by_sentences(text, max_chars=800):
    """
    חלוקה לפי משפטים.
    כל מקטע הוא כמה משפטים עד ~800 תווים.
    """
    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks = []
    current = ""

    for sent in sentences:
        sent = sent.strip()
        if not sent:
            continue

        # אם עוד משפט נכנס במקטע הנוכחי
        if len(current) + len(sent) + 1 <= max_chars:
            current = (current + " " + sent).strip()
        else:
            if current:
                chunks.append(current)
            current = sent

    if current:
        chunks.append(current)

    return chunks


def chunk_by_paragraphs(text, max_chars=1000):
    """
    חלוקה לפי פסקאות (שורה ריקה = מעבר פסקה).
    מאחד פסקאות קצרות ביחד עד ~1000 תווים.
    """
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks = []
    current = ""

    for para in paragraphs:
        # אם הפסקה עוד נכנסת במקטע הנוכחי
        if len(current) + len(para) + 2 <= max_chars:
            current = (current + "\n\n" + para).strip()
        else:
            if current:
                chunks.append(current)
            current = para

    if current:
        chunks.append(current)

    return chunks


def split_text(text, strategy):
    """בוחר אסטרטגיית חלוקה לפי מה שהמשתמש ביקש."""
    strategy = strategy.lower()
    if strategy == "fixed":
        return chunk_fixed(text)
    elif strategy == "sentence":
        return chunk_by_sentences(text)
    elif strategy == "paragraph":
        return chunk_by_paragraphs(text)
    else:
        raise ValueError("strategy חייב להיות: fixed / sentence / paragraph")


# ========= שלב 3: יצירת Embeddings עם Gemini =========

def embed_chunks(chunks):
    """
    מקבל רשימת מקטעים (strings) ומחזיר רשימת embeddings.
    כל embedding הוא רשימת מספרים (וקטור).
    """
    if not chunks:
        return []

    result = client.models.embed_content(
        model="gemini-embedding-001",
        contents=chunks,
        config=types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT")
    )

    vectors = [e.values for e in result.embeddings]
    return vectors


# ========= שלב 4: שמירה ל-PostgreSQL =========

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS document_chunks (
    id SERIAL PRIMARY KEY,
    chunk_text TEXT NOT NULL,
    embedding DOUBLE PRECISION[] NOT NULL,
    filename TEXT NOT NULL,
    strategy_split TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
"""


def init_db():
    """יוצר חיבור ל-PostgreSQL ודואג שהטבלה קיימת."""
    conn = psycopg2.connect(POSTGRES_URL)
    with conn:
        with conn.cursor() as cur:
            cur.execute(CREATE_TABLE_SQL)
    return conn


def save_chunks(conn, chunks, embeddings, filename, strategy):
    """שומר את כל המקטעים והוקטורים בטבלה."""
    if len(chunks) != len(embeddings):
        raise ValueError("מספר המקטעים לא שווה למספר ה-embeddings")

    rows = []
    for chunk, emb in zip(chunks, embeddings):
        rows.append(
            (chunk, emb, filename, strategy, datetime.utcnow())
        )

    sql = """
    INSERT INTO document_chunks (chunk_text, embedding, filename, strategy_split, created_at)
    VALUES %s
    """

    with conn:
        with conn.cursor() as cur:
            execute_values(cur, sql, rows)


# ========= שלב 5: main – נקודת הכניסה לסקריפט =========

def main():
    parser = argparse.ArgumentParser(
        description="אינדוקס מסמך: חלוקה למקטעים + יצירת embeddings ושמירה ל-PostgreSQL."
    )
    parser.add_argument("file_path", help="נתיב לקובץ PDF או DOCX")
    parser.add_argument(
        "--strategy",
        default="fixed",
        choices=["fixed", "sentence", "paragraph"],
        help="שיטת חלוקה: fixed / sentence / paragraph (ברירת מחדל: fixed)",
    )
    args = parser.parse_args()

    print(f"[+] קורא את הקובץ: {args.file_path}")
    text = load_text(args.file_path)

    print(f"[+] מחלק למקטעים לפי אסטרטגיה: {args.strategy}")
    chunks = split_text(text, args.strategy)
    print(f"[+] נוצרו {len(chunks)} מקטעים")

    print("[+] יוצר embeddings בעזרת Gemini...")
    embeddings = embed_chunks(chunks)

    print("[+] מתחבר למסד הנתונים ויוצר טבלה אם צריך...")
    conn = init_db()

    print("[+] שומר את המקטעים והוקטורים בטבלה...")
    filename_only = os.path.basename(args.file_path)
    save_chunks(conn, chunks, embeddings, filename_only, args.strategy)
    conn.close()

    print("[✓] הסתיים בהצלחה – כל המידע נשמר בטבלת document_chunks.")


if __name__ == "__main__":
    main()
