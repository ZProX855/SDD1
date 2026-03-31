import os
import tempfile
import traceback
import requests

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

app = Flask(__name__, static_folder='static')
CORS(app)

OPENROUTER_KEY = os.getenv("OPENROUTER_KEY")

def extract_pdf_content(pdf_path):
    results = []
    try:
        import pdfplumber
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages):
                text = page.extract_text() or ""
                results.append({"page": i+1, "text": text})
    except Exception as e:
        print("pdfplumber error:", e)
    return results

def format_content(pages):
    return "\n".join([f"=== PAGE {p['page']} ===\n{p['text']}" for p in pages])

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/api/extract-pdf', methods=['POST'])
def extract_pdf():
    try:
        file = request.files.get('pdf')
        if not file:
            return jsonify({"error": "No file"}), 400

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            file.save(tmp.name)
            path = tmp.name

        try:
            pages = extract_pdf_content(path)
            content = format_content(pages)
        finally:
            os.unlink(path)

        return jsonify({"content": content, "pages": len(pages)})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/ai', methods=['POST'])
def ai():
    try:
        data = request.json

        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_KEY}",
                "Content-Type": "application/json"
            },
            json=data
        )

        return jsonify(resp.json())

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    os.makedirs('static', exist_ok=True)
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
