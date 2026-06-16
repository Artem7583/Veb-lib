async function loadLayoutPartials() {
  const shell = document.getElementById("pageShell");
  const dialogsRoot = document.getElementById("dialogsRoot");
  if (!shell || !dialogsRoot) {
    throw new Error("Контейнеры разметки не найдены.");
  }
  const fetchPart = (url) =>
    fetch(url, { cache: "no-cache" }).then((response) => {
      if (!response.ok) throw new Error(`Не удалось загрузить ${url}`);
      return response.text();
    });
  const [header, main, footer, dialogs] = await Promise.all([
    fetchPart("/partials/header.html"),
    fetchPart("/partials/main.html"),
    fetchPart("/partials/footer.html"),
    fetchPart("/partials/dialogs.html"),
  ]);
  shell.innerHTML = header + main;
  dialogsRoot.insertAdjacentHTML("beforebegin", footer.trim());
  dialogsRoot.innerHTML = dialogs;
}

window.__layoutReady = loadLayoutPartials();
