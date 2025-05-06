from flask import Flask
from flask_socketio import SocketIO
from game import Game

games: dict[int, Game] = {}
app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

import routes #init http requests
routes.add_global(games=games,app=app)
routes.main()

import websocket_routes #init web sockets
websocket_routes.add_global(games=games,socketio=socketio)
websocket_routes.main()

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000)
