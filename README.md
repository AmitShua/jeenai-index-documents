---

# Document Indexing Module — JeenAI Assignment

המשימה: כתיבת סקריפט בפייתון שמקבל מסמך מסוג PDF או DOCX, מחלץ ממנו טקסט, מחלק את התוכן למקטעים, יוצר embedding לכל מקטע באמצעות Google Gemini, ושומר את המידע במסד נתונים PostgreSQL.

---
 ## JeenAI Assignment

 ## התקנה

### 1. יצירת סביבת עבודה

```bash
python -m venv venv
source venv/bin/activate
```

### 2. התקנת התלויות

```bash
pip install google-genai psycopg2-binary python-docx PyPDF2 python-dotenv
```

### 3. קובץ .env

בתיקיית הפרויקט יצרתי קובץ בשם `.env` עם ההגדרות:

```
GEMINI_API_KEY=your_api_key
POSTGRES_URL=postgresql://user:password@localhost:5432/your_db
```

---

## הרצה

הסקריפט מקבל נתיב לקובץ ושיטת חלוקה.

### חלוקה בגודל קבוע:

```bash
python index_documents.py myfile.pdf --strategy fixed
```

### חלוקה לפי משפטים:

```bash
python index_documents.py myfile.pdf --strategy sentence
```

### חלוקה לפי פסקאות:

```bash
python index_documents.py myfile.docx --strategy paragraph
```

שלבי העבודה:

1. טעינת המסמך וחילוץ הטקסט
2. חלוקת הטקסט למקטעים
3. הפקת embeddings באמצעות Gemini
4. שמירת המקטעים והווקטורים במסד הנתונים

---

## מבנה בסיס הנתונים

הסקריפט יוצר טבלה בשם `document_chunks` עם השדות:

* `id` — מספר שורה
* `chunk_text` — טקסט המקטע
* `embedding` — וקטור ההטבעה
* `filename` — שם הקובץ
* `strategy_split` — שיטת החלוקה
* `created_at` — תאריך יצירה

---

## מרכיבי הקוד

* `load_text()` — טעינת טקסט מ־PDF או DOCX
* `chunk_fixed()` — חלוקה בגודל קבוע
* `chunk_by_sentences()` — חלוקה לפי משפטים
* `chunk_by_paragraphs()` — חלוקה לפי פסקאות
* `embed_chunks()` — יצירת embeddings
* `init_db()` — יצירת טבלה והתחברות למסד הנתונים
* `save_chunks()` — שמירת המקטעים במסד הנתונים
* `main()` — ביצוע רצף התהליך

---

## מבנה הפרויקט

```
project/
│
├── index_documents.py
├── README.md
├── .env
└── .gitignore
```

---

## שימוש ב-.gitignore

```
.env
__pycache__/
*.pyc
```

---
## שימוש ב-Langflow

* חלק מהמשימה כלל בניית Agent המבצע סיכום אימיילים באמצעות רכיב מותאם אישית. 
ה-Agent נבנה ב-Langflow וכלל:
- רכיב Custom Component בשם gmail_reader
- Agent שמקבל טקסט חופשי כקלט
- חיבור בין Chat Input → Agent → רכיב gmail_reader → Chat Output

הרכיב gmail_reader מקבל מחרוזת טקסט ומחזיר אותה כערך מסוג Data, 
וה-Agent משתמש בתוצאה ליצירת סיכום או ניסוח תשובה.


---
