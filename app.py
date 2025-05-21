from flask import Flask
from facebook_oauth.routes import facebook_oauth_blueprint
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config.from_prefixed_env()

app.register_blueprint(facebook_oauth_blueprint, url_prefix='/facebook')

@app.route('/')
def index():
    return {'status': 'ok'}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
