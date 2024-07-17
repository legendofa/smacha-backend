import paho.mqtt.client as mqtt
import configparser
import json
import pymongo
import random
from iot_backend.planner import Planner

# TODO: Groß/Kleinschreibung bei True und False beim Planner
class MQTTClient:
    def __init__(self, mongo_client, config):
        print('MQTTClient init', flush=True)

        # Connect to MQTT broker
        self.client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2, client_id='iot-backend' + str(random.randint(0, 1000)))
        #self.client.username_pw_set(config['mosquitto']['user'], config['mosquitto']['pass'])
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.connect(config['mosquitto']['host'], int(config['mosquitto']['port']))
        self.client.loop_start()

        # Connect to MongoDB
        self.mongo_client = mongo_client
        self.db = self.mongo_client[config['mongodb']['db']]
        self.temperature_data = self.db['temperature_data']
        self.humidity_data = self.db['humidity_data']
        self.wall_plug_data = self.db['wall_plug_data']
        self.solar_panel_data = self.db['solar_panel_data']

        # Planning component
        self.planner = Planner(self.client)

    def on_connect(self, client, userdata, flags, reason_code, properties):
        print(f"Connected with result code {reason_code}", flush=True) # TODO: connection can also be refused, so the reason_code needs to be checked
        self.client.subscribe('sensors', qos=2)
        self.client.subscribe('/wall-plug/stats', qos=2)
        self.client.subscribe('/solar-panel/stats', qos=2)
        self.client.subscribe('frontend/+', qos=2)
        self.client.message_callback_add('sensors', self.on_sensor_data_received)
        self.client.message_callback_add('/wall-plug/stats', self.on_wall_plug_stats_received)
        self.client.message_callback_add('/solar-panel/stats', self.on_solar_panel_stats_received)
        self.client.message_callback_add('frontend/trip-start', self.on_trip_start_received)
        self.client.message_callback_add('frontend/schedule-use', self.on_schedule_use_received)
        self.client.message_callback_add('frontend/trip-end', self.on_trip_end_received)

    def on_sensor_data_received(self, client, userdata, message):
        data = json.loads(message.payload.decode())
        self.planner.add_dht_sensor_data(int(data['values']['temperature']), int(data['values']['humidity']))
        self.temperature_data.insert_one({'temperature': data['values']['temperature'], 'timestamp': data['timestamp']})
        self.humidity_data.insert_one({'humidity': data['values']['humidity'], 'timestamp': data['timestamp']})

    #pub struct INA219Stats {
    #    datetime: DateTime,
    #    shunt_voltage: i16,
    #    power: i16,
    #    current: f32,
    #    bus_voltage: u16,
    #}

    def on_wall_plug_stats_received(self, client, userdata, message):
        data = json.loads(message.payload.decode())
        #print('Wall plug stats received: {}'.format(data))
        self.wall_plug_data.insert_one({'shunt_voltage': data['shunt_voltage'], 'power': data['power'], 'current': data['current'], 'bus_voltage': data['bus_voltage'], 'timestamp': data['datetime']})

    def on_solar_panel_stats_received(self, client, userdata, message):
        data = json.loads(message.payload.decode())
        #print('Solar panel stats received: {}'.format(data))
        self.solar_panel_data.insert_one({'shunt_voltage': data['shunt_voltage'], 'power': data['power'], 'current': data['current'], 'bus_voltage': data['bus_voltage'], 'timestamp': data['datetime']})

    def on_trip_start_received(self, client, userdata, message):
        data = json.loads(message.payload.decode())
        msg = {'energy_usage_mwh': int(data['mWh'])}
        self.planner.start_trip()
        self.client.publish('/car/start-trip', json.dumps(msg), qos=2)

    def on_schedule_use_received(self, client, userdata, message):
        data = message.payload.decode()
        self.planner.set_schedule_use(True if data == 'true' else False)

    def on_trip_end_received(self, client, userdata, message):
        self.planner.end_trip()

    def on_message(self, client, userdata, message):
        print('Unhandled Message topic {}'.format(message.topic), flush=True)
        print('Message payload:', flush=True)
        print(message.payload.decode())


    # When to start the planner:
    # - When ScheduleUse changes - yes
    # - When SolarPanel 
    # - When temperature and humidity change
    # - Dont run planner if there is currently an trip going on
    # - When the user returns from a trip - yes

