import os
import mailbox
import uuid
import zipfile
from flask import Flask, after_this_request, session, url_for, render_template, request, redirect, flash, send_from_directory
from flask_bootstrap import Bootstrap
from werkzeug.utils import secure_filename
from flask_session import Session

UPLOAD_FOLDER = './uploads'
DOWNLOAD_FOLDER = './downloads'
ALLOWED_EXTENSIONS = set(['mbox'])
OUTPUT_TEMPLATE_FILE = 'output_template.html'
OUTPUT_TEMPLATE_SINGLE_FILE = 'output_template_single.html'

# set the project root directory as the static folder, you can set others.
app = Flask(__name__, static_url_path='')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['SECRET_KEY'] = 'Your_secret_string'
app.config['SESSION_TYPE'] = 'filesystem'
Bootstrap(app)
Session(app)


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
    return render_template('index.html')


@app.route('/results')
def results():
    return render_template('results.html')


@app.route('/upload', methods=['POST'])
def upload():
    # we remove the upload file info from session
    session.pop('uploaded_file_info', None)

    # check if the post request has the file part
    if 'file' not in request.files:
        flash('No file part', 'error')
        return redirect(url_for('index'))

    file = request.files['file']
    # if user does not select file, browser also
    # submit a empty part without filename
    if file.filename == '':
        flash('No selected file', 'error')
        return redirect(url_for('index'))

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        if not os.path.exists(UPLOAD_FOLDER):
            os.makedirs(UPLOAD_FOLDER)

        unique_filename = uuid.uuid4().hex
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename))
        session['uploaded_file_info'] = dict(filename=filename, unique_filename=unique_filename)
        flash('File {} uploaded successfully'.format(filename), 'success')
        return redirect(url_for('index'))
    else:
        flash('Not allowed file', 'error')
        return redirect(url_for('index'))


@app.route('/convert', methods=['POST'])
def convert():
    if 'uploaded_file_info' in session:
        if not os.path.exists(DOWNLOAD_FOLDER):
            os.makedirs(DOWNLOAD_FOLDER)

        filename = session['uploaded_file_info'].get('filename')
        unique_filename = session['uploaded_file_info'].get('unique_filename')
        mbox_file = mailbox.mbox(os.path.join(UPLOAD_FOLDER, unique_filename))
        fname, file_extension = os.path.splitext(filename)
        process_msgs_as_separated_files = request.form.get('process_msgs_as_separated_files')
        generated_filename_to_download = ''
        list_of_files_to_remove = []
        if process_msgs_as_separated_files == 'on' and len(mbox_file) > 1:
            generated_filename_to_download = '{}.zip'.format(fname)
            generated_filename_to_download_unique = uuid.uuid4().hex
            zip = zipfile.ZipFile(os.path.join(DOWNLOAD_FOLDER, generated_filename_to_download_unique), 'w', zipfile.ZIP_DEFLATED)
            msg_counter = 0
            for msg in mbox_file:
                msg_counter = msg_counter + 1
                unique_name_html_file = uuid.uuid4().hex
                app.jinja_env \
                    .get_template(OUTPUT_TEMPLATE_SINGLE_FILE) \
                    .stream(message=msg, title='{} - Message number: {}'.format(fname, '%02d' % (msg_counter,))) \
                    .dump(os.path.join(DOWNLOAD_FOLDER, unique_name_html_file))

                zip.write(os.path.join(DOWNLOAD_FOLDER, unique_name_html_file),
                          arcname='{}_{}.html'.format(fname, '%02d' % (msg_counter,)))

                list_of_files_to_remove.append(os.path.join(DOWNLOAD_FOLDER, unique_name_html_file))

            zip.close()
        else:
            generated_filename_to_download = '{}.html'.format(fname)
            generated_filename_to_download_unique = uuid.uuid4().hex
            app.jinja_env \
                .get_template(OUTPUT_TEMPLATE_FILE) \
                .stream(mbox=mbox_file, title=fname) \
                .dump(os.path.join(DOWNLOAD_FOLDER, generated_filename_to_download_unique))

        list_of_files_to_remove.append(os.path.join(UPLOAD_FOLDER, unique_filename))
        list_of_files_to_remove.append(os.path.join(DOWNLOAD_FOLDER, generated_filename_to_download_unique))
        uploaded_file_info = session['uploaded_file_info']
        uploaded_file_info.update(file_to_download=generated_filename_to_download,
                                file_to_download_unique=generated_filename_to_download_unique,
                                list_of_files_to_remove=list_of_files_to_remove)
        session['uploaded_file_info'] = uploaded_file_info
        return redirect(url_for('results'))
    else:
        flash('You need to upload a mbox file before convert it', 'error')
        return redirect(url_for('index'))


@app.route('/download', methods=['GET'])
def download():
    if 'uploaded_file_info' in session:
        filename_to_download = session['uploaded_file_info'].get('file_to_download')
        filename_to_download_unique = session['uploaded_file_info'].get('file_to_download_unique')
        @after_this_request
        def remove_files(response):
            list_of_files_to_remove = session['uploaded_file_info'].get('list_of_files_to_remove')
            session.pop('uploaded_file_info', None)
            try:
                for file_path_to_remove in list_of_files_to_remove:
                    os.remove(file_path_to_remove)
            except Exception as error:
                app.logger.error('Error removing file {} from the system'.format(file_path_to_remove),
                                 error)
            return response

        return send_from_directory(DOWNLOAD_FOLDER,
                                   filename_to_download_unique,
                                   attachment_filename=filename_to_download,
                                   as_attachment=True)
    else:
        return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
