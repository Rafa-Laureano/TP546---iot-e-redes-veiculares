# sensor_presence_sim.py (versão rápida p/ demonstração)
import json, time
import paho.mqtt.client as mqtt

BROKER = "localhost"
TOPIC_PRES = "lab1/presence"
CLIENT_ID = "sensor_presence_lab1"

def main():
    c = mqtt.Client(client_id=CLIENT_ID)
    c.connect(BROKER, 1883, 60)
    c.loop_start()

    print("Simulador de presença iniciado (troca a cada 30 s)")
    present = False
    while True:
        present = not present  # alterna True/False
        c.publish(TOPIC_PRES, json.dumps({"present": present}), qos=1, retain=True)
        print(f"Presença: {'sim' if present else 'não'}")
        time.sleep(30)  # intervalo de 30 segundos entre mudanças

if __name__ == "__main__":
    main()

