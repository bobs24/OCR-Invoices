import streamlit as st
import base64
from mistralai import Mistral
import pandas as pd
from io import BytesIO
import json
import re
import pdfplumber
from PIL import Image
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- App Title ---
st.title("Mistral Table Extractor (Fast Multi-Image & PDF)")

# --- Sidebar Option ---
source_option = st.sidebar.selectbox(
    "Select source",
    ["From Images", "From PDF"]
)

# --- Dynamic Description ---
if source_option == "From Images":
    st.write("Upload one or more images containing tables. Mistral AI will extract and append all tables.")
elif source_option == "From PDF":
    st.write("Upload a PDF containing tables. Mistral AI will convert each page to an image (resolution 230) and extract tables.")

# --- API Client ---
try:
    api_key = st.secrets["MISTRAL_API_KEY"]
    client = Mistral(api_key=api_key)
except KeyError:
    st.error("Mistral API key not found. Add it to `.streamlit/secrets.toml`.")
    st.stop()

# --- File Upload ---
uploaded_files = None
if source_option == "From Images":
    st.subheader("Upload Images")
    uploaded_files = st.file_uploader(
        "Choose image files...",
        type=["jpg", "jpeg", "png"],
        accept_multiple_files=True
    )
elif source_option == "From PDF":
    st.subheader("Upload PDF")
    uploaded_files = st.file_uploader("Choose a PDF file...", type=["pdf"], accept_multiple_files=False)

# --- PDF to Images ---
def pdf_to_images_resized(file_bytes, resolution=230, max_width=1024):
    images = []
    with pdfplumber.open(BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            img = page.to_image(resolution=resolution).original
            if img.width > max_width:
                ratio = max_width / img.width
                new_height = int(img.height * ratio)
                img = img.resize((max_width, new_height))
            images.append(img)
    return images

# --- Convert PIL Image to Base64 ---
def image_to_base64(img):
    buf = BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")

# --- Mistral Extraction for One Image ---
def process_image(img, instruction_prompt):
    base64_file = image_to_base64(img)
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": instruction_prompt},
                {"type": "image_url", "image_url": f"data:image/png;base64,{base64_file}"}
            ]
        }
    ]
    response = client.chat.complete(model="mistral-large-latest", messages=messages)
    extracted_text = response.choices[0].message.content.strip()
    if not extracted_text:
        return []
    json_match = re.search(r"\[.*\]", extracted_text, re.DOTALL)
    if not json_match:
        return []
    return json.loads(json_match.group(0))

# --- Concurrent Processing ---
def process_images_concurrent(images, instruction_prompt, max_workers=8):
    all_data = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(process_image, img, instruction_prompt) for img in images]
        for future in as_completed(futures):
            all_data.extend(future.result())
    return all_data

# --- Main Logic ---
if uploaded_files:
    if source_option == "From Images":
        st.write(f"{len(uploaded_files)} image(s) uploaded.")
    else:
        st.write(f"Uploaded file: {uploaded_files.name}")

    # --- Expected Columns ---
    expected_columns_input = st.text_input(
        "Enter expected column headers (comma separated)",
        value="Invoice Number,Date,Supplier,Customer,Item,Qty,Price,Total"
    )
    expected_columns = [col.strip() for col in expected_columns_input.split(",") if col.strip()]

    # --- Instruction Prompt ---
    instruction_prompt = (
        "You are a meticulous data extraction and transformation system. "
        "Your task is to extract all tables from the provided file (PDF, image, spreadsheet, or other formats) "
        "and transform them into a single JSON array. "
        "Each JSON object represents exactly one row from the table in the file — no more, no less.\n\n"
        "0. COLUMN PRIORITY:\n"
        "   - If the user provides a specific list of expected columns, strictly follow that column order and naming exactly: "
        f"{expected_columns if expected_columns else '[No columns provided — detect automatically]'}.\n"
        "   - If no expected columns are provided, automatically detect them from the first table on the first page and use them for all pages.\n\n"
        "1. COLUMN DETECTION & CONSISTENCY:\n"
        "   - Classify columns into:\n"
        "       a) 'Identifier' columns: static product info (e.g., product name, code, color, category).\n"
        "       b) 'Value' columns: numeric quantities for specific sizes or attributes (e.g., S, M, L, 35, 45).\n"
        "   - Preserve exact header names—no rewording, no guessing.\n\n"
        "2. ROW PROCESSING:\n"
        "   - Output exactly one JSON object for each row in the table.\n"
        "   - Each JSON object must include all 'identifier' and 'value' columns exactly as they appear.\n"
        "   - Keep the original quantity as shown in the table — do not change it to 1 and do not multiply rows.\n"
        "   - Never create extra rows that are not in the source.\n\n"
        "3. DATA ACCURACY REQUIREMENTS:\n"
        "   - Ensure every value is correctly aligned with its original header.\n"
        "   - Preserve exact spelling, punctuation, and capitalization from the source.\n"
        "   - If an 'identifier' value is missing, search the surrounding document text (e.g., title above the table) to fill it in.\n\n"
        "4. FILTERING & EXCLUSIONS:\n"
        "   - Exclude totals, subtotals, discounts, and any summary rows.\n"
        "   - Omit rows with all quantities empty or zero.\n"
        "   - Never invent new sizes or reorder the size columns.\n\n"
        "5. FINAL OUTPUT FORMAT:\n"
        "   - Output only a valid JSON array containing all row objects.\n"
        "   - Do not include any explanations, comments, or extra text — JSON array only.\n"
    )


    if st.button("Extract Table"):
        with st.spinner("Extracting table data..."):
            try:
                all_images = []
                # --- Prepare Images ---
                if source_option == "From Images":
                    for f in uploaded_files:
                        img = Image.open(f)
                        all_images.append(img)
                else:  # PDF
                    pdf_bytes = uploaded_files.read()
                    all_images = pdf_to_images_resized(pdf_bytes, resolution=230)

                # --- Process All Images Concurrently ---
                all_data = process_images_concurrent(all_images, instruction_prompt, max_workers=8)

                # --- Combine and Display Data ---
                if all_data:
                    df = pd.DataFrame(all_data)
                    st.success("Extraction complete! 🎉")
                    st.dataframe(df)

                    # --- Download Excel ---
                    output = BytesIO()
                    with pd.ExcelWriter(output, engine="openpyxl") as writer:
                        df.to_excel(writer, index=False, sheet_name="Extracted Table")
                    excel_data = output.getvalue()
                    st.download_button(
                        label="💾 Download as Excel",
                        data=excel_data,
                        file_name="extracted_table.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                else:
                    st.warning("No data extracted from uploaded files.")
            except Exception as e:

                st.error(f"An error occurred: {e}")


