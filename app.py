import os
import tempfile
import traceback
import requests

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

# ===== BASIC SETUP =====
app = Flask(__name__, static_folder='static')
CORS(app)

print("🚀 App is starting...")

OPENROUTER_KEY = os.getenv("OPENROUTER_KEY")

# ===== SAFE PDF EXTRACTION =====
def extract_pdf_content(pdf_path):
    results = []

    # --- TEXT EXTRACTION (SAFE) ---
    try:
        import pdfplumber
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages):
                text = page.extract_text() or ""
                results.append({
                    "page": i + 1,
                    "text": text,
                    "ocr_text": ""
                })
    except Exception as e:
        print("⚠️ pdfplumber error:", e)

    # --- OCR (OPTIONAL – won't crash if missing) ---
    try:
        import pytesseract
        from pdf2image import convert_from_path

        images = convert_from_path(pdf_path, dpi=150)

        for i, img in enumerate(images):
            if i < len(results):
                if not results[i]["text"] or len(results[i]["text"].strip()) < 50:
                    results[i]["ocr_text"] = pytesseract.image_to_string(img)
            else:
                results.append({
                    "page": i + 1,
                    "text": "",
                    "ocr_text": pytesseract.image_to_string(img)
                })

    except Exception as e:
        print("⚠️ OCR skipped (not installed or failed):", e)

    return results


def format_content(pages):
    output = []
    for p in pages:
        output.append(f"\n=== PAGE {p['page']} ===\n")
        if p["text"]:
            output.append(p["text"])
        if p["ocr_text"]:
            output.append("\n[OCR]\n" + p["ocr_text"])
    return "\n".join(output)


# ===== ROUTES =====
@app.route('/')
def index():
    return send_from_directory('static', 'index.html')


@app.route('/api/extract-pdf', methods=['POST'])
def extract_pdf():
    try:
        file = request.files.get('pdf')
        if not file:
            return jsonify({"error": "No file uploaded"}), 400

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            file.save(tmp.name)
            path = tmp.name

        try:
            pages = extract_pdf_content(path)
            content = format_content(pages)
        finally:
            os.unlink(path)

        return jsonify({
            "success": True,
            "content": content,
            "pages": len(pages)
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/api/ai', methods=['POST'])
def ai():
    try:
        if not OPENROUTER_KEY:
            return jsonify({"error": "Missing OPENROUTER_KEY"}), 500

        data = request.json

        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_KEY}",
                "Content-Type": "application/json"
            },
            json=data,
            timeout=60
        )

        return jsonify(resp.json())

    except Exception as e:
        print("❌ AI ERROR:", e)
        return jsonify({"error": str(e)}), 500


# ===== HEALTH CHECK (IMPORTANT FOR RAILWAY) =====
@app.route('/health')
def health():
    return "OK", 200


# ===== RUN LOCAL ONLY =====
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"🚀 Running on port {port}")
    app.run(host="0.0.0.0", port=port)
