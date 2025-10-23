from flask import Flask, request, render_template, send_file
import os
import pandas as pd
import pdfplumber
import pytesseract
from pdf2image import convert_from_path
from PIL import Image
from docx import Document
import re

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf', 'docx'}

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_text_from_pdf(file_path):
    text = ""
    try:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        return text.strip()
    except Exception:
        return ""

def extract_text_from_scanned_pdf(file_path):
    text = ""
    try:
        images = convert_from_path(file_path, dpi=300)
        for image in images:
            page_text = pytesseract.image_to_string(image)
            text += page_text + "\n"
        return text.strip()
    except Exception:
        return ""

def extract_text_from_docx(file_path):
    doc = Document(file_path)
    text = " ".join([para.text for para in doc.paragraphs])
    return text.strip()

def extract_data(text):
    card_numbers = re.findall(r'\b\d{4}\b', text)
    dates = re.findall(r'\b\d{1,2}[-/\.][A-Za-z]{3,}[-/\.]\d{2,4}|\b\d{1,2}[-/\.]\d{1,2}[-/\.]\d{2,4}', text)
    amounts = re.findall(r'\b\d{1,3}(?:,\d{3})*(?:\.\d{2})?\b', text)
    variants = re.findall(r'\b(VISA|MasterCard|Rupay|Platinum|Signature|Gold|Titanium)\b', text, re.IGNORECASE)
    banks = re.findall(r'\b(HDFC|ICICI|SBI|Axis|Kotak|Citi|Yes Bank|Bank of Baroda|IndusInd)\b', text, re.IGNORECASE)
    data = []
    for i in range(min(len(card_numbers), len(dates), len(amounts))):
        data.append({
            "Credit Card - Last 4 Digits": card_numbers[i],
            "Transaction Date": dates[i],
            "Card Variant": variants[i] if i < len(variants) else "Unknown",
            "Transaction Amount": amounts[i],
            "Bank Name": banks[i] if i < len(banks) else "Unknown"
        })
    return data

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        if "file" not in request.files:
            return "No file uploaded.", 400
        file = request.files["file"]
        if not allowed_file(file.filename):
            return "Only PDF and DOCX files are allowed.", 400

        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(filepath)

        # Extract statement text
        if file.filename.lower().endswith(".pdf"):
            text = extract_text_from_pdf(filepath)
            if not text:
                text = extract_text_from_scanned_pdf(filepath)
        else:
            text = extract_text_from_docx(filepath)
        data = extract_data(text)
        df = pd.DataFrame(data)

        csv_path = os.path.join(app.config['UPLOAD_FOLDER'], "result.csv")
        df.to_csv(csv_path, index=False)
        table_data = df.to_dict(orient="records")

        return render_template("result.html", table_data=table_data, csv_path=csv_path)

    return render_template("index.html")

@app.route('/download')
def download():
    path = os.path.join(app.config['UPLOAD_FOLDER'], "result.csv")
    return send_file(path, as_attachment=True)

if __name__ == "__main__":
    app.run(debug=True)
