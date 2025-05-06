from typing import Union
from util import OverwritableGlobal, add_global_wrapper
from flask import Flask, request, send_from_directory, make_response
from game import Game
import random

add_global = add_global_wrapper(globals())
app:Union[Flask,OverwritableGlobal] = OverwritableGlobal()
games:Union[dict[int, Game],OverwritableGlobal] = OverwritableGlobal()

def main(): #add app routes
    if type(app) != Flask:
        raise TypeError("Overwrite app with routes.add_global(app=Flask())")
    if type(games) != dict:
        raise TypeError("Overwrite games with routes.add_global(games=dict())")
    @app.route("/")
    def index():
        resp = make_response(open("static/index.html").read())
        if request.cookies.get("nonce") is None:
            resp.set_cookie("nonce", str(random.randint(0, 2**64 - 1)))
        return resp


    @app.route("/src/<path:path>")
    def src(path):
        return send_from_directory("src", path)


    @app.route("/game/<int:id>", methods=["GET"])
    def game_GET(id):
        nonce = request.cookies.get("nonce")
        if id not in games:
            games[id] = Game(owner_nonce=nonce)
        return open("static/game.html").read()


    @app.route("/game/<int:id>", methods=["POST"])
    def game_POST(id):
        nonce = request.cookies.get("nonce")
        name = request.args.get("name")
        if not name:
            return "Missing name", 400
        if id not in games:
            games[id] = Game(owner_nonce=nonce)
        games[id].player_add(nonce, name)
        print(games[id].players)
        return "", 200