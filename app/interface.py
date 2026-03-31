import streamlit as st
import os
# Import the logic function from your app.py file
from app import process_and_generate_report

# Page Config
st.set_page_config(page_title="AI DDR Generator", page_icon="🏗️", layout="centered")

# Custom CSS for a "Beautiful" look
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #007bff; color: white; }
    .stHeader { color: #1e3d59; }
    </style>
    """, unsafe_allow_html=True)

st.title("🏗️ Professional DDR Generator")

st.info("ℹ️ **System Note:** This version is optimized for text-based diagnostic correlation. Image analysis is currently limited due to API Free Tier constraints.")

st.subheader("Upload inspection data to generate a Diagnostic Report")

with st.container():
    st.info("Please upload both the Physical Inspection and Thermal Analysis files.")
    
    # File Uploaders
    col1, col2 = st.columns(2)
    with col1:
        insp_file = st.file_uploader("Physical Inspection (PDF/DOCX)", type=["pdf", "docx"])
    with col2:
        ther_file = st.file_uploader("Thermal Data (PDF/DOCX/TXT)", type=["pdf", "docx", "txt"])

    # Generate Button
    if st.button("Generate Detailed Diagnostic Report"):
        if insp_file and ther_file:
            with st.spinner("AI is analyzing reports and generating PDF..."):
                try:
                    # DIRECT CALL to your app.py logic
                    # This replaces the requests.post("http://127.0.0.1:8000/...")
                    pdf_content = process_and_generate_report(insp_file, ther_file)
                    
                    if pdf_content:
                        st.success("✅ Report Generated Successfully!")
                        # Download Button for the PDF
                        st.download_button(
                            label="📥 Download Professional PDF Report",
                            data=pdf_content,
                            file_name=f"DDR_Final_Report.pdf",
                            mime="application/pdf"
                        )
                    else:
                        st.error("Backend Error: Failed to generate PDF content.")
                        
                except Exception as e:
                    # This now catches real processing errors instead of just connection errors
                    st.error(f"Processing Error: {e}")
        else:
            st.warning("Please upload both files before proceeding.")

st.markdown("---")
st.caption("Powered by Gemini 3 Flash & Streamlit Cloud")