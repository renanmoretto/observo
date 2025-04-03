import observo as observo
from flask import Flask
from werkzeug.middleware.dispatcher import DispatcherMiddleware

app = Flask(__name__)

observo.watch_logs()
observo_app = observo.get_wsgi_app()

app.wsgi_app = DispatcherMiddleware(app.wsgi_app, {'/observo': observo_app})


@app.route('/')
def index():
    return 'Hello, World!'


if __name__ == '__main__':
    app.run(debug=True)
