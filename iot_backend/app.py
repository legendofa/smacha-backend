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
    response = jsonify(dumps(curser))
    response.headers.add("Access-Control-Allow-Origin", "*")
    return response

@app.route("/get_humidity_data")
async def get_humidity_data() -> ResponseReturnValue:
    curser = database.humidity_data.find()
    response = jsonify(dumps(curser))
    response.headers.add("Access-Control-Allow-Origin", "*")
    return response
    
@app.route("/get_wall_plug_data")
async def get_wall_plug_data() -> ResponseReturnValue:
    curser = database.wall_plug_data.find()
    response = jsonify(dumps(curser))
    response.headers.add("Access-Control-Allow-Origin", "*")
    return response
    
@app.route("/get_solar_panel_data")
async def get_solar_panel_data() -> ResponseReturnValue:
    curser = database.solar_panel_data.find()
    response = jsonify(dumps(curser))
    response.headers.add("Access-Control-Allow-Origin", "*")
    return response

@app.route("/get_average_temperature_data")
async def get_average_temperature_data() -> ResponseReturnValue:
    # get the last 10 entries
    curser = database.temperature_data.find().sort("_id", -1).limit(10)

    # calculate the average
    sum = 0
    count = 0
    for entry in curser:
        sum += entry['temperature']
        count += 1
    average = sum / count

    response = jsonify(average)
    response.headers.add("Access-Control-Allow-Origin", "*")
    return response

@app.route("/get_average_humidity_data")
async def get_average_humidity_data() -> ResponseReturnValue:
    # get the last 10 entries
    curser = database.humidity_data.find().sort("_id", -1).limit(10)

    # calculate the average
    sum = 0
    count = 0
    for entry in curser:
        sum += entry['humidity']
        count += 1
    average = sum / count

    response = jsonify(average)
    response.headers.add("Access-Control-Allow-Origin", "*")
    return response