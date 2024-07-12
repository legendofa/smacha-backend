from flask import Flask, jsonify
from flask.typing import ResponseReturnValue
from iot_backend.mqtt_client import MQTTClient
import pymongo
import configparser
from bson.json_util import dumps

app = Flask(__name__)
app.config["CORS_HEADERS"] = "Content-Type"

config = configparser.ConfigParser()
config.read('iot_backend/config.ini')
mongo_client = pymongo.MongoClient(config['mongodb']['host'], int(config['mongodb']['port']))
database = mongo_client[config['mongodb']['db']]
mqtt_client = MQTTClient(mongo_client, config)

if __name__ == "__main__":
    app.run(host='0.0.0.0')

@app.route("/get_temperature_data")
async def get_temperature_data() -> ResponseReturnValue:
    curser = database.temperature_data.find()
    return jsonify(dumps(curser))

@app.route("/get_humidity_data")
async def get_humidity_data() -> ResponseReturnValue:
    curser = database.humidity_data.find()
    return jsonify(dumps(curser))
    
