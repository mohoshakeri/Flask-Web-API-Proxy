import os

import jwt
import requests
from dotenv import load_dotenv
from flask import Flask, request, Response

app = Flask(__name__)

load_dotenv(override=True)
SIGN_KEY = os.getenv("SIGN_KEY")

if SIGN_KEY is None:
    raise ValueError("SIGN KEY Not found")


@app.route(
    "/",
    defaults={"path": ""},
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
)
@app.route("/path:path", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
def proxy(path):
    # Auth
    jwt_token = request.args.get("originJWT")
    try:
        decoded_payload = jwt.decode(jwt_token, SIGN_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        return "JWT Expired", 403
    except jwt.InvalidTokenError:
        return "JWT Error", 403

    # Target
    target_base = request.args.get("targetProxyServer")
    if not target_base:
        return "targetProxyServer not founded", 400

    # Clean Path
    if path:
        target_url = target_base.rstrip("/") + "/" + path
    else:
        target_url = target_base

    # GET Params
    params = dict(request.args)
    params.pop("targetProxyServer", None)
    params.pop("originJWT", None)

    # Headers
    headers = {}
    for key, value in request.headers:
        if key.lower() == "host":
            continue
        headers[key] = value

    # Body
    data = request.get_data()

    try:
        # Request
        resp = requests.request(
            method=request.method,
            url=target_url,
            params=params,
            headers=headers,
            data=data,
            cookies=request.cookies,
            allow_redirects=False,
        )
    except requests.exceptions.RequestException as e:
        return f"Target Server Error -> {str(e)}", 502

    # Response
    response = Response(resp.content, status=resp.status_code)

    # Response Headers
    excluded_headers = ["content-encoding", "transfer-encoding", "connection"]
    for name, value in resp.headers.items():
        if name.lower() not in excluded_headers:
            response.headers[name] = value

    return response


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
