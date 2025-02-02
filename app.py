import os
import io
import requests
from flask import Flask, render_template_string, request, redirect, session
from pyresparser import ResumeParser
from docx import Document
from PyPDF2 import PdfReader
from openpyxl import load_workbook

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Configuração inicial
AI_SERVICES = {
    'OpenAI': {
        'guide': [
            '1. Acesse https://platform.openai.com/ e faça login',
            '2. Clique em "API Keys" no menu lateral',
            '3. Clique em "Create new secret key"',
            '4. Nomeie a chave (ex: MeuSistema) e clique em "Create"',
            '5. Copie a chave gerada e cole abaixo'
        ],
        'api_url': 'https://api.openai.com/v1/chat/completions'
    },
    'HuggingFace': {
        'guide': [
            '1. Acesse https://huggingface.co/ e faça login',
            '2. Clique em seu ícone de perfil no canto superior direito',
            '3. Selecione "Settings"',
            '4. Navegue até "Access Tokens" no menu lateral',
            '5. Gere um novo token ou copie um existente',
            '6. Cole o token abaixo'
        ],
        'api_url': 'https://api-inference.huggingface.co/models/google/flan-t5-xxl'
    },
    'Cohere': {
        'guide': [
            '1. Acesse https://dashboard.cohere.ai/ e faça login',
            '2. Navegue até a seção "API Keys"',
            '3. Clique em "Generate API Key"',
            '4. Nomeie a chave (ex: MeuSistema) e confirme',
            '5. Copie a chave gerada e cole abaixo'
        ],
        'api_url': 'https://api.cohere.ai/v1/generate'
    }
}

HTML_BASE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Sistema de Resumo de Documentos</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        .container { max-width: 800px; margin: 50px auto; }
        .card { margin-top: 20px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); }
        .guide-step { margin: 15px 0; padding: 10px; background: #f8f9fa; border-radius: 5px; }
    </style>
</head>
<body>
    <div class="container">
        <h2 class="text-center mb-4">📄 Sistema de Resumo de Documentos</h2>
        <div class="card p-4">
            <a href="/" class="btn btn-secondary mb-3">🏠 Voltar</a>
            {% block content %}{% endblock %}
        </div>
    </div>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
'''

def extract_text(file):
    filename = file.filename
    content = file.read()
    
    if filename.endswith('.pdf'):
        pdf = PdfReader(io.BytesIO(content))
        return '\n'.join([page.extract_text() for page in pdf.pages])
    
    elif filename.endswith('.docx'):
        doc = Document(io.BytesIO(content))
        return '\n'.join([para.text for para in doc.paragraphs])
    
    elif filename.endswith(('.xlsx', '.xls')):
        wb = load_workbook(io.BytesIO(content))
        text = []
        for sheet in wb:
            for row in sheet.iter_rows(values_only=True):
                text.append(' '.join(map(str, row)))
        return '\n'.join(text)
    
    return ''

def generate_summary(text, filename):
    service = session.get('ai_service')
    api_key = session.get('api_key')
    
    prompt = f"Faça um resumo dessas informações, listadas abaixo, extraídas do documento: {filename}\n\n{text}"
    
    try:
        if service == 'OpenAI':
            headers = {'Authorization': f'Bearer {api_key}'}
            data = {
                "model": "gpt-3.5-turbo",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7
            }
            response = requests.post(AI_SERVICES[service]['api_url'], json=data, headers=headers)
            return response.json()['choices'][0]['message']['content']
        
        elif service == 'HuggingFace':
            headers = {'Authorization': f'Bearer {api_key}'}
            data = {"inputs": prompt}
            response = requests.post(AI_SERVICES[service]['api_url'], json=data, headers=headers)
            return response.json()[0]['generated_text']
        
        elif service == 'Cohere':
            headers = {'Authorization': f'Bearer {api_key}'}
            data = {
                "prompt": prompt,
                "max_tokens": 500,
                "temperature": 0.7
            }
            response = requests.post(AI_SERVICES[service]['api_url'], json=data, headers=headers)
            return response.json()['generations'][0]['text']
    
    except Exception as e:
        return f"Erro ao gerar resumo: {str(e)}"

@app.route('/')
def home():
    return render_template_string(HTML_BASE, content='''
        <div class="text-center">
            <h4 class="mb-4">Selecione uma opção:</h4>
            <a href="/settings" class="btn btn-primary btn-lg mb-2">⚙️ Configurações do Sistema</a><br>
            <a href="/process" class="btn btn-success btn-lg">📄 Usar o Sistema</a>
        </div>
    ''')

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if request.method == 'POST':
        session['ai_service'] = request.form.get('ai_service')
        return redirect(f'/configure/{request.form.get("ai_service")}')
    
    return render_template_string(HTML_BASE, content='''
        <h4 class="mb-4">🔧 Configurações do Sistema</h4>
        <form method="POST">
            <div class="mb-3">
                <label class="form-label">Selecione o serviço de IA:</label>
                <select name="ai_service" class="form-select" required>
                    <option value="">-- Selecione --</option>
                    <option value="OpenAI">OpenAI (GPT-3.5)</option>
                    <option value="HuggingFace">HuggingFace</option>
                    <option value="Cohere">Cohere</option>
                </select>
            </div>
            <button type="submit" class="btn btn-primary">Avançar</button>
        </form>
    ''')

@app.route('/configure/<service>', methods=['GET', 'POST'])
def configure(service):
    if request.method == 'POST':
        session['api_key'] = request.form.get('api_key')
        return redirect('/')
    
    guide = AI_SERVICES.get(service, {}).get('guide', [])
    return render_template_string(HTML_BASE, content=f'''
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
    ''')

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
        
        return render_template_string(HTML_BASE, content=f'''
            <h4 class="mb-4">📝 Resumo Gerado</h4>
            <div class="alert alert-success">
                <h5>{file.filename}</h5>
                <pre style="white-space: pre-wrap;">{summary}</pre>
            </div>
            <a href="/process" class="btn btn-primary">Nova Análise</a>
        ''')
    
    return render_template_string(HTML_BASE, content='''
        <h4 class="mb-4">📤 Processar Documento</h4>
        <form method="POST" enctype="multipart/form-data">
            <div class="mb-3">
                <label class="form-label">Selecione o arquivo (PDF, DOCX, XLSX):</label>
                <input type="file" name="file" class="form-control" accept=".pdf,.docx,.xlsx" required>
            </div>
            <button type="submit" class="btn btn-primary">Enviar e Processar</button>
        </form>
    ''')

if __name__ == '__main__':
    app.run(debug=True)

