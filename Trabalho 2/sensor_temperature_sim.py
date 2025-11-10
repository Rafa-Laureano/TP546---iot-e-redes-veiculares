import json, time, random
import paho.mqtt.client as mqtt

BROKER = "localhost"
TOPIC_TEMP = "lab1/temperature"
CLIENT_ID = "sensor_temp_lab1"

# Temperatura inicial
temp = 29.0
tendency = -0.02  # tendência inicial (resfriando bem devagar)

def main():
    global temp, tendency
    c = mqtt.Client(client_id=CLIENT_ID)
    c.connect(BROKER, 1883, 60)
    c.loop_start()

    print("Simulador de temperatura iniciado (mudanças lentas a cada 3 s)")
    while True:
        # pequenas flutuações + tendência suave
        temp += tendency + random.uniform(-0.01, 0.01)

        # Mantém temperatura dentro de limites realistas (20–31°C)
        if temp < 20:
            temp = 20
            tendency = +0.02
        elif temp > 31:
            temp = 31
            tendency = -0.02

        c.publish(TOPIC_TEMP, json.dumps({"celsius": round(temp, 2)}), qos=1)
        time.sleep(3)

if __name__ == "__main__":
    main()

