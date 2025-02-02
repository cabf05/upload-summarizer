import os
os.environ['NLTK_DATA'] = '/opt/render/nltk_data'

import nltk
nltk.download('stopwords', quiet=True)
nltk.download('punkt', quiet=True)
nltk.download('wordnet', quiet=True)
nltk.download('omw-1.4', quiet=True)

import io
import requests
import pytesseract
from flask import Flask, request, redirect, session
from docx import Document
from PyPDF2 import PdfReader
from openpyxl import load_workbook
from PIL import Image
import fitz  # PyMuPDF

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Configurações dos serviços de IA
AI_SERVICES = {
    'OpenAI': {
        'guide': [
            '1. Acesse https://platform.openai.com/ e faça login',
            '2. Clique em "API Keys" no menu lateral',
            '3. Clique em "Create new secret key"',
            '4. Nomeie a chave e clique em "Create"',
            '5. Copie a chave gerada e cole abaixo'
        ],
        'api_url': 'https://api.openai.com/v1/chat/completions'
    },
    'HuggingFace': {
        'guide': [
            '1. Acesse https://huggingface.co/ e faça login',
            '2. Clique em seu ícone de perfil > Settings > Access Tokens',
            '3. Gere um token com permissão "Read"',
            '4. Escolha um modelo na lista abaixo',
            '5. Cole o token e selecione o modelo desejado'
        ],
        'api_url': 'https://api-inference.huggingface.co/models/'
    }
}

# Modelos para Hugging Face
MODELOS_HF = [
    ('unicamp-dl/ptt5-base-portuguese-vocab', 'PTT5 (Português)'),
    ('google/mt5-base', 'mT5 (Multilíngue)'),
    ('microsoft/layoutlmv3-base', 'LayoutLMv3 (Documentos)')
]

HTML_BASE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Sistema de Resumo de Documentos</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        .container {{ max-width: 800px; margin: 50px auto; }}
        .card {{ margin-top: 20px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); }}
        .guide-step {{ margin: 15px 0; padding: 10px; background: #f8f9fa; border-radius: 5px; }}
        pre {{ white-space: pre-wrap; background: #f8f9fa; padding: 15px; border-radius: 5px; }}
        .alert {{ margin-top: 20px; }}
    </style>
</head>
<body>
    <div class="container">
        <h2 class="text-center mb-4">📄 Sistema de Resumo de Documentos</h2>
        <div class="card p-4">
            <a href="/" class="btn btn-secondary mb-3">🏠 Voltar</a>
            {}
        </div>
    </div>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
'''

def extract_text_with_ocr(pdf_bytes):
    """Extrai texto de PDFs digitalizados usando OCR"""
    try:
        text = []
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        
        for page in doc:
            pix = page.get_pixmap(dpi=300)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            text.append(pytesseract.image_to_string(img, lang='por+eng'))
        
        return '\n'.join(text)
    except Exception as e:
        return f"Erro no OCR: {str(e)}"

def extract_text(file):
    """Extrai texto de diferentes formatos de arquivo"""
    filename = file.filename
    content = file.read()
    
    try:
        # Extração para PDF
        if filename.endswith('.pdf'):
            # Tenta extração textual
            try:
                pdf = PdfReader(io.BytesIO(content))
                text = '\n'.join([page.extract_text() for page in pdf.pages])
                if text.strip():
                    return text
            except:
                pass
            
            # Fallback para OCR
            return extract_text_with_ocr(content)
        
        # Extração para DOCX
        elif filename.endswith('.docx'):
            doc = Document(io.BytesIO(content))
            return '\n'.join([para.text for para in doc.paragraphs])
        
        # Extração para Excel
        elif filename.endswith(('.xlsx', '.xls')):
            wb = load_workbook(io.BytesIO(content))
            text = []
            for sheet in wb:
                for row in sheet.iter_rows(values_only=True):
                    text.append(' '.join(map(str, row)))
            return '\n'.join(text)
            
    except Exception as e:
        print(f"Erro na extração: {str(e)}")
    
    return "Não foi possível extrair o texto do documento"

def generate_summary(text, filename):
    """Gera o resumo usando o serviço de IA configurado"""
    service = session.get('ai_service')
    api_key = session.get('api_key')
    
    prompt = f"Resuma este documento de forma clara e detalhada em português brasileiro:\n\n{text}"
    
    try:
        if service == 'OpenAI':
            headers = {'Authorization': f'Bearer {api_key}'}
            data = {
                "model": "gpt-3.5-turbo",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7
            }
            response = requests.post(
                AI_SERVICES[service]['api_url'],
                json=data,
                headers=headers,
                timeout=60
            )
            return response.json()['choices'][0]['message']['content']
        
        elif service == 'HuggingFace':
            headers = {'Authorization': f'Bearer {api_key}'}
            modelo = session.get('hf_model', 'unicamp-dl/ptt5-base-portuguese-vocab')
            
            data = {
                "inputs": prompt,
                "parameters": {
                    "max_length": 1000,
                    "temperature": 0.7
                }
            }
            
            response = requests.post(
                f"{AI_SERVICES[service]['api_url']}{modelo}",
                json=data,
                headers=headers,
                timeout=120
            )
            
            if response.status_code == 503:
                return "⚠️ Modelo está carregando. Tente novamente em 30 segundos."
                
            return response.json()[0]['generated_text']
    
    except Exception as e:
        return f"Erro ao gerar resumo: {str(e)}"

# Rotas da aplicação
@app.route('/')
def home():
    content = '''
    <div class="text-center">
        <h4 class="mb-4">Selecione uma opção:</h4>
        <a href="/settings" class="btn btn-primary btn-lg mb-2">⚙️ Configurações</a><br>
        <a href="/process" class="btn btn-success btn-lg">📄 Processar Documento</a>
    </div>
    '''
    return HTML_BASE.format(content)

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if request.method == 'POST':
        session['ai_service'] = request.form.get('ai_service')
        return redirect(f'/configure/{request.form.get("ai_service")}')
    
    content = '''
    <h4 class="mb-4">🔧 Configurações do Sistema</h4>
    <form method="POST">
        <div class="mb-3">
            <label class="form-label">Selecione o serviço de IA:</label>
            <select name="ai_service" class="form-select" required>
                <option value="">-- Selecione --</option>
                <option value="OpenAI">OpenAI (GPT-3.5)</option>
                <option value="HuggingFace">HuggingFace</option>
            </select>
        </div>
        <button type="submit" class="btn btn-primary">Avançar</button>
    </form>
    '''
    return HTML_BASE.format(content)

@app.route('/configure/<service>', methods=['GET', 'POST'])
def configure(service):
    if request.method == 'POST':
        session['api_key'] = request.form.get('api_key')
        if service == 'HuggingFace':
            session['hf_model'] = request.form.get('hf_model')
        return redirect('/')
    
    if service == 'HuggingFace':
        content = f'''
        <h4 class="mb-4">🔧 Configurar HuggingFace</h4>
        <form method="POST">
            <div class="mb-3">
                <label class="form-label">Token de Acesso:</label>
                <input type="text" name="api_key" class="form-control" required>
            </div>
            <div class="mb-3">
                <label class="form-label">Selecione o Modelo:</label>
                <select name="hf_model" class="form-select" required>
                    {"".join(f'<option value="{m[0]}">{m[1]}</option>' for m in MODELOS_HF)}
                </select>
            </div>
            <button type="submit" class="btn btn-primary">Salvar</button>
        </form>
        '''
    else:
        guide = AI_SERVICES[service]['guide']
        content = f'''
        <h4 class="mb-4">🔑 Configurar {service}</h4>
        <div class="mb-4">
            <h5>Siga estas instruções:</h5>
            {'<hr>'.join(f'<div class="guide-step">{step}</div>' for step in guide)}
        </div>
        <form method="POST">
            <div class="mb-3">
                <label class="form-label">Cole sua chave API aqui:</label>
                <input type="text" name="api_key" class="form-control" required>
            </div>
            <button type="submit" class="btn btn-primary">Salvar</button>
        </form>
        '''
    
    return HTML_BASE.format(content)

@app.route('/process', methods=['GET', 'POST'])
def process():
    if 'api_key' not in session:
        return redirect('/settings')
    
    if request.method == 'POST':
        if 'file' not in request.files:
            return redirect(request.url)
        
        file = request.files['file']
        if file.filename == '':
            return redirect(request.url)
        
        text = extract_text(file)
        summary = generate_summary(text, file.filename)
        
        content = f'''
        <h4 class="mb-4">📝 Resumo Gerado</h4>
        <div class="alert alert-info">
            <h5>Texto Extraído:</h5>
            <pre>{text[:2000]}...</pre>
        </div>
        <div class="alert alert-success">
            <h5>Resumo:</h5>
            <pre>{summary}</pre>
        </div>
        <a href="/process" class="btn btn-primary">Nova Análise</a>
        '''
        return HTML_BASE.format(content)
    
    content = '''
    <h4 class="mb-4">📤 Processar Documento</h4>
    <form method="POST" enctype="multipart/form-data">
        <div class="mb-3">
            <label class="form-label">Selecione o arquivo (PDF, DOCX, XLSX):</label>
            <input type="file" name="file" class="form-control" accept=".pdf,.docx,.xlsx" required>
        </div>
        <button type="submit" class="btn btn-primary">Enviar e Processar</button>
    </form>
    '''
    return HTML_BASE.format(content)

if __name__ == '__main__':
    app.run(debug=True)
