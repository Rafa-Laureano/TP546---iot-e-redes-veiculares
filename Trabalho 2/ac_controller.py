import json, time
from datetime import datetime
import paho.mqtt.client as mqtt

BROKER = "localhost"
TOPIC_TEMP = "lab1/temperature"
TOPIC_PRES = "lab1/presence"
TOPIC_CMD  = "lab1/ac/cmd"
TOPIC_STATE= "lab1/ac/state"

SETPOINT = 24.0
ON_AT    = 28.0
HYST     = 0.5
MIN_OFF  = 120  # segundos mínimo OFF

state = "OFF"         # OFF | COOL | SLEEP
last_temp = None
present = False
last_off_time = datetime.min

def publish_cmd(c, power, mode, setpoint):
    c.publish(TOPIC_CMD, json.dumps({"power": power, "mode": mode, "setpoint": setpoint}), qos=1, retain=True)

def publish_state(c, msg):
    c.publish(TOPIC_STATE, json.dumps(msg), qos=1, retain=True)

def on_message(c, userdata, msg):
    global last_temp, present
    try:
        data = json.loads(msg.payload.decode())
        if msg.topic == TOPIC_TEMP:
            last_temp = float(data["celsius"])
        elif msg.topic == TOPIC_PRES:
            present = bool(data["present"])
    except Exception:
        pass

def main():
    global state, last_off_time
    c = mqtt.Client(client_id="ac_controller_lab1")
    c.on_message = on_message
    c.connect(BROKER, 1883, 60)
    c.subscribe([(TOPIC_TEMP,1),(TOPIC_PRES,1)])
    c.loop_start()

    publish_state(c, {"state": state, "reason":"boot"})
    while True:
        if last_temp is None:
            time.sleep(0.5); continue

        now = datetime.now()
        can_turn_on = (now - last_off_time).total_seconds() >= MIN_OFF

        # lógica de decisão
        desired, mode = "OFF", "off"
        if not present:
            desired, mode = "OFF", "off"
        else:
            if last_temp >= ON_AT and can_turn_on:
                desired, mode = "COOL", "cool"
            elif SETPOINT - HYST <= last_temp <= SETPOINT + HYST:
                desired, mode = "SLEEP", "sleep"
            elif last_temp > SETPOINT + HYST and can_turn_on:
                desired, mode = "COOL", "cool"
            else:
                desired, mode = "OFF", "off"

        if desired != state:
            state = desired
            if state == "OFF":
                publish_cmd(c, "off", "off", SETPOINT)
                last_off_time = now
            elif state == "COOL":
                publish_cmd(c, "on", "cool", SETPOINT)
            elif state == "SLEEP":
                publish_cmd(c, "on", "sleep", SETPOINT)

            publish_state(c, {"state": state, "temp": round(last_temp,2), "present": present, "reason":"rule"})

        time.sleep(1.0)

if __name__ == "__main__":
    main()
