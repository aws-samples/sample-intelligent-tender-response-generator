import { useAnalysisDataStore } from "../data_store/analysisDataStore.ts";

let ws = null;
let started = false;
let reconnectTimer = null;


function scheduleReconnect(connect) {
    if (reconnectTimer) return;

    reconnectTimer = window.setTimeout(() => {
        reconnectTimer = null;
        connect();
    }, 1000);
}


export function startWebSocket(url, token) {
    if (started) return;

    started = true;

    const connect = async () => {
        try {
            const finalUrl = `${url}?token=${encodeURIComponent(token)}`;

            ws = new WebSocket(finalUrl);
            ws.onopen = () => {};

            ws.onmessage = (evt) => {
                let msg = {};

                try { msg = JSON.parse(evt.data); }
                catch { return; }

                const store = useAnalysisDataStore.getState();
                store.upsertItem(msg)
            };

            ws.onclose = () => {
                ws = null;
                scheduleReconnect(connect);
            };

            ws.onerror = () => {
                ws?.close();
            };
        }
        catch {
            scheduleReconnect(connect);
        }
    };

    connect();
}

export function stopWebSocket() {
    started = false;

    if (reconnectTimer) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
    }

    ws?.close();
    ws = null;
}
