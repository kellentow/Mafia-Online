# Update the Flask app to use Flask-SocketIO for WebSocket support
from flask import Flask, request, send_from_directory, make_response, jsonify
from flask_socketio import SocketIO, emit, join_room
import random

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# Map each player-nonce to their Socket.IO session ID
player_sids: dict[str, str] = {}

class Game:
    def __init__(self, owner_nonce):
        self.owner:str = owner_nonce
        self.players:list[dict] = []
        self.chat:tuple[str,str] = []
        self.mafia_chat:tuple[str,str] = []
        self.current_roles:dict[str,int] = {"mafia": 0, "doctor": 0, "wizard": 0, "muter": 0, "soulmates": 0}
        self.time:int[1,0] = 1 # 1=Day,0=Night
        self.total_votes:int = 0
        self.total_alive:int = 0
        self.total_mafia:int = 0
        self.used_roles:int = 0
        self.wizard_revealed = []

    def player_by_nonce(self,nonce):
        for player in self.players:
            if player["nonce"] == nonce:
                return player
            
    def player_add(self, nonce, username):
        for player in self.players:
            if player["nonce"] == nonce:
                return  # Already joined
        # role assignment logic
        if len(self.players) == 0 or self.current_roles["mafia"] / max(1, len(self.players)) < 0.15:
            role = "mafia"
            self.total_mafia += 1
        elif self.current_roles["doctor"] == 0:
            role = "doctor"
        elif self.current_roles["wizard"] == 0:
            role = "wizard"
        elif self.current_roles["muter"] == 0:
            role = "muter"
        elif self.current_roles["soulmates"] < 1:
            role = "soulmates"
        else:
            role = "innocent"

        self.total_alive += 1
        self.current_roles[role] += 1
        self.players.append({"nonce": nonce, "name": username, "role": role, "alive": True, "votes":0, "voted": False, "muted":False, "protected":False, "used_role":False})

    def mute_player(self, muter, muted):
        muter = self.player_by_nonce(muter)
        muted = self.player_by_nonce(muted)
        if muter["role"] != "muter" or muter["used_role"]:
            return
        muted["muted"] = True
        muter["used_role"] = True
    
    def protect_player(self, protector, protected):
        protector = self.player_by_nonce(protector)
        protected = self.player_by_nonce(protected)
        if protector["role"] != "doctor" or protector["used_role"]:
            return
        protected["protected"] = True
        protector["used_role"] = True

    def check_player(self, checker, checked):
        checker = self.player_by_nonce(checker)
        if checker["role"] != "wizard" or checker["used_role"]:
            return
        checker["used_role"] = True
        self.wizard_revealed.append(checked)

    def vote_kill_player(self, voter, voted):
        voted_player = None
        voter = self.player_by_nonce(voter)
        voted = self.player_by_nonce(voted)
        if voter["voted"] or voter["role"] != "mafia":
            return
        
        voter["voted"] = True
        self.mchat_add(f"{voter['name']} voted for {voted['name']}","SYSTEM")
        voted["votes"] += 1
        self.total_votes += 1
        print(self.total_votes,self.total_mafia)
        self._use_role(voter["nonce"])

    def _kill_player(self,nonce,message):
        killed = self.player_by_nonce(nonce)
        killed["alive"] = False
        self.total_alive -= 1 
        if killed["role"] == "mafia":
            self.total_mafia
        print(killed)
        self.chat_add(message,"SYSTEM")
        if killed['role'] == "soulmates":
            for p2 in self.players:
                if p2 != killed and p2['role'] == "soulmates":
                    p2['alive'] = False
                    self.chat_add(f"{p2['name']} was killed (soulmates with {killed['name']})","SYSTEM")
                    return
    
    def chat_add(self, message, name="SYSTEM"):
        self.chat.append((name,message))

    def mchat_add(self, message, name="SYSTEM"):
        self.mafia_chat.append((name,message))

    def vote_player(self, voter, voted):
        voted_player = None
        voter = self.player_by_nonce(voter)
        voted = self.player_by_nonce(voted)
        if voter["voted"]:
            return
        
        voter["voted"] = True
        self.chat_add(f"{voter['name']} voted","SYSTEM")
        voted["votes"] += 1
        self.total_votes += 1

        print(self.total_votes,self.total_alive)
        if self.total_votes >= self.total_alive:
            self.time = 0 #night
            self.total_votes = 0
            voted_player = {"votes":-1}
            for player in self.players:
                if player["votes"] > voted_player["votes"]:
                    voted_player = player
                player["votes"] = 0
            for p in self.players:
                p["voted"] = False
                p["votes"] = False
                p["used_role"] = False
                p["protected"] = False
                p["muted"] = False
            self._kill_player(voted_player['nonce'],f"{voted_player['name']} was voted")
            self.chat_add("Please wait for all special roles to be used")

    def json_data(self, nonce):
        # build per-player view
        self_player = next((p for p in self.players if p["nonce"] == nonce), None)
        if not self_player:
            return {"error": "not joined"}

        # reveal mafia status only to mafia
        players_json=[]
        for p in self.players:
            player_json = [p["nonce"], p["name"], p["alive"],p["muted"]]
            if self_player["role"] == "mafia" or not self_player["alive"]:
                player_json.append(p["role"] == "mafia")
            elif self_player["role"] == "wizard":
                if p["nonce"] in self.wizard_revealed:
                    player_json.append(p["role"])
            players_json.append(player_json)

        return {
            "players": players_json,
            "chat": self.chat,
            "mafia_chat": self.mafia_chat if self_player["role"] == "mafia" else [],
            "self": self_player,
            "day": self.time == 1
        }

    def is_game_over(self):
        alive = 0
        mafia = 0
        innocent = 0
        for player in self.players:
            if player['alive']:
                alive += 1
                if player['role'] == 'mafia':
                    mafia += 1
                else:
                    innocent += 1
        self.total_alive = alive
        if (innocent <= mafia and len(self.players) >= 3) or self.total_alive == 0 or self.total_mafia == 0:
            random.shuffle(self.players)
            old_players = self.players.copy()
            self.__init__(self.owner)
            for player in old_players:
                self.player_add(player['nonce'],player['name'])
            return True
        return False

    def remove_player(self, nonce):
        # remove the player dict from self.players
        removed = [p for p in self.players if p["nonce"] == nonce]
        self.players = [p for p in self.players if p["nonce"] != nonce]
        # adjust counts if someone was actually removed
        if removed:
            p = removed[0]
            self.total_alive -= 1
            if p["role"] == "mafia":
                self.total_mafia -= 1
            # if you track current_roles, decrement that too:
            self.current_roles[p["role"]] -= 1

    def _use_role(self,nonce):
        user = self.player_by_nonce(nonce)
        user["used_role"] = True
        self.used_roles += 1
        if sum(self.current_roles.values()) == self.used_roles:
            self.time = 1 #day 
            self.total_votes = 0
            voted_player = {"votes":-1}
            for player in self.players:
                if player["votes"] > voted_player["votes"]:
                    voted_player["protected"] = False
                    voted_player = player
            if voted_player["protected"]:
                for p in self.players:
                    p["voted"] = False
                    p["votes"] = 0
                    p["used_role"] = False
                    p["protected"] = False
                    p["muted"] = False
                self.chat_add(f"The mafia tried to kill {voted_player['name']} but the doctor saved them","SYSTEM")
                return
            for p in self.players:
                p["voted"] = False
                p["votes"] = False
                p["used_role"] = False
                p["protected"] = False
                p["muted"] = False
            self._kill_player(voted_player['nonce'],f"{voted_player['name']} was killed")

games: dict[int, Game] = {}

@app.route("/")
def index():
    resp = make_response(open("static/index.html").read())
    if request.cookies.get('nonce') is None:
        resp.set_cookie('nonce', str(random.randint(0, 2**64 - 1)))
    return resp

@app.route("/src/<path:path>")
def src(path):
    return send_from_directory('src', path)

@app.route("/game/<int:id>", methods=["GET"])
def game_GET(id):
    nonce = request.cookies.get('nonce')
    if id not in games:
        games[id] = Game(owner_nonce=nonce)
    return open("static/game.html").read()

@app.route("/game/<int:id>", methods=["POST"])
def game_POST(id):
    nonce = request.cookies.get('nonce')
    name = request.args.get('name')
    if not name:
        return "Missing name", 400
    if id not in games:
        games[id] = Game(owner_nonce=nonce)
    games[id].player_add(nonce, name)
    print(games[id].players)
    return "", 200

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
    nonce = request.cookies.get('nonce')
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
    nonce = request.cookies.get('nonce')
    if game_id is None or message is None:
        return
    g = games[int(game_id)]
    player = None
    for p in g.players:
        if p["nonce"] == nonce:
            player = p
    if player is None:
        return #spectator
    g.chat_add(message,player["name"])
    # emit per-player
    update_players(g)

@socketio.on("vote", namespace="/game")
def on_vote(data):
    game_id = data.get("id")
    voted = data.get("voted")
    nonce = request.cookies.get('nonce')
    if game_id is None or voted is None:
        return
    g = games[int(game_id)]
    # record vote
    g.vote_player(nonce,voted)
    # emit updated state to each player individually
    update_players(g)

@socketio.on("votekill", namespace="/game")
def on_vote_kill(data):
    game_id = data.get("id")
    voted = data.get("voted")
    nonce = request.cookies.get('nonce')
    if game_id is None or voted is None:
        return
    g = games[int(game_id)]
    # record vote
    print(g.total_votes,g.total_mafia)
    g.vote_kill_player(nonce,voted)
    # emit updated state to each player individually
    update_players(g)

@socketio.on("mute", namespace="/game")
def on_mute(data):
    game_id = data.get("id")
    muted = data.get("muted")
    nonce = request.cookies.get('nonce')
    if game_id is None or muted is None:
        return
    g:Game = games[int(game_id)]

    g.mute_player(nonce,muted)

    update_players(g)

@socketio.on("protect", namespace="/game")
def on_protect(data):
    game_id = data.get("id")
    protected = data.get("protected")
    nonce = request.cookies.get('nonce')
    if game_id is None or protected is None:
        return
    g:Game = games[int(game_id)]

    g.protect_player(nonce,protected)

    update_players(g)

@socketio.on("check", namespace="/game")
def on_check(data):
    game_id = data.get("id")
    checked = data.get("checked")
    nonce = request.cookies.get('nonce')
    if game_id is None or checked is None:
        return
    g:Game = games[int(game_id)]

    g.check_player(nonce,checked)

    update_players(g)

@socketio.on("mchat", namespace="/game")
def on_mchat(data):
    game_id = data.get("id")
    message = data.get("message")
    nonce = request.cookies.get('nonce')
    if game_id is None or message is None:
        return
    g = games[int(game_id)]
    player = None
    for p in g.players:
        if p["nonce"] == nonce:
            player = p
    g.mchat_add(message,player["name"])
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
                        emit("update", game.json_data(p["nonce"]),
                             room=target_sid, namespace="/game")

            break

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000)
