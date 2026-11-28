import { singingLink } from "./song-flow.js";

const list = document.getElementById("song-list");
const message = document.getElementById("msg");
const params = new URLSearchParams(window.location.search);
const settings = {};
for (const key of ["difficulty", "latency"]) {
  if (params.has(key)) settings[key] = params.get(key);
}

async function loadSongs() {
  try {
    const response = await fetch("/api/songs");
    if (!response.ok) throw new Error("目前無法讀取歌曲清單，請重新整理後再試。");
    const songs = await response.json();
    if (!songs.length) {
      message.textContent = "目前沒有可唱的歌曲。加入歌曲後請重新整理。";
      return;
    }

    const items = songs.map(({ id, title }) => {
      const item = document.createElement("li");
      const link = document.createElement("a");
      const name = document.createElement("span");
      const arrow = document.createElement("span");

      link.href = singingLink(id, settings);
      name.textContent = title || id;
      arrow.textContent = "→";
      arrow.setAttribute("aria-hidden", "true");
      link.append(name, arrow);
      item.append(link);
      return item;
    });
    list.replaceChildren(...items);
    message.textContent = "";
  } catch (error) {
    message.textContent = error.message;
  }
}

loadSongs();
