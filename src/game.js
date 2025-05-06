document.addEventListener("DOMContentLoaded", () => {
  const gameId        = window.location.pathname.split("/")[2];
  const mafiaSection  = document.getElementById("mafia-chat");
  const publicSection = document.getElementById("public-chat");
  const chatBox       = document.getElementById("chat-box");
  const mafiaBox      = document.getElementById("mafia-box");
  const playersList   = document.getElementById("players");
  const messageInput  = document.getElementById("message");
  const sendBtn       = document.getElementById("send");

  let selfRole = "innocent";
  let day      = false;
  let selfAlive= true;

  const socket = io("/game");

  socket.on("connect", () => {
    socket.emit("join", { id: gameId });
  });

  sendBtn.addEventListener("click", sendMessage);
  messageInput.addEventListener("keydown", e => {
    if (e.key === "Enter") sendMessage();
  });

  function sendMessage() {
    const msg = messageInput.value.trim();
    if (!msg) return;
    const evt = (selfRole === "mafia" && !day) ? "mchat" : "chat";
    socket.emit(evt, { id: gameId, message: msg });
    messageInput.value = "";
  }

  function vote(targetNonce) {
    const evt = day ? "vote" : "votekill";
    socket.emit(evt, { id: gameId, voted: targetNonce });
  }

  function mute(targetNonce) {
    socket.emit("mute", { id: gameId, muted: targetNonce });
  }
  function protect(targetNonce) {
    socket.emit("protect", { id: gameId, protected: targetNonce });
  }
  function checkRole(targetNonce) {
    socket.emit("check", { id: gameId, checked: targetNonce });
  }

  socket.on("update", updateUI);

  function updateUI(data) {
    console.log(data)
    day       = data.day;
    selfAlive = data.self.alive;
    selfRole  = data.self.role;
    selfVoted  = data.self.voted;

    // render players
    playersList.innerHTML = "";
    data.players.forEach(p => {
      // p = [nonce, name, alive, muted, (maybe) isMafia or role]
      const [nonce, name, alive, muted, roleFlag] = p;
      const li = document.createElement("li");
      li.textContent = name;

      // style dead
      if (!alive) li.classList.add("dead");
      // style muted
      if (muted) li.style.opacity = "0.5";
      // style mafia for mafia
      if (selfRole === "mafia" && roleFlag === true && alive) {
        li.style.color = "red";
      }

      // always show action buttons if alive
      if (alive && !selfVoted && selfAlive) {
        // voting
        if (day) {
          const btn = document.createElement("button");
          btn.textContent = "Vote";
          btn.onclick = () => vote(nonce);
          li.appendChild(btn);
        }
        // night actions
        if (!day) {
          if (selfRole === "mafia") {
            const btn = document.createElement("button");
            btn.textContent = "Kill";
            btn.onclick = () => vote(nonce);
            li.appendChild(btn);
          }
          if (selfRole === "muter") {
            const btn = document.createElement("button");
            btn.textContent = "Mute";
            btn.onclick = () => mute(nonce);
            li.appendChild(btn);
          }
          if (selfRole === "doctor") {
            const btn = document.createElement("button");
            btn.textContent = "Protect";
            btn.onclick = () => protect(nonce);
            li.appendChild(btn);
          }
          if (selfRole === "wizard") {
            const btn = document.createElement("button");
            btn.textContent = "Check";
            btn.onclick = () => checkRole(nonce);
            li.appendChild(btn);
          }
        }
      }

      playersList.appendChild(li);
    });

    // render public chat
    chatBox.innerHTML = "";
    data.chat.forEach(([who,msg]) => {
      const d = document.createElement("div");
      d.textContent = `${who}: ${msg}`;
      chatBox.appendChild(d);
    });

    // render mafia chat
    mafiaBox.innerHTML = "";
    data.mafia_chat.forEach(([who,msg]) => {
      const d = document.createElement("div");
      d.textContent = `${who}: ${msg}`;
      mafiaBox.appendChild(d);
    });

    // reset visibility & input
    publicSection.style.display = "block";
    mafiaSection.style.display = "none";
    chatBox.classList.remove("disabled");
    messageInput.disabled = false;

    // if dead, always disable
    if (!selfAlive) {
      messageInput.disabled = true;
    }
    // night & mafia alive
    if (!day && selfRole === "mafia" && selfAlive) {
      publicSection.style.display = "none";
      mafiaSection.style.display = "block";
    }
    // night & innocent alive
    if (!day && selfRole !== "mafia" && selfAlive) {
      chatBox.classList.add("disabled");
      messageInput.disabled = true;
    }
  }
});
