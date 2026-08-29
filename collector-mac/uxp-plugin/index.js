// Ghost Agent UXP panel (Photoshop 23+). Consent behaviour:
//  - capture is OFF every time Photoshop starts; the designer flips the toggle per session
//  - the panel text always states the current state
//  - the log is a plain JSON-lines file in the plugin's data folder, path shown on request
//  - nothing is written unless the toggle is on

const photoshop = require("photoshop");
const uxp = require("uxp");
const fs = uxp.storage.localFileSystem;

let capturing = false;
let logFile = null;

const stateEl = document.getElementById("state");
const toggle = document.getElementById("capture-toggle");
const logPathEl = document.getElementById("log-path");

function renderState() {
  if (capturing) {
    stateEl.textContent = "● On - logging layer edits for the active document";
    stateEl.className = "state on";
  } else {
    stateEl.textContent = "● Off - nothing is being logged";
    stateEl.className = "state off";
  }
}

async function ensureLog() {
  if (logFile) return logFile;
  const folder = await fs.getDataFolder();
  logFile = await folder.createFile("ghost-agent-uxp.jsonl", { overwrite: false }).catch(async () => {
    return await folder.getEntry("ghost-agent-uxp.jsonl");
  });
  return logFile;
}

async function appendLine(obj) {
  const file = await ensureLog();
  const existing = await file.read().catch(() => "");
  await file.write(existing + JSON.stringify(obj) + "\n");
}

function describeDocument() {
  const doc = photoshop.app.activeDocument;
  if (!doc) return null;
  const layers = [];
  const walk = (list, prefix) => {
    for (const layer of list) {
      const name = prefix + layer.name;
      if (layer.layers && layer.layers.length) {
        walk(layer.layers, name + "/");
        continue;
      }
      const b = layer.bounds;
      layers.push({
        name,
        kind: String(layer.kind),
        visible: layer.visible,
        bbox: b ? { x: b.left, y: b.top, width: b.right - b.left, height: b.bottom - b.top } : null,
      });
    }
  };
  walk(doc.layers, "");
  return {
    document: doc.name,
    canvas: { width: doc.width, height: doc.height, dpi: doc.resolution },
    layers,
  };
}

toggle.addEventListener("change", (e) => {
  capturing = !!e.target.checked;
  renderState();
  appendLine({ event_type: capturing ? "capture_on" : "capture_off", timestamp: new Date().toISOString() });
});

document.getElementById("open-log").addEventListener("click", async () => {
  const file = await ensureLog();
  logPathEl.textContent = file.nativePath;
});

photoshop.action.addNotificationListener(["historyStateChanged", "save"], async (event) => {
  if (!capturing) return; // hard gate - nothing below runs unless the toggle is on
  const snapshot = describeDocument();
  if (!snapshot) return;
  await appendLine({ event_type: event, timestamp: new Date().toISOString(), ...snapshot });
});

renderState();
