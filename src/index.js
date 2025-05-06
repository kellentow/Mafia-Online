document.addEventListener("DOMContentLoaded", () => {
  const idInput = document.getElementById("id_input");
  const nameInput = document.getElementById("name_input");
  const joinBtn = document.getElementById("join_button");
  const spectBtn = document.getElementById("spectate_button");

  joinBtn.addEventListener("click", () => {
    const id = idInput.value.trim();
    const name = nameInput.value.trim();

    if (!id || !name) {
      alert("Please enter both a name and game ID.");
      return;
    }

    fetch(`/game/${id}?name=${encodeURIComponent(name)}`, {
      method: "POST"
    }).then(res => {
      if (res.ok) {
        window.location.href = `/game/${id}`;
      } else {
        alert("Failed to join the game.");
      }
    });
  });
  spectBtn.addEventListener("click", () => {
    const id = idInput.value.trim();

    if (!id) {
      alert("Please enter a game ID.");
      return;
    }
    window.location.href = `/game/${id}`;
  });
});