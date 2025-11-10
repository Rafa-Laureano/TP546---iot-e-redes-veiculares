# blynk_bridge_rest.py — Bridge MQTT <-> Blynk Cloud via REST (HTTPS 443)
import os, json, time, threading
import urllib.parse
import requests
import paho.mqtt.client as mqtt

# ---- Config ----
BROKER     = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT  = int(os.getenv("MQTT_PORT", "1883"))
TOKEN      = os.getenv("BLYNK_TOKEN")
assert TOKEN, "Defina BLYNK_TOKEN com o token do seu Device (Blynk Cloud)."

BASE_URL   = "https://blynk.cloud/external/api"
TIMEOUT_S  = 5
POLL_S     = 2.0    # intervalo para ler Vpins do Blynk

# Tópicos MQTT
TOPIC_TEMP   = "lab1/temperature"   # {"celsius": 29.8}
TOPIC_PRES   = "lab1/presence"      # {"present": true}
TOPIC_AC_CMD = "lab1/ac/cmd"        # {"power":"on/off","mode":"cool/sleep/off","setpoint":24.0}
TOPIC_AC_ST  = "lab1/ac/state"      # {"state":"COOL","temp":27.5,"present":true}

# Vpins
V_TEMP, V_PRES, V_STATE, V_MODE, V_SETPT, V_POWER = "V0","V1","V2","V3","V4","V5"

# Estado cacheado para evitar floods
last_blynk = {"V0": None, "V1": None, "V2": None, "V3": None, "V4": None, "V5": None}
last_cmd    = {"power": None, "mode": None, "setpoint": None}
stop_flag   = False

# ---------- Helpers Blynk REST ----------
def blynk_update(pin, value):
    """
    Atualiza 1 Vpin via API REST do Blynk.
    Aceita número ou string. Strings serão url-encoded.
    """
    try:
        if isinstance(value, str):
            # strings precisam ser devidamente escapadas
            val = urllib.parse.quote(value, safe="")
        else:
            val = str(value)
        url = f"{BASE_URL}/update?token={TOKEN}&{pin}={val}"
        r = requests.get(url, timeout=TIMEOUT_S)
        return r.ok
    except Exception:
        return False

def blynk_get(pin):
    """
    Lê 1 Vpin via API REST do Blynk.
    Retorna string (valor) ou None.
    """
    try:
        url = f"{BASE_URL}/get?token={TOKEN}&{pin}"
        r = requests.get(url, timeout=TIMEOUT_S)
        if not r.ok:
            return None
        # a API pode retornar ["valor"] ou  valor direto
        try:
            data = r.json()
            if isinstance(data, list) and data:
                return data[0]
            return str(data)
        except Exception:
            return r.text
    except Exception:
        return None

# ---------- MQTT callbacks ----------
def on_connect(c, u, f, rc, p=None):
    c.subscribe([
        (TOPIC_TEMP, 1),
        (TOPIC_PRES, 1),
        (TOPIC_AC_ST, 1)
    ])

def on_message(c, u, msg):
    global last_blynk
    try:
        data = json.loads(msg.payload.decode())
    except Exception:
        return

    if msg.topic == TOPIC_TEMP:
        # Atualiza V0 (Temperatura)
        try:
            temp = float(data.get("celsius", 0.0))
        except Exception:
            return
        if last_blynk[V_TEMP] != temp:
            if blynk_update(V_TEMP, temp):
                last_blynk[V_TEMP] = temp

    elif msg.topic == TOPIC_PRES:
        # Atualiza V1 (Presença)
        present = bool(data.get("present", False))
        v = 1 if present else 0
        if last_blynk[V_PRES] != v:
            if blynk_update(V_PRES, v):
                last_blynk[V_PRES] = v

    elif msg.topic == TOPIC_AC_ST:
        # Atualiza V2 (Estado do AC) como texto
        st = data.get("state", "OFF")
        txt = f"{st}"
        if "temp" in data:
            try:
                txt += f" @ {float(data['temp']):.2f}°C"
            except Exception:
                pass
        if last_blynk[V_STATE] != txt:
            if blynk_update(V_STATE, txt):
                last_blynk[V_STATE] = txt

# ---------- Thread para ler Vpins do Blynk e publicar em MQTT ----------
def poll_blynk_to_mqtt(mclient):
    global stop_flag, last_cmd
    # Sincroniza leitura inicial para evitar publicar lixo
    for pin in (V_PRES, V_MODE, V_SETPT, V_POWER):
        last_blynk[pin] = blynk_get(pin)
        time.sleep(0.1)

    while not stop_flag:
        # V1 Presença -> publica em lab1/presence
        pres = blynk_get(V_PRES)
        if pres is not None and pres != last_blynk[V_PRES]:
            last_blynk[V_PRES] = pres
            present = True if str(pres) in ("1","true","True") else False
            mclient.publish(TOPIC_PRES, json.dumps({"present": present}), qos=1, retain=True)

        # V3 Modo -> parte do comando
        mode = blynk_get(V_MODE)
        # V4 Setpoint -> parte do comando
        setpt = blynk_get(V_SETPT)
        # V5 Power -> parte do comando
        power = blynk_get(V_POWER)

        # Monta comando se algo mudou
        changed = False
        payload = {}

        if mode is not None and mode != last_blynk[V_MODE]:
            last_blynk[V_MODE] = mode
            m = str(mode).lower()
            if m in ("off","cool","sleep"):
                payload["mode"] = m
                changed = True

        if setpt is not None and setpt != last_blynk[V_SETPT]:
            last_blynk[V_SETPT] = setpt
            try:
                payload["setpoint"] = float(setpt)
                changed = True
            except Exception:
                pass

        if power is not None and power != last_blynk[V_POWER]:
            last_blynk[V_POWER] = power
            p = "on" if str(power) in ("1","true","True") else "off"
            payload["power"] = p
            changed = True

        if changed:
            # Evita repetir o mesmo comando sem necessidade
            if payload != last_cmd:
                mclient.publish(TOPIC_AC_CMD, json.dumps(payload), qos=1, retain=True)
                last_cmd = payload

        time.sleep(POLL_S)

# ---------- Main ----------
def main():
    print("Bridge REST (HTTPS) Blynk <-> MQTT rodando. Ctrl+C para sair.")

    # MQTT client
    mclient = mqtt.Client(client_id="blynk_bridge_rest")
    mclient.on_connect = on_connect
    mclient.on_message = on_message
    mclient.connect(BROKER, MQTT_PORT, 60)
    mclient.loop_start()

    # Thread de polling Blynk
    t = threading.Thread(target=poll_blynk_to_mqtt, args=(mclient,), daemon=True)
    t.start()

    try:
        while True:
            time.sleep(0.2)
    except KeyboardInterrupt:
        pass
    finally:
        global stop_flag
        stop_flag = True
        mclient.loop_stop()

if __name__ == "__main__":
    main()

