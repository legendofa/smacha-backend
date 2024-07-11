from flask import Flask
from flask.typing import ResponseReturnValue

app = Flask(__name__)
app.config["CORS_HEADERS"] = "Content-Type"

if __name__ == "__main__":
    app.run()

@app.route("/get_temperature_data")
async def get_temperature_data() -> ResponseReturnValue:
    return "TODO"
    
