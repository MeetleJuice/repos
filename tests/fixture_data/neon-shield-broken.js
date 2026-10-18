(() => {
  const canvas = document.getElementById("game"),
    ctx = canvas.getContext("2d");
  const $ = (id) => document.getElementById(id);
  const W = canvas.width,
    H = canvas.height,
    keys = new Set();
  let state = "ready",
    x = W / 2,
    elapsed = 0,
    spawn = 0,
    last = 0,
    score = 0,
    best = 0;
  let obstacles = [],
    particles = [],
    shield = null,
    pickups = [],
    shieldActive = false;
  const storageKey = "neon-dodge-best";
  try {
    const saved = Number(localStorage.getItem(storageKey));
    best = Number.isFinite(saved) ? Math.max(0, Math.floor(saved)) : 0;
  } catch (_) {
    $("storage-notice").textContent =
      "Storage is unavailable. High scores last only for this session.";
  }
  $("best").textContent = best;
  function persist() {
    if (score > best) {
      best = score;
      $("best").textContent = best;
      try {
        localStorage.setItem(storageKey, String(best));
      } catch (_) {
        $("storage-notice").textContent =
          "Your browser could not save the high score.";
      }
    }
  }
  function showState(value) {
    $("state").textContent = value;
  }
  function start() {
    state = "playing";
    x = W / 2;
    elapsed = spawn = score = 0;
    obstacles = [];
    particles = [];
    pickups = [];
    shieldActive = false;
    keys.clear();
    $("score").textContent = "0";
    $("overlay").hidden = true;
    $("pause").disabled = false;
    $("pause").textContent = "Pause";
    showState("Playing");
    canvas.focus();
  }
  function pause() {
    if (state === "playing") {
      state = "paused";
      keys.clear();
      showState("Paused");
      $("pause").textContent = "Resume";
    } else if (state === "paused") {
      state = "playing";
      showState("Playing");
      $("pause").textContent = "Pause";
    }
  }
  function gameOver() {
    state = "over";
    persist();
    keys.clear();
    showState("Game over");
    $("pause").disabled = true;
    $("overlay-title").textContent = "Nice flight.";
    $("overlay-message").textContent =
      `Final score: ${score}. Ready for another run?`;
    $("start").textContent = "Play again";
    $("overlay").hidden = false;
  }
  function update(dt) {
    if (state !== "playing") return;
    elapsed += dt;
    score = Math.floor(elapsed * 10);
    $("score").textContent = score;
    // Save earned progress even if the user refreshes before a collision.
    persist();
    const direction = (keys.has("right") ? 1 : 0) - (keys.has("left") ? 1 : 0);
    x = Math.max(18, Math.min(W - 18, x + direction * 370 * dt));
    spawn += dt;
    const interval = Math.max(0.24, 0.9 - elapsed * 0.009);
    while (spawn >= interval) {
      spawn -= interval;
      const size = 18 + Math.random() * 22;
      obstacles.push({
        x: size + Math.random() * (W - size * 2),
        y: -size,
        size,
        speed: Math.min(420, 140 + elapsed * 4) + Math.random() * 50,
      });
      if (Math.random() < 0.15) {
        pickups.push({
          x: size + Math.random() * (W - size * 2),
          y: -size,
          size,
          speed: Math.min(420, 140 + elapsed * 4) + Math.random() * 50,
        });
      }
    }
    for (const o of obstacles) {
      o.y += o.speed * dt;
      if (
        Math.abs(o.x - x) < o.size * 0.65 + 12 &&
        Math.abs(o.y - (H - 65)) < o.size * 0.65 + 16
      ) {
        if (shieldActive) {
          shieldActive = false;
        } else {
          gameOver();
          break;
        }
      }
    }
    for (const p of pickups) {
      p.y += p.speed * dt;
      if (
        Math.abs(p.x - x) < p.size * 0.65 + 12 &&
        Math.abs(p.y - (H - 65)) < p.size * 0.65 + 16
      ) {
        shieldActive = true;
        pickups = pickups.filter((p) => p !== p);
        break;
      }
    }
    obstacles = obstacles.filter((o) => o.y < H + 50);
    pickups = pickups.filter((p) => p.y < H + 50);
    if (direction) particles.push({ x, y: H - 44, life: 0.3 });
    for (const p of particles) {
      p.y += 70 * dt;
      p.life -= dt;
    }
    particles = particles.filter((p) => p.life > 0).slice(-100);
  }
  function draw(now) {
    ctx.fillStyle = "#09111f";
    ctx.fillRect(0, 0, W, H);
    for (let i = 0; i < 65; i++) {
      const sx = (i * 127.3) % W,
        sy = (i * 83.7 + elapsed * (12 + (i % 9))) % H;
      ctx.fillStyle = i % 3 ? "#40546e" : "#86bbda";
      ctx.fillRect(sx, sy, 1.5, 1.5);
    }
    ctx.strokeStyle = "#10243a";
    ctx.lineWidth = 1;
    for (let i = 1; i < 6; i++) {
      ctx.beginPath();
      ctx.moveTo(i * 100, 0);
      ctx.lineTo(i * 100, H);
      ctx.stroke();
    }
    for (const p of particles) {
      ctx.fillStyle = `rgba(77,218,255,${p.life})`;
      ctx.fillRect(p.x - 2, p.y, 4, 8);
    }
    ctx.shadowBlur = 16;
    ctx.shadowColor = "#ff5d9e";
    ctx.fillStyle = "#f25f9e";
    for (const o of obstacles) {
      ctx.beginPath();
      ctx.moveTo(o.x, o.y - o.size);
      ctx.lineTo(o.x + o.size * 0.7, o.y);
      ctx.lineTo(o.x, o.y + o.size);
      ctx.lineTo(o.x - o.size * 0.7, o.y);
      ctx.closePath();
      ctx.fill();
    }
    ctx.shadowColor = "#43d5ff";
    ctx.fillStyle = "#63e1ff";
    ctx.beginPath();
    ctx.moveTo(x, H - 85);
    ctx.lineTo(x + 15, H - 48);
    ctx.lineTo(x, H - 57);
    ctx.lineTo(x - 15, H - 48);
    ctx.closePath();
    ctx.fill();
    ctx.shadowBlur = 0;
    if (shieldActive) {
      ctx.fillStyle = "#00ff00";
      ctx.beginPath();
      ctx.arc(W / 2, H - 50, 15, 0, Math.PI * 2);
      ctx.fill();
    }
    if (state === "paused") {
      ctx.fillStyle = "#08101b99";
      ctx.fillRect(0, 0, W, H);
      ctx.fillStyle = "#d8f5ff";
      ctx.font = "bold 32px system-ui";
      ctx.textAlign = "center";
      ctx.fillText("PAUSED", W / 2, H / 2);
    }
  }
  function frame(now) {
    const dt = Math.min(0.05, Math.max(0, (now - last) / 1000));
    last = now;
    update(dt);
    draw(now);
    requestAnimationFrame(frame);
  }
  const keyMap = {
    ArrowLeft: "left",
    a: "left",
    A: "left",
    ArrowRight: "right",
    d: "right",
    D: "right",
  };
  window.addEventListener("keydown", (e) => {
    if (keyMap[e.key]) {
      e.preventDefault();
      keys.add(keyMap[e.key]);
    }
    if (["p", "P", " "].includes(e.key)) {
      e.preventDefault();
      if (!e.repeat) pause();
    }
  });
  window.addEventListener("keyup", (e) => keys.delete(keyMap[e.key]));
  window.addEventListener("blur", () => {
    keys.clear();
    if (state === "playing") pause();
  });
  document.addEventListener("visibilitychange", () => {
    if (document.hidden && state === "playing") pause();
  });
  for (const id of ["left", "right"]) {
    $(id).addEventListener("pointerdown", (e) => {
      e.preventDefault();
      $(id).setPointerCapture(e.pointerId);
      keys.add(id);
    });
    for (const event of ["pointerup", "pointercancel", "lostpointercapture"])
      $(id).addEventListener(event, () => keys.delete(id));
  }
  $("start").addEventListener("click", start);
  $("restart").addEventListener("click", start);
  $("pause").addEventListener("click", pause);
  requestAnimationFrame(frame);
})();
