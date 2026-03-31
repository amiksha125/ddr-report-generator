import os
import requests
import pdfplumber
from docx import Document
from fpdf import FPDF
import datetime
import io
from dotenv import load_dotenv

load_dotenv()

# ---------------- CONFIG ------------------
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") 
UPLOAD_FOLDER = "uploaded_reports"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ---------------- HELPERS ------------------
def extract_text_from_bytes(file_bytes, filename):
    text = ""
    try:
        if filename.lower().endswith(".pdf"):
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                text = "\n".join([page.extract_text() for page in pdf.pages if page.extract_text()])
        elif filename.lower().endswith(".docx"):
            doc = Document(io.BytesIO(file_bytes))
            text = "\n".join([p.text for p in doc.paragraphs])
        elif filename.lower().endswith(".txt"):
            text = file_bytes.decode("utf-8")
        
        return text.strip()[:10000] if text else "Not Available"
    except Exception as e:
        return f"Extraction Error: {str(e)}"

def call_gemini_rest(prompt):

  # Use the current stable high-performance model
    modelname = "gemini-2.5-flash" 
    
    # Switch to the v1beta endpoint to ensure the model is found
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelname}:generateContent?key={GEMINIAPIKEY}"
    
    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}]
    }
    
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 200:
        result = response.json()
        return result['candidates'][0]['content']['parts'][0]['text']
    else:
        raise Exception(f"Gemini API Error: {response.status_code} - {response.text}")
    

class DDR_PDF(FPDF):
    def header(self):
        self.set_fill_color(230, 230, 230)
        self.rect(0, 0, 210, 30, 'F')
        self.set_font('Arial', 'B', 15)
        self.set_text_color(50, 50, 50)
        self.cell(0, 10, 'DETAILED DIAGNOSTIC REPORT (DDR)', ln=True, align='C')
        self.set_font('Arial', 'I', 10)
        self.cell(0, 10, f'Generated on: {datetime.date.today()}', ln=True, align='C')
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', align='C')

# ---------------- CORE FUNCTION ------------------
def process_and_generate_report(insp_file_obj, ther_file_obj):
    # 1. Extract Text
    inspection_text = extract_text_from_bytes(insp_file_obj.getvalue(), insp_file_obj.name)
    thermal_text = extract_text_from_bytes(ther_file_obj.getvalue(), ther_file_obj.name)

    # 2. Prompt
    prompt = f"Act as an expert building inspector. Create a DDR.\nINSPECTION: {inspection_text}\nTHERMAL: {thermal_text}\nUse headers 1-5."
    
    # 3. Generate & Clean Content
    ddr_content = call_gemini_rest(prompt)

    # CRITICAL FIX: Instead of 'ignore', we replace common problematic characters
    # This ensures the text doesn't disappear.
    replacements = {
        '\u2019': "'", '\u2018': "'", '\u201d': '"', '\u201c': '"', 
        '\u2013': '-', '\u2014': '-', '\u2022': '*', 
    }
    for char, replacement in replacements.items():
        ddr_content = ddr_content.replace(char, replacement)
    
    # Final safety net for Latin-1
    ddr_content = ddr_content.encode('latin-1', 'replace').decode('latin-1')

    # 4. CREATE PDF
    pdf = DDR_PDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15) # Prevents blank pages if content overflows
    pdf.set_font("Arial", size=11)
    
    lines = ddr_content.split('\n')
    for line in lines:
        clean_line = line.strip().replace("**", "")
        if not clean_line:
            pdf.ln(2)
            continue

        is_header = any(clean_line.startswith(f"{i}.") for i in range(1, 7))
        if is_header:
            pdf.ln(5)
            pdf.set_font("Arial", 'B', 12)
            pdf.set_fill_color(235, 235, 235) 
            pdf.multi_cell(0, 10, f" {clean_line}", fill=True) # Used multi_cell for wrapping
            pdf.ln(2)
            pdf.set_font("Arial", size=11)
        else:
            pdf.multi_cell(0, 7, clean_line)

    # 5. Return as bytes
    # pdf.output() returns a bytearray/string. Streamlit's download_button loves this.
    return pdf.output(dest='S')