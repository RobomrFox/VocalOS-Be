import { contextBridge, ipcRenderer } from "electron";

contextBridge.exposeInMainWorld("electron", {
  ipcRenderer: {
    send: (channel, data) => ipcRenderer.send(channel, data),
    on: (channel, listener) => ipcRenderer.on(channel, (event, ...args) => listener(...args)),
    removeAllListeners: (channel) => ipcRenderer.removeAllListeners(channel),
  },
});