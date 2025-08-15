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
        "Extract all tables from this file and return them as JSON. "
        "Each object is a row with keys as column names: " + ", ".join(expected_columns) + ". "
        "Use the header from the first page for all subsequent pages, even if the header is missing. "
        "For size and quantity: "
        "  - Only create a row if the quantity for that size is >= 1. "
        "  - The 'size' in each row must exactly match the column header of the filled cell. "
        "  - If quantity > 1, create multiple rows for that size with the same non-size data. "
        "  - Skip all blank or zero cells. "
        "All other data from the row (product name, ID, etc.) should be copied to each new row. "
        "Ignore totals, discounts, subtotals, and summary rows. "
        "If a requested column is missing in the table, use metadata from the first page or above the table. "
        "Do NOT invent sizes or reorder them. Return valid JSON only, no extra text."
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