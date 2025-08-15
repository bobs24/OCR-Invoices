# Mistral OCR Table Extractor

A Streamlit application that uses the Mistral AI API to perform Optical Character Recognition (OCR) and extract structured table data from uploaded images.

## Table of Contents
- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Usage](#usage)
- [Project Structure](#project-structure)
- [Acknowledgments](#acknowledgments)
- [License](#license)

## Features
- **Image Upload:** Easily upload images (JPG, JPEG, PNG) through a simple web interface.
- **Table Extraction:** Utilizes the advanced multimodal capabilities of the Mistral AI to accurately identify and extract tables.
- **Structured Output:** Presents the extracted table data in a clean, readable Markdown format directly within the application.
- **Secure API Key Management:** Uses Streamlit's built-in secrets management to keep your API keys secure.

## Prerequisites
Before you begin, ensure you have the following installed:
- Python 3.8 or higher
- `pip` package manager

You will also need a **Mistral AI API key**. You can obtain one by signing up on the official [Mistral AI Platform](https://platform.mistral.ai/).

## Installation
1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/your-username/ocr_streamlit_app.git](https://github.com/your-username/ocr_streamlit_app.git)
    cd ocr_streamlit_app
    ```

2.  **Create a virtual environment (optional but recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
    ```

3.  **Install the required dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Set up your API key:**
    Create a `.streamlit` folder and a `secrets.toml` file inside it.
    ```bash
    mkdir .streamlit
    touch .streamlit/secrets.toml
    ```
    Add your Mistral API key to the `secrets.toml` file:
    ```toml
    # .streamlit/secrets.toml
    MISTRAL_API_KEY="your_mistral_api_key_here"
    ```

## Usage
To run the application, simply execute the following command from the project's root directory:

```bash
streamlit run app.py