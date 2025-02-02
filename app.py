from flask import Flask, render_template, request, jsonify, session
import os
import PyPDF2
import docx
import pandas as pd
import requests

app = Flask(__name__)
app.secret_key = 'supersecretkey'
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

IA_SERVICES = {
    "OpenAI": "https://api.openai.com/v1/completions",
    "HuggingFace": "https://api-inference.huggingface.co/models/facebook/bart-large-cnn",
    "Cohere": "https://api.cohere.ai/v1/generate"
}

def extract_text_from_file(filepath):
    ext = os.path.splitext(filepath)[1].lower()
    text = ""
    
    if ext == ".pdf":
        with open(filepath, "rb") as file:
            reader = PyPDF2.PdfReader(file)
            for page in reader.pages:
                text += page.extract_text() + "\n"
    elif ext == ".docx":
        doc = docx.Document(filepath)
        for para in doc.paragraphs:
            text += para.text + "\n"
    elif ext in [".xls", ".xlsx"]:
        df = pd.read_excel(filepath)
        text = df.to_string()
    return text.strip()

def summarize_text(text, doc_name):
    ia_service = session.get("ia_service")
    api_key = session.get("api_key")
    if not ia_service or not api_key:
        return "IA service not configured."
    
    prompt = f"Faça um resumo dessas informações, extraídas do documento: {doc_name}:\n{text}"
    
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    data = {"prompt": prompt, "max_tokens": 150}
    
    response = requests.post(IA_SERVICES[ia_service], headers=headers, json=data)
    if response.status_code == 200:
        return response.json().get("choices", [{}])[0].get("text", "Erro ao gerar resumo")
    return "Erro ao conectar com a IA"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/configure', methods=['GET', 'POST'])
def configure():
    if request.method == 'POST':
        service = request.form['ia_service']
        api_key = request.form['api_key']
        session['ia_service'] = service
        session['api_key'] = api_key
        return jsonify({"message": "Configuração salva!"})
    return render_template('configure.html', services=IA_SERVICES.keys())

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "Nenhum arquivo enviado"})
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "Nenhum arquivo selecionado"})
    
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    file.save(filepath)
    extracted_text = extract_text_from_file(filepath)
    summary = summarize_text(extracted_text, file.filename)
    
    return jsonify({"summary": summary})

if __name__ == '__main__':
    app.run(debug=True)
