from flask import Flask, request


def create_app() -> Flask:
    app = Flask(__name__)
    from .api import api
    app.register_blueprint(api)

    # CORS: card runs in browser (HA origin), API on different port → browser blocks without this
    @app.after_request
    def _cors_headers(response):
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        return response

    @app.before_request
    def _cors_preflight():
        if request.method == "OPTIONS":
            return "", 204

    return app
