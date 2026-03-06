from flask import Flask, redirect, url_for, render_template, request, jsonify
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import os

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="")
CORS(app)

@app.route('/')
def index():
    return app.send_static_file('index.html')

@socketio.on('data')
def handle_data(data):
    emit('update', data, broadcast=True)

if __name__ == '__main__':
    socketio.run(app, debug=True)
