import os, fnmatch, mailbox
from flask import Flask, render_template, request, redirect, flash, send_from_directory
from flask_bootstrap import Bootstrap
from werkzeug.utils import secure_filename

UPLOAD_FOLDER = './uploads'
DOWNLOAD_FOLDER = './downloads'
ALLOWED_EXTENSIONS = set(['mbox'])
OUTPUT_TEMPLATE_FILE = "output_template.html"

# set the project root directory as the static folder, you can set others.
app = Flask(__name__, static_url_path='')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['SECRET_KEY'] = "Your_secret_string"
Bootstrap(app)


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def stream_template(template_name, **context):
    app.update_template_context(context)
    t = app.jinja_env.get_template(template_name)
    rv = t.stream(context)
    rv.enable_buffering(5)
    return rv


@app.route('/')
def index():
    list_of_mbox_files = []
    if os.path.exists(UPLOAD_FOLDER):
        list_of_files = os.listdir(UPLOAD_FOLDER)
        pattern = "*.mbox"
        for entry in list_of_files:
            if fnmatch.fnmatch(entry, pattern):
                list_of_mbox_files.append(entry)

    list_of_html_files = []
    if os.path.exists(DOWNLOAD_FOLDER):
        list_of_files = os.listdir(DOWNLOAD_FOLDER)
        pattern = "*.html"
        for entry in list_of_files:
            if fnmatch.fnmatch(entry, pattern):
                list_of_html_files.append(entry)
                
    return render_template('index.html',
                           list_of_mbox_files=sorted(list_of_mbox_files),
                           list_of_html_files=sorted(list_of_html_files))
    

@app.route('/upload', methods=['POST'])
def upload():
    # check if the post request has the file part
    if 'file' not in request.files:
        flash('No file part', 'error')
        return redirect('/')
        
    file = request.files['file']
    # if user does not select file, browser also
    # submit a empty part without filename
    if file.filename == '':
        flash('No selected file', 'error')
        return redirect('/')
        
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        if not os.path.exists(UPLOAD_FOLDER):
            os.makedirs(UPLOAD_FOLDER)
            
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        flash('File {} uploaded successfully'.format(filename), 'success')
        return redirect('/')
    else:
        flash('Not allowed file', 'error')
        return redirect('/')


@app.route('/mbox_to_html/<string:filename>', methods=['GET'])
def mbox_to_html(filename):
    if not os.path.exists(DOWNLOAD_FOLDER):
        os.makedirs(DOWNLOAD_FOLDER)

    mbox_file = mailbox.mbox(os.path.join(UPLOAD_FOLDER, filename))
    fname, file_extension = os.path.splitext(filename)
    output_filename = fname + ".html"
    app.jinja_env\
        .get_template(OUTPUT_TEMPLATE_FILE)\
        .stream(mbox=mbox_file, title=fname)\
        .dump(os.path.join(DOWNLOAD_FOLDER, output_filename))

    flash('Generated html file: {}'.format(output_filename), 'success')
    return redirect('/')


@app.route('/download/<string:filename>', methods=['GET'])
def download(filename):
    return send_from_directory(DOWNLOAD_FOLDER, filename, as_attachment=True)


if __name__ == '__main__':
   app.run(host='0.0.0.0', port=8080)
