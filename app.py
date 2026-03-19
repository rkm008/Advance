from flask import Flask, render_template, request, redirect, send_from_directory, url_for, session
import os
import subprocess
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from PIL import Image, ImageOps
import mimetypes

app = Flask(__name__)
app.secret_key = "super_secret_key_change_this" 

# Folder Configuration
UPLOAD_FOLDER = 'static/uploads'
CALC2_FOLDER = 'Calculus 2'
THUMB_FOLDER = 'static/uploads/thumbs'
CONFIG_FILE = 'admin_config.txt'
SCAN_FOLDERS = [UPLOAD_FOLDER, CALC2_FOLDER]

# Auto-create necessary directories
for folder in [UPLOAD_FOLDER, CALC2_FOLDER, THUMB_FOLDER]:
    os.makedirs(folder, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['THUMB_FOLDER'] = THUMB_FOLDER

# Default Admin Setup (admin / password123)
if not os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, 'w') as f:
        f.write(f"admin123,{generate_password_hash('its~your-boss')}")

def load_config():
    with open(CONFIG_FILE, 'r') as f:
        return f.read().split(',')

mimetypes.add_type("video/mp4", ".mp4")
mimetypes.add_type("video/quicktime", ".mov")

def get_file_type(filename):
    mime_type, _ = mimetypes.guess_type(filename)
    if mime_type and mime_type.startswith('image/'): return 'image'
    if mime_type and mime_type.startswith('video/'): return 'video'
    return 'other'

def generate_video_thumbnail(video_path, thumb_path):
    try:
        thumb_path = os.path.splitext(thumb_path)[0] + ".jpg"
        subprocess.run(['ffmpeg', '-y', '-ss', '00:00:01', '-i', video_path, '-vframes', '1', '-vf', 'scale=400:-1', thumb_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except: return False

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        for file_storage in request.files.getlist('images'):
            if file_storage.filename:
                filename = secure_filename(file_storage.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                if not os.path.exists(filepath):
                    file_storage.save(filepath)
                    file_type = get_file_type(filename)
                    if file_type == 'image':
                        try:
                            img = Image.open(filepath)
                            img = ImageOps.exif_transpose(img)
                            if img.mode in ('RGBA', 'P', 'CMYK'): img = img.convert('RGB')
                            img.thumbnail((400, 300))
                            img.save(os.path.join(THUMB_FOLDER, filename))
                        except: pass
                    elif file_type == 'video':
                        generate_video_thumbnail(filepath, os.path.join(THUMB_FOLDER, filename))
        return redirect(url_for('index'))

    media_items = []
    for folder in SCAN_FOLDERS:
        if not os.path.exists(folder): continue
        for media_name in os.listdir(folder):
            full_path = os.path.join(folder, media_name)
            if not os.path.isfile(full_path): continue
            file_type = get_file_type(media_name)
            thumb_name = media_name if file_type == 'image' else os.path.splitext(media_name)[0] + ".jpg"
            thumb_path = os.path.join(THUMB_FOLDER, thumb_name)
            cache_buster = int(os.path.getmtime(thumb_path) if os.path.exists(thumb_path) else os.path.getmtime(full_path))
            media_items.append({'name': media_name, 'folder': folder, 'type': file_type, 'thumb': thumb_name, 'cache_buster': cache_buster})
    return render_template('index.html', media_items=media_items, is_admin=session.get('admin'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username, hashed_pw = load_config()
        if request.form['username'] == username and check_password_hash(hashed_pw, request.form['password']):
            session['admin'] = True
            return redirect(url_for('index'))
        error = "Invalid Credentials"
    return render_template('login.html', error=error)

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if not session.get('admin'): return redirect(url_for('login'))
    message = None
    if request.method == 'POST':
        new_user = request.form['username']
        new_pass = request.form['password']
        if new_user and new_pass:
            with open(CONFIG_FILE, 'w') as f:
                f.write(f"{new_user},{generate_password_hash(new_pass)}")
            message = "Admin credentials updated!"
    return render_template('settings.html', message=message)

@app.route('/logout')
def logout():
    session.pop('admin', None)
    return redirect(url_for('index'))

@app.route('/delete/<path:folder>/<filename>')
def delete_file(folder, filename):
    if not session.get('admin'): return redirect(url_for('login'))
    file_path = os.path.join(folder, filename)
    file_type = get_file_type(filename)
    thumb_name = filename if file_type == 'image' else os.path.splitext(filename)[0] + ".jpg"
    thumb_path = os.path.join(THUMB_FOLDER, thumb_name)
    if os.path.exists(file_path): os.remove(file_path)
    if os.path.exists(thumb_path): os.remove(thumb_path)
    return redirect(url_for('index'))

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    for folder in SCAN_FOLDERS:
        path = os.path.join(folder, filename)
        if os.path.exists(path): return send_from_directory(folder, filename)
    return "File not found", 404

@app.route('/thumbs/<filename>')
def thumb_file(filename):
    return send_from_directory(app.config['THUMB_FOLDER'], filename)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
