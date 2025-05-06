from typing import Union
from util import OverwritableGlobal, add_global_wrapper
from flask_socketio import SocketIO, emit, join_room
from flask import request
from game import Game

player_sids: dict[str, str] = {}
add_global = add_global_wrapper(globals())
socketio:Union[SocketIO,OverwritableGlobal] = OverwritableGlobal()
games:Union[dict[int, Game],OverwritableGlobal] = OverwritableGlobal()

def main(): #add app routes
    if type(games) != dict:
        raise TypeError("Overwrite games with routes.add_global(games=dict())")
    if type(socketio) != SocketIO:
        raise TypeError("Overwrite socketio with routes.add_global(socketio=SocketIO())")
    
    def update_players(g):
        g.is_game_over()
        for p in g.players:
            sid = player_sids.get(p["nonce"])
            if sid:
                emit("update", g.json_data(p["nonce"]), room=sid, namespace="/game")

    @socketio.on("join", namespace="/game")
    def on_join(data):
        game_id = data.get("id")
        name = request.args.get("name")
        if game_id is None:
            return
        nonce = request.cookies.get("nonce")
        if game_id not in games:
            games[game_id] = Game(nonce)
        sid = request.sid
        # record this player's sid
        player_sids[nonce] = sid
        # add socket to room for potential group events
        join_room(str(game_id))
        # send personalized state
        personal = games[int(game_id)].json_data(nonce)
        emit("update", personal, room=sid, namespace="/game")


    @socketio.on("chat", namespace="/game")
    def on_chat(data):
        game_id = data.get("id")
        message = data.get("message")
        nonce = request.cookies.get("nonce")
        if game_id is None or message is None:
            return
        g = games[int(game_id)]
        player = None
        for p in g.players:
            if p["nonce"] == nonce:
                player = p
        if player is None:
            return  # spectator
        g.chat_add(message, player["name"])
        # emit per-player
        update_players(g)


    @socketio.on("vote", namespace="/game")
    def on_vote(data):
        game_id = data.get("id")
        voted = data.get("voted")
        nonce = request.cookies.get("nonce")
        if game_id is None or voted is None:
            return
        g = games[int(game_id)]
        # record vote
        g.vote_player(nonce, voted)
        # emit updated state to each player individually
        update_players(g)


    @socketio.on("votekill", namespace="/game")
    def on_vote_kill(data):
        game_id = data.get("id")
        voted = data.get("voted")
        nonce = request.cookies.get("nonce")
        if game_id is None or voted is None:
            return
        g = games[int(game_id)]
        # record vote
        print(g.total_votes, g.total_mafia)
        g.vote_kill_player(nonce, voted)
        # emit updated state to each player individually
        update_players(g)


    @socketio.on("mute", namespace="/game")
    def on_mute(data):
        game_id = data.get("id")
        muted = data.get("muted")
        nonce = request.cookies.get("nonce")
        if game_id is None or muted is None:
            return
        g: Game = games[int(game_id)]

        g.mute_player(nonce, muted)

        update_players(g)


    @socketio.on("protect", namespace="/game")
    def on_protect(data):
        game_id = data.get("id")
        protected = data.get("protected")
        nonce = request.cookies.get("nonce")
        if game_id is None or protected is None:
            return
        g: Game = games[int(game_id)]

        g.protect_player(nonce, protected)

        update_players(g)


    @socketio.on("check", namespace="/game")
    def on_check(data):
        game_id = data.get("id")
        checked = data.get("checked")
        nonce = request.cookies.get("nonce")
        if game_id is None or checked is None:
            return
        g: Game = games[int(game_id)]

        g.check_player(nonce, checked)

        update_players(g)


    @socketio.on("mchat", namespace="/game")
    def on_mchat(data):
        game_id = data.get("id")
        message = data.get("message")
        nonce = request.cookies.get("nonce")
        if game_id is None or message is None:
            return
        g = games[int(game_id)]
        player = None
        for p in g.players:
            if p["nonce"] == nonce:
                player = p
        g.mchat_add(message, player["name"])
        # emit per-player
        update_players(g)


    @socketio.on("disconnect", namespace="/game")
    def on_disconnect():
        sid = request.sid

        # find which nonce was using this sid
        for nonce, stored_sid in list(player_sids.items()):
            if stored_sid == sid:
                # remove from the sid map
                del player_sids[nonce]

                # remove from every game they were in
                for game_id, game in games.items():
                    game.remove_player(nonce)

                    # push updated state to remaining players
                    for p in game.players:
                        target_sid = player_sids.get(p["nonce"])
                        if target_sid:
                            emit(
                                "update",
                                game.json_data(p["nonce"]),
                                room=target_sid,
                                namespace="/game",
                            )

                break