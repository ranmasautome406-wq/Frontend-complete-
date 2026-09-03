import os, sqlite3, json, uuid
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import requests

BASE = Path(__file__).resolve().parent
DB = BASE / 'bhasha.db'
UPLOADS = BASE / 'uploads'
UPLOADS.mkdir(exist_ok=True)

LANGUAGES = {
    'en':'English','hi':'Hindi','mr':'Marathi','gu':'Gujarati','bn':'Bengali','ta':'Tamil','te':'Telugu'
}
DEMO = {
 'photosynthesis': {
   'en':'Photosynthesis is the process by which green plants use sunlight, water and carbon dioxide to make food and release oxygen.',
   'hi':'प्रकाश संश्लेषण वह प्रक्रिया है जिसमें हरे पौधे सूर्य के प्रकाश, पानी और कार्बन डाइऑक्साइड की मदद से अपना भोजन बनाते हैं और ऑक्सीजन छोड़ते हैं।',
   'mr':'प्रकाशसंश्लेषण ही प्रक्रिया आहे ज्यामध्ये हिरव्या वनस्पती सूर्यप्रकाश, पाणी आणि कार्बन डायऑक्साइड वापरून अन्न तयार करतात आणि ऑक्सिजन सोडतात।'
 },
 'gravity': {'en':'Gravity is the force that pulls objects toward Earth.','hi':'गुरुत्वाकर्षण वह बल है जो वस्तुओं को पृथ्वी की ओर खींचता है।','mr':'गुरुत्वाकर्षण हे वस्तूंना पृथ्वीच्या दिशेने ओढणारे बल आहे.'},
 'water cycle': {'en':'The water cycle describes evaporation, condensation, precipitation and collection of water on Earth.','hi':'जल चक्र में वाष्पीकरण, संघनन, वर्षा और जल का संग्रह शामिल है।','mr':'जलचक्रामध्ये बाष्पीभवन, संघनन, पर्जन्य आणि पाण्याचे संकलन यांचा समावेश होतो.'}
}

def db():
    con=sqlite3.connect(DB); con.row_factory=sqlite3.Row; return con

def init_db():
    con=db(); con.executescript('''
    CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT,email TEXT UNIQUE,password TEXT,role TEXT DEFAULT 'student',language TEXT DEFAULT 'hi');
    CREATE TABLE IF NOT EXISTS lessons(id INTEGER PRIMARY KEY AUTOINCREMENT,title TEXT,content TEXT,language TEXT DEFAULT 'en',created_by INTEGER,published INTEGER DEFAULT 1);
    CREATE TABLE IF NOT EXISTS progress(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,lesson_id INTEGER,score INTEGER,weak_topic TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS chats(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,question TEXT,answer TEXT,language TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
    ''')
    if not con.execute('SELECT 1 FROM users LIMIT 1').fetchone():
        con.execute('INSERT INTO users(name,email,password,role,language) VALUES(?,?,?,?,?)',('Demo Student','student@bhasha.setu','Student@123','student','hi'))
        con.execute('INSERT INTO users(name,email,password,role,language) VALUES(?,?,?,?,?)',('Demo Teacher','teacher@bhasha.setu','Teacher@123','teacher','en'))
    if not con.execute('SELECT 1 FROM lessons LIMIT 1').fetchone():
        lessons=[('Photosynthesis','Plants need sunlight, water and carbon dioxide to make food. This process is called photosynthesis.','en'),('Gravity','Gravity is a force that pulls objects toward Earth. It keeps us on the ground and keeps the Moon in orbit.','en'),('Water Cycle','Water changes into vapour, forms clouds, falls as rain, and collects again. This is the water cycle.','en')]
        con.executemany('INSERT INTO lessons(title,content,language) VALUES(?,?,?)',lessons)
    con.commit(); con.close()

app=Flask(__name__, static_folder=str(BASE.parent/'frontend'), static_url_path='')
CORS(app, resources={r'/api/*': {'origins':'*'}}, allow_headers=['Content-Type','Authorization','X-Guest-Id'])

@app.get('/')
def home(): return send_from_directory(app.static_folder,'index.html')
@app.get('/<path:path>')
def frontend(path):
    p=Path(app.static_folder)/path
    if p.exists() and p.is_file(): return send_from_directory(app.static_folder,path)
    return send_from_directory(app.static_folder,'index.html')

@app.get('/api/health')
def health(): return jsonify(status='healthy',project='Bhasha Shiksha Setu',problem_statement='SIH26042',version='2.0')
@app.get('/api/config')
def config():
    return jsonify(ai_enabled=bool(os.getenv('OPENAI_API_KEY')),ai_provider='openai' if os.getenv('OPENAI_API_KEY') else 'demo',languages=LANGUAGES,version='2.0')

def translate_demo(text,target):
    t=text.strip(); low=t.lower()
    for key, vals in DEMO.items():
        if key in low: return vals.get(target, vals['en'])
    # useful phrase fallback
    phrases={'who is the president of india':'भारत के राष्ट्रपति द्रौपदी मुर्मू हैं।','what is bhasha shiksha setu':'Bhasha Shiksha Setu is an AI-powered vernacular education platform.'}
    if low in phrases:
        return phrases[low] if target=='hi' else phrases[low]
    return None

def openai_answer(question, language, context=''):
    key=os.getenv('OPENAI_API_KEY')
    if not key: return None
    model=os.getenv('OPENAI_MODEL','gpt-5.6-luna')
    prompt=f'''You are Bhasha AI Tutor for primary-school learners. Answer accurately, simply and safely. Reply ONLY in {LANGUAGES.get(language,language)}. Keep it concise but educational. If the question is factual and you are uncertain, say so rather than inventing.\nQuestion: {question}\nContext: {context[:5000]}'''
    r=requests.post('https://api.openai.com/v1/responses',headers={'Authorization':f'Bearer {key}','Content-Type':'application/json'},json={'model':model,'input':prompt,'max_output_tokens':500},timeout=35)
    r.raise_for_status(); data=r.json()
    if data.get('output_text'): return data['output_text']
    # defensive extraction
    parts=[]
    for item in data.get('output',[]):
        for c in item.get('content',[]):
            if c.get('type')=='output_text': parts.append(c.get('text',''))
    return ''.join(parts).strip() or None

@app.post('/api/chat')
def chat():
    data=request.get_json(silent=True) or {}; q=str(data.get('message','')).strip(); lang=data.get('language','hi'); uid=data.get('user_id')
    if not q: return jsonify(error='Please enter a question.'),400
    try:
        answer=openai_answer(q,lang,data.get('context',''))
        provider='openai'
    except Exception as e:
        answer=None; provider='demo'
    if not answer:
        answer=translate_demo(q,lang)
    if not answer:
        answer={
          'hi':'मैं अभी Demo Mode में हूँ। इस प्रश्न का विश्वसनीय उत्तर देने के लिए OpenAI API key जोड़ें।',
          'mr':'मी सध्या Demo Mode मध्ये आहे. या प्रश्नाचे विश्वसनीय उत्तर देण्यासाठी OpenAI API key जोडा.',
          'en':'I am currently in Demo Mode. Add an OpenAI API key for reliable answers to general questions.'
        }.get(lang,'I am currently in Demo Mode. Add an OpenAI API key for reliable answers.')
        provider='demo'
    con=db(); con.execute('INSERT INTO chats(user_id,question,answer,language) VALUES(?,?,?,?)',(uid,q,answer,lang)); con.commit(); con.close()
    return jsonify(answer=answer,provider=provider,language=lang)

@app.post('/api/translate')
def translate():
    data=request.get_json(silent=True) or {}; text=str(data.get('text','')).strip(); target=data.get('target_language','hi')
    if not text: return jsonify(error='Text is required'),400
    if target not in LANGUAGES: return jsonify(error='Unsupported language'),400
    key=os.getenv('OPENAI_API_KEY')
    if key:
        try:
            prompt=f'Translate the following educational text into {LANGUAGES[target]}. Preserve meaning. Return only the translation.\n{text}'
            r=requests.post('https://api.openai.com/v1/responses',headers={'Authorization':f'Bearer {key}','Content-Type':'application/json'},json={'model':os.getenv('OPENAI_MODEL','gpt-5.6-luna'),'input':prompt,'max_output_tokens':700},timeout=35); r.raise_for_status(); out=r.json().get('output_text')
            if out: return jsonify(translated_text=out.strip(),provider='openai',target_language=target)
        except Exception: pass
    d=translate_demo(text,target)
    if d: return jsonify(translated_text=d,provider='demo',target_language=target)
    return jsonify(translated_text=text,provider='fallback',target_language=target)

@app.post('/api/explain')
def explain():
    data=request.get_json(silent=True) or {}; text=str(data.get('text','')).strip(); lang=data.get('language','hi')
    if not text: return jsonify(error='Text is required'),400
    if os.getenv('OPENAI_API_KEY'):
        try:
            prompt=f'Explain this educational content for a primary-school child in simple {LANGUAGES.get(lang,lang)}. Use short sentences and one example.\n{text}'
            r=requests.post('https://api.openai.com/v1/responses',headers={'Authorization':f"Bearer {os.getenv('OPENAI_API_KEY')}",'Content-Type':'application/json'},json={'model':os.getenv('OPENAI_MODEL','gpt-5.6-luna'),'input':prompt,'max_output_tokens':600},timeout=35); r.raise_for_status(); out=r.json().get('output_text')
            if out:return jsonify(explanation=out.strip(),provider='openai')
        except Exception: pass
    d=translate_demo(text,lang) or text
    return jsonify(explanation=d,provider='demo')

@app.get('/api/lessons')
def lessons():
    con=db(); rows=con.execute('SELECT * FROM lessons WHERE published=1 ORDER BY id DESC').fetchall(); con.close(); return jsonify(lessons=[dict(r) for r in rows])

@app.post('/api/progress')
def save_progress():
    data=request.get_json(silent=True) or {}; con=db(); con.execute('INSERT INTO progress(user_id,lesson_id,score,weak_topic) VALUES(?,?,?,?)',(data.get('user_id'),data.get('lesson_id'),int(data.get('score',0)),data.get('weak_topic',''))); con.commit(); con.close(); return jsonify(success=True)

@app.post('/api/auth/login')
def login():
    data=request.get_json(silent=True) or {}; con=db(); row=con.execute('SELECT * FROM users WHERE email=? AND password=?',(data.get('email'),data.get('password'))).fetchone(); con.close()
    if not row:return jsonify(error='Invalid email or password'),401
    return jsonify(token='demo-'+str(uuid.uuid4()),user=dict(row))

@app.post('/api/voice/transcribe')
def transcribe(): return jsonify(error='Browser voice recognition is used for this prototype. No server upload is required.'),501

@app.get('/api/stats')
def stats():
    con=db(); total=con.execute('SELECT COUNT(*) c FROM lessons').fetchone()['c']; chats=con.execute('SELECT COUNT(*) c FROM chats').fetchone()['c']; avg=con.execute('SELECT COALESCE(AVG(score),0) a FROM progress').fetchone()['a']; con.close(); return jsonify(total_lessons=total,total_questions=chats,average_score=round(avg))

init_db()

if __name__=='__main__': app.run(host='0.0.0.0',port=int(os.getenv('PORT',5000)),debug=True)
