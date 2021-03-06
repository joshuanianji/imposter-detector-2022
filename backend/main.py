import os
from flask import *
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from speech import *
from lib.utils import recognizeResponseToDict, upload_blob, download_blob
from flask_cors import CORS
import shutil
import pathlib

load_dotenv()


UPLOAD_FOLDER = '/files'
ALLOWED_EXTENSIONS = { 'mp3', 'wav'}

app = Flask(__name__)
CORS(app)

# Google App Engine doesn't allow read/write to the file system, so we have to use the /tmp directory and google cloud storage
app.config['UPLOAD_FOLDER'] = '/tmp/hacked-poopoo-tmp' if os.environ['GAE_ENV'] == 'standard' else app.root_path + UPLOAD_FOLDER 


def allowed_file_type(filename):
	return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/', methods=['GET', 'POST'])
def upload_file():
	# make the temp directory if it doesn't exist
	if os.environ['GAE_ENV'] == 'standard':
		pathlib.Path('/tmp/hacked-poopoo-tmp').mkdir(exist_ok=True)

	if request.method == 'POST':
		# check if the post request has the file part
		print(request.files)
		if 'file' not in request.files:
			print('GET /: No Files!')
			return redirect(request.url)
		else:
			print('GET /: Files!')

		file = request.files['file']
		if file.filename == '':
			print('GET /: No File Name!')
			return make_response(jsonify({'error': 'No ilename'}), 400)
		elif not allowed_file_type(file.filename):
			print('GET /: Not Allowed File Type!', file.filename)
			return make_response(jsonify({'error': 'File type not allowed'}), 400)
		else:
			filename = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(file.filename))
			file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

			name = file.filename

			# Convert file
			originalFilePath = os.path.join(app.config['UPLOAD_FOLDER'], name)
			print(f'GET /processed/{name}: Retrieving filepath {originalFilePath}')
			unBoomifiedFile, res = get_text_from_audio(originalFilePath)

			if (res == 'No speech detected'):
				return make_response(jsonify({'error': 'No speech detected'}), 200)

			if (isinstance(res, str)):
				return make_response(res, 200)

			boomified, triggerword_count, length = add_vine_booms(unBoomifiedFile, res)
			response_data = recognizeResponseToDict(res)
			response_data['count'] = triggerword_count
			response_data['length'] = length

			# upload vine boom to cloud storage
			blob_name = upload_blob('hacked-team-3iq-2.appspot.com', boomified, name)

			# remove content in /tmp directory
			if os.environ['GAE_ENV'] == 'standard':
				shutil.rmtree('/tmp/hacked-poopoo-tmp')

			response_data['file_name'] = blob_name

			return make_response(jsonify(response_data), 200)
	else:
		return'''
		<!doctype html>
		<title>Upload new File</title>
		<h1>Upload new File</h1>
		<form method=post enctype=multipart/form-data>
		<input type=file name=file>
		<input type=submit value=Upload>
		</form>
		'''


# basically a CDN to deliver the files
# sends over the GCB files
@app.route('/cdn/<date>/<name>')
def deliver_file(date, name):
	# make the temp directory if it doesn't exist
	if os.environ['GAE_ENV'] == 'standard':
		pathlib.Path('/tmp/hacked-poopoo-tmp').mkdir(exist_ok=True)

	filePath = os.path.join(app.config['UPLOAD_FOLDER'], name)

	print(f'GET /cdn/{date}/{name}: Downloading from GCB to {filePath}')
	download_blob('hacked-team-3iq-2.appspot.com', f'{date}/{name}', filePath)

	return send_file(filePath, as_attachment=False)


if __name__ == '__main__':
	# This is used when running locally only. When deploying to Google App
	# Engine, a webserver process such as Gunicorn will serve the app. This
	# can be configured by adding an `entrypoint` to app.yaml.
	# Flask's development server will automatically serve static files in
	# the "static" directory. See:
	# http://flask.pocoo.org/docs/1.0/quickstart/#static-files. Once deployed,
	# App Engine itself will serve those files as configured in app.yaml.
	app.run(host='127.0.0.1', port=8080, debug=True)
