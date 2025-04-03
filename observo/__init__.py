import os
import json
from pathlib import Path
from functools import wraps
from typing import TypedDict
import datetime

from flask import (
    Flask,
    request,
    render_template,
    redirect,
    url_for,
    session,
    flash,
    send_file,
    abort,
)


_OBSERVO_DIR = Path(__file__).parent.parent
_TEMPLATES_DIR = _OBSERVO_DIR / 'templates'
auth_username = os.getenv('OBSERVO_USERNAME')
auth_password = os.getenv('OBSERVO_PASSWORD')


app = Flask(__name__, template_folder=str(_TEMPLATES_DIR))
app.secret_key = os.getenv('OBSERVO_SECRET_KEY', os.urandom(24))


class WatchedFile:
    def __init__(self, path: Path, name: str | None = None):
        self.name = name or path.name
        self.path = path

    @property
    def size(self) -> str:
        return _get_file_size(self.path)

    @property
    def last_modified(self) -> str:
        return _get_last_modified(self.path)


class WatchedDirectory:
    def __init__(self, title: str, path: Path):
        self.title = title
        self.path = path

    def list_files(self) -> list[WatchedFile]:
        return [WatchedFile(file) for file in self.path.iterdir()]

    def to_dict(self) -> dict:
        return {
            'title': self.title,
            'path': self.path,
            'files': self.list_files(),
        }


watched_dirs: list[WatchedDirectory] = []
watched_files: list[WatchedFile] = []


# funcs


def _get_file_size(file_path):
    size_bytes = os.path.getsize(file_path)
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0 or unit == 'GB':
            return f'{size_bytes:.2f} {unit}'
        size_bytes /= 1024.0


def _get_last_modified(file_path):
    timestamp = os.path.getmtime(file_path)
    return datetime.datetime.fromtimestamp(timestamp).strftime(
        '%Y-%m-%d %H:%M:%S'
    )


# flask stuff


def _login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if auth_username is None and auth_password is None:
            return f(*args, **kwargs)
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)

    return decorated_function


@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if auth_password is None or (
            (auth_username is None or username == auth_username)
            and password == auth_password
        ):
            session['logged_in'] = True
            return redirect(url_for('index'))
        else:
            error = 'Invalid credentials'

    return render_template('login.html', error=error)


@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))


@app.route('/')
@_login_required
def index():
    is_logged_in = 'logged_in' in session
    return render_template(
        'index.html',
        watched_dirs=[d.to_dict() for d in watched_dirs],
        watched_files=[f for f in watched_files],
        is_logged_in=is_logged_in,
    )


@app.route('/file/<path:file_path>')
@_login_required
def file_detail(file_path: str):
    print(file_path)
    file_path = Path(file_path)
    if not file_path.exists():
        abort(404)

    download = request.args.get('download', 'false').lower() == 'true'

    if download:
        return send_file(
            str(file_path.absolute()),
            as_attachment=True,
            download_name=file_path.name,
        )

    try:
        file_content = file_path.read_text()
        return render_template(
            'file_detail.html',
            file_path=file_path,
            file_content=file_content,
        )
    except UnicodeDecodeError:
        flash('Cannot display binary file content')
        return redirect(url_for('index'))


@app.route('/file/<file_path>/delete', methods=['POST'])
@_login_required
def delete_file(file_path):
    file_path = Path(file_path)
    if not file_path.exists():
        abort(404)

    try:
        file_path.unlink()
        flash(f'File {file_path.name} deleted successfully')
    except Exception as e:
        flash(f'Error deleting log file: {str(e)}')

    return redirect(url_for('index'))


@app.route('/file/<file_path>/clear', methods=['POST'])
@_login_required
def clear_file(file_path):
    file_path = Path(file_path)
    if not file_path.exists():
        abort(404)

    try:
        file_path.write_text('')
        flash(f'File {file_path.name} cleared successfully')
    except Exception as e:
        flash(f'Error clearing file: {str(e)}')

    return redirect(url_for('index'))


def watch(title: str, path: str | Path):
    global watched_dirs
    watched_dirs.append(WatchedDirectory(title=title, path=Path(path)))


def watch_logs(logs_dir: str | Path = 'logs'):
    watch(title='logs', path=logs_dir)


def watch_file(path: str | Path, name: str | None = None):
    global watched_files
    watched_files.append(WatchedFile(path=path, name=name))


def get_wsgi_app():
    return app


def get_asgi_app():
    from asgiref.wsgi import WsgiToAsgi

    return WsgiToAsgi(app)


def run(host: str = '0.0.0.0', port: int = 8080, debug: bool = False, **kwargs):
    app.run(host=host, port=port, debug=debug, **kwargs)
