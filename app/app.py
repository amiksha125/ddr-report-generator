import os
import requests
import pdfplumber
from docx import Document
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from fpdf import FPDF
import datetime
from dotenv import load_dotenv

load_dotenv()

# ---------------- CONFIG ------------------
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") 

UPLOAD_FOLDER = "uploaded_reports"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_API_KEY}"

response = requests.get(url)
if response.status_code == 200:
    models = response.json()
    print("--- ACCESSIBLE MODELS FOR YOUR KEY ---")
    for m in models.get('models', []):
        if "flash" in m['name']:
            print(f"USE THIS NAME: {m['name']}")
else:
    print(f"Error {response.status_code}: {response.text}")


# ---------------- HELPERS ------------------
def extract_text(file_path, filename):
    """Reads text from PDF or DOCX and returns a string."""
    text = ""
    try:
        if filename.lower().endswith(".pdf"):
            with pdfplumber.open(file_path) as pdf:
                text = "\n".join([page.extract_text() for page in pdf.pages if page.extract_text()])
        elif filename.lower().endswith(".docx"):
            doc = Document(file_path)
            text = "\n".join([p.text for p in doc.paragraphs])
        elif filename.lower().endswith(".txt"):
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read()
        
        # Increased limit: 1.5-flash handles much more than 15k chars
        return text.strip()[:10000] if text else "Not Available"
    except Exception as e:
        return f"Extraction Error: {str(e)}"



def call_gemini_rest(prompt):
    # Change 'gemini-2.0-flash' to 'gemini-flash-latest'
    model_name = "gemini-flash-latest" 
    
    # The URL stays the same, just with the new model name
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={GEMINI_API_KEY}"
    
    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }]
    }
    
    response = requests.post(url, headers=headers, json=payload)
    
    # Check for success
    if response.status_code == 200:
        result = response.json()
        return result['candidates'][0]['content']['parts'][0]['text']
    else:
        # If this also gives a 429, try "gemini-1.5-flash-8b" (a smaller, higher-quota model)
        raise HTTPException(status_code=response.status_code, detail=response.text)
    

# ---------------- FASTAPI APP ------------------
app = FastAPI(title="Free AI DDR Generator")



# --- CUSTOM PDF CLASS FOR BEAUTIFUL HEADERS ---
class DDR_PDF(FPDF):
    def header(self):
        # Set background color for header
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

@app.post("/generate_ddr/")
async def generate_ddr_api(
    inspection_file: UploadFile = File(...),
    thermal_file: UploadFile = File(...)
):
    try:
        # 1. Save & Extract (Keep your existing logic)
        insp_path = os.path.join(UPLOAD_FOLDER, inspection_file.filename)
        ther_path = os.path.join(UPLOAD_FOLDER, thermal_file.filename)
        
        with open(insp_path, "wb") as f: f.write(await inspection_file.read())
        with open(ther_path, "wb") as f: f.write(await thermal_file.read())

        inspection_text = extract_text(insp_path, inspection_file.filename)
        thermal_text = extract_text(ther_path, thermal_file.filename)

        # 2. Prompt
        prompt = f"""
        Act as an expert building inspector. Create a Detailed Diagnostic Report (DDR).
        
        INSPECTION DATA: {inspection_text}
        THERMAL DATA: {thermal_text}
        
        Structure the report with these EXACT headings:
        1. Property Issue Summary
        2. Area-wise Observations
        3. Probable Root Cause
        4. Severity Assessment
        5. Recommended Actions

        IMPORTANT: Do not use Markdown symbols like ### or **. 
        Use plain text headers numbered 1 through 5.
        """
        
        # 3. Generate Content
        ddr_content = call_gemini_rest(prompt)

        # 4. CREATE BEAUTIFUL PDF
        pdf = DDR_PDF()
        pdf.add_page()
        pdf.set_font("Arial", size=11)
        pdf.set_text_color(0, 0, 0)

        lines = ddr_content.split('\n')

        # --- CRITICAL: EVERYTHING BELOW MUST BE INDENTED ---
        for line in lines:
            clean_line = line.strip()
            
            # Skip empty lines but add a small gap
            if not clean_line:
                pdf.ln(2)
                continue

            # Check if this specific line is a Header
            is_header = any(clean_line.startswith(f"{i}.") for i in range(1, 6))

            if is_header:
                # Format the Heading
                pdf.ln(5)
                pdf.set_font("Arial", 'B', 12)
                pdf.set_fill_color(235, 235, 235) 
                pdf.set_text_color(30, 30, 30)
                
                header_text = clean_line.replace("###", "").replace("**", "").strip()
                pdf.cell(0, 10, f" {header_text}", ln=True, fill=True)
                
                pdf.ln(2)
                pdf.set_font("Arial", size=11) # Reset font for body
                pdf.set_text_color(0, 0, 0)
            else:
                # Format the Body Text
                body_text = clean_line.replace("**", "").replace("*", "-")
                pdf.multi_cell(0, 7, body_text)
        # --- END OF LOOP ---

        # 5. Save and Return PDF
        output_filename = f"DDR_{inspection_file.filename.split('.')[0]}.pdf"
        output_path = os.path.join(UPLOAD_FOLDER, output_filename)
        pdf.output(output_path)

        return FileResponse(output_path, media_type='application/pdf', filename=output_filename)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
