import json, time
import paho.mqtt.client as mqtt

BROKER = "localhost"
TOPIC_CMD  = "lab1/ac/cmd"
TOPIC_TEMP = "lab1/temperature"

outside = 31.0
temp = 30.0
cool_rate = 0.25
sleep_rate = 0.08
leak_rate = 0.02

mode = "off"
setpoint = 24.0
power = "off"

def on_message(c, userdata, msg):
    global mode, setpoint, power
    try:
        data = json.loads(msg.payload.decode())
        power = data.get("power","off")
        mode = data.get("mode","off")
        setpoint = float(data.get("setpoint",24.0))
    except Exception:
        pass

def main():
    global temp
    c = mqtt.Client(client_id="ac_actuator_sim_lab1")
    c.on_message = on_message
    c.connect(BROKER, 1883, 60)
    c.subscribe([(TOPIC_CMD,1)])
    c.loop_start()

    while True:
        if power == "on" and mode == "cool":
            if temp > setpoint:
                temp -= cool_rate
        elif power == "on" and mode == "sleep":
            if temp > setpoint: temp -= sleep_rate
            elif temp < setpoint: temp += sleep_rate/2.0
        else:
            if temp < outside: temp += leak_rate
            elif temp > outside: temp -= leak_rate

        c.publish(TOPIC_TEMP, json.dumps({"celsius": round(temp,2)}), qos=1, retain=True)
        time.sleep(1.0)

if __name__ == "__main__":
    main()
