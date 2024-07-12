import paho.mqtt.client as mqtt
import configparser
import json
import pymongo

class MQTTClient:
    def __init__(self, mongo_client, config):
        # Connect to MQTT broker
        self.client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2, client_id='Sensor subscriber')
        self.client.username_pw_set(config['mosquitto']['user'], config['mosquitto']['pass'])
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.connect(config['mosquitto']['host'], int(config['mosquitto']['port']))
        self.client.loop_start()

        # Connect to MongoDB
        self.mongo_client = mongo_client
        self.db = self.mongo_client[config['mongodb']['db']]
        self.temperature_data = self.db['temperature_data']
        self.humidity_data = self.db['humidity_data']

    def on_connect(self, client, userdata, flags, reason_code, properties):
        print(f"Connected with result code {reason_code}") # TODO: connection can also be refused, so the reason_code needs to be checked
        self.client.subscribe('sensors', qos=2)
        self.client.message_callback_add('sensors', self.on_sensor_data_received)

    def on_sensor_data_received(self, client, userdata, message):
        data = json.loads(message.payload.decode())
        self.temperature_data.insert_one({'temperature': data['values']['temperature'], 'timestamp': data['timestamp']})
        self.humidity_data.insert_one({'humidity': data['values']['humidity'], 'timestamp': data['timestamp']})

    def on_message(self, client, userdata, message):
        print('Message topic {}'.format(message.topic))
        print('Message payload:')
        print(message.payload.decode())