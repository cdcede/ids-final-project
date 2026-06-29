import json
import numpy as np
import time
from datetime import datetime

import paho.mqtt.client as mqtt

# MQTT
client = mqtt.Client()
client.connect("mosquitto", 1883, 60)
gap = 4
# Leer tweets
with open("tweets1.json", "r", encoding="utf-8") as f:
    tweets = json.load(f)

while True:

    try:
        user = np.random.randint(len(tweets))
        tweet = np.random.randint(len(tweets[user]["tweets"]))
        # Produce the JSON data to the Kafka topic
        now = datetime.now()
        formatted = now.strftime("%Y-%m-%d %H:%M:%S")
        text = tweets[user]["tweets"][tweet].encode('utf-8','ignore').decode("utf-8").replace('\n', ' ')
        text += "."
        text = text.replace('"', "")
        text = text.replace('\\', "")

        #print('{"user_id":' + str(tweets[user]["id"]) + ',"tweet":"' + text + '", "timestamp":"' + formatted + '"}')
        payload = {
            "user_id": tweets[user]["id"],
            "tweet": text,
            "timestamp": formatted
        }

        message = json.dumps(payload, ensure_ascii=False)
        client.publish("tweets/topic", message)
        time.sleep(2)
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON: {e}")
        # Introduce a delay between insertions
        time.sleep(gap)

