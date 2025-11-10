import { app, BrowserWindow, ipcMain, screen } from "electron";
import path, { dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

let win;
const isDev = process.env.NODE_ENV === "development";

/**
 * 🪟 Create the main VocalAI window (centered by default)
 */
function createWindow() {
  const display = screen.getPrimaryDisplay();
  const { width: screenWidth, height: screenHeight } = display.bounds; // ✅ use full screen bounds
  const { x: displayX, y: displayY } = display.bounds; // offset in multi-monitor setups

  const winWidth = 1000;
  const winHeight = 700;

  // ✅ Calculate perfect center considering monitor offsets
  const x = Math.floor(displayX + (screenWidth - winWidth) / 2);
  const y = Math.floor(displayY + (screenHeight - winHeight) / 2);

  win = new BrowserWindow({
    x,
    y,
    width: winWidth,
    height: winHeight,
    frame: false,
    transparent: true,
    backgroundColor: "#00000000",
    resizable: true,
    movable: true,
    focusable: true,
    hasShadow: true,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: false,
      experimentalFeatures: true,
      webSecurity: false,
      devTools: true,
    },
  });

  if (isDev) {
    win.loadURL("http://localhost:5173/");
  } else {
    win.loadFile(path.join(__dirname, "../dist/index.html"));
  }

  // ✅ Keep Audient always on top
  win.setAlwaysOnTop(true, "screen-saver");

  console.log("✅ VocalAI window created and perfectly centered");

  win.on("resize", () => {
    const [width, height] = win.getSize();
    win.webContents.send("window-resized", { width, height });
  });

  // ✅ Ensure window comes to front & visible after load
  win.once("ready-to-show", () => {
    win.show();
    win.focus();
  });
}

/**
 * 🧩 Smooth animated movement helper
 */
function smoothMoveWindow(bounds, duration = 450) {
  if (!win) return;

  const startBounds = win.getBounds();
  const startTime = Date.now();

  const animate = () => {
    const elapsed = Date.now() - startTime;
    const progress = Math.min(elapsed / duration, 1);
    const eased = 0.5 - Math.cos(progress * Math.PI) / 2; // easeInOut

    const x = startBounds.x + (bounds.x - startBounds.x) * eased;
    const y = startBounds.y + (bounds.y - startBounds.y) * eased;
    const width = startBounds.width + (bounds.width - startBounds.width) * eased;
    const height = startBounds.height + (bounds.height - startBounds.height) * eased;

    win.setBounds({
      x: Math.round(x),
      y: Math.round(y),
      width: Math.round(width),
      height: Math.round(height),
    });

    if (progress < 1) {
      setTimeout(animate, 1000 / 60);
    } else {
      win.webContents.send("window-resized", { width: bounds.width, height: bounds.height });
    }
  };

  animate();
}

/**
 * 🎧 Listening mode — only visual, no window movement
 */
ipcMain.on("set-listening-mode", (_, listening) => {
  if (!win) return;
  
  // ✅ No smoothMoveWindow or setSize here — just log
  console.log(`🎧 Listening mode toggled → ${listening}`);
  
  // Optional: notify frontend if you want UI to react
  win.webContents.send("listening-state", listening);
});


/**
 * 🪟 Dock to RIGHT side (Siri-style)
 */
ipcMain.on("move-window-side", () => {
  if (!win) return;

  const display = screen.getPrimaryDisplay();
  const { width, height } = display.workAreaSize;

  let targetWidth = Math.floor(width * 0.3);
  let targetHeight = Math.floor(height * 0.85);
  targetWidth = Math.max(360, Math.min(targetWidth, width - 40));
  targetHeight = Math.max(400, Math.min(targetHeight, height - 40));

  const margin = 10;
  const targetX = width - targetWidth - margin;
  const targetY = Math.floor(height * 0.07);

  smoothMoveWindow({ x: targetX, y: targetY, width: targetWidth, height: targetHeight }, 500);
  win.focus();
  win.webContents.send("window-position", "side");
  console.log("✅ Docked on right with animation!");
});

/**
 * 🪞 Dock to LEFT side (focus-safe + screen offset aware)
 */
ipcMain.on("move-window-left", () => {
  if (!win) return;

  const display = screen.getPrimaryDisplay();
  const { bounds } = display;
  const { width, height, x: screenX, y: screenY } = bounds;

  // ⚙️ Window target size (adaptive but stable)
  const targetWidth = Math.floor(width * 0.32);
  const targetHeight = Math.floor(height * 0.85);
  const margin = 10;

  // 🧭 Target position — left side, small top offset
  const targetX = screenX + margin;
  const targetY = screenY + Math.floor(height * 0.07);

  console.log("🪞 Docking Audient LEFT:", { targetX, targetY, targetWidth, targetHeight });

  // ✅ Delay slightly to allow Chrome to finish opening
  setTimeout(() => {
    try {
      // Make sure window is visible and on top
      win.show();
      win.setAlwaysOnTop(true, "screen-saver");
      win.focus();

      // ✅ Smooth slide to left
      smoothMoveWindow(
        { x: targetX, y: targetY, width: targetWidth, height: targetHeight },
        600
      );

      // ✅ Ensure it stays on top and recognized as docked
      setTimeout(() => {
        win.setAlwaysOnTop(true, "screen-saver");
        win.webContents.send("window-position", "left");
        console.log("✅ Audient docked LEFT successfully!");
      }, 800);
    } catch (err) {
      console.error("❌ Docking error (LEFT):", err);
    }
  }, 1200); // 1.2s delay after Playwright opens
});


/**
 * 🏠 Return to Center
 */
ipcMain.on("move-window-center", () => {
  if (!win) return;

  const display = screen.getPrimaryDisplay();
  const { width, height } = display.workAreaSize;

  const targetWidth = Math.floor(width * 0.6);
  const targetHeight = Math.floor(height * 0.7);
  const targetX = Math.floor((width - targetWidth) / 2);
  const targetY = Math.floor((height - targetHeight) / 2);

  smoothMoveWindow({ x: targetX, y: targetY, width: targetWidth, height: targetHeight }, 500);
  win.focus();
  win.webContents.send("window-position", "center");
  console.log("✅ Returned to center view!");
});

/**
 * 🧪 Ping test
 */
ipcMain.on("ping-test", () => {
  console.log("📡 Renderer connected successfully!");
});

/**
 * 🚀 App Lifecycle
 */
app.whenReady().then(() => {
  createWindow();
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});