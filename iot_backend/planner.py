import requests
import json
import time
import asyncio
from threading import Thread

problem = """
(define (problem charge-battery-problem)
  (:domain charge-battery)

  (:objects
    need-charge charging Choose-ChgType fullycharge 
    high low medium
    fast slow stop
    true false
    Solar Mix Oulet
    battery1  battery2  battery3
  )

  (:init
    (state-battery {state_battery})
    (temperature {temperature})
    (humidity {humidity})
    (connected-battery {connected_battery})
    (BatteryN {BatteryN})
    (ScheduleUse {ScheduleUse})
    (SolarPanel {SolarPanel})
    
    (transition need-charge Choose-ChgType)
    (transition Choose-ChgType fullycharge)
    (transition charging fullycharge)
  )

  (:goal
    (charge-speed stop) 
  ) 
)

"""

domain = """
(define (domain charge-battery)
  (:predicates
    (state-battery ?state)
    (transition ?ini ?fin)
    (ScheduleUse ?Soon)
    (SolarPanel ?sun)
    (temperature ?temp)
    (humidity ?hum)
    (charge-speed ?velocity)
    (charge-type ?Solar)
    (connected-battery ?connected)
    (BatteryN ?battery)
  )

  (:action fast-charge-transition
    :parameters (?ini-state ?fin-state ?battery)
    :precondition (and (not(state-battery Choose-ChgType))(BatteryN ?battery)(connected-battery true)(state-battery ?ini-state) (transition ?ini-state ?fin-state)(or(ScheduleUse True)(SolarPanel True)(and(temperature high)(humidity low))))
    :effect (and (charge-speed fast)(state-battery  ?fin-state)(BatteryN ?battery))
    )
  
  (:action medium-charge-transition
    :parameters (?ini-state ?fin-state ?battery)
    :precondition (and (not(state-battery Choose-ChgType))(ScheduleUse false)(BatteryN ?battery)(connected-battery true)(state-battery ?ini-state) (transition ?ini-state ?fin-state)(SolarPanel false)(or(and(temperature low)(humidity low))(and(temperature high)(humidity high))))
    :effect (and (charge-speed medium)(BatteryN ?battery)(state-battery ?fin-state))
  )
  
  (:action slow-charge-transition
    :parameters (?ini-state ?fin-state ?battery)
    :precondition (and (not(state-battery Choose-ChgType))(ScheduleUse false)(BatteryN ?battery)(connected-battery true)(state-battery ?ini-state) (transition ?ini-state ?fin-state)(SolarPanel false)(temperature low)(humidity high))
    :effect (and (charge-speed slow)(BatteryN ?battery)(state-battery ?fin-state))
    )
  
    (:action stop-charge
    :parameters ( ?battery )
    :precondition (and(BatteryN ?battery)(or (state-battery fullycharge)(connected-battery false)))
    :effect (and (charge-speed stop)(BatteryN ?battery))
  )
  
    (:action Solar-type-transition
    :parameters (?ini-state ?fin-state ?battery)
    :precondition (and (state-battery Choose-ChgType)(BatteryN ?battery)(transition ?ini-state ?fin-state)(or(charge-speed medium)(and(connected-battery true)(or(SolarPanel True)(and(temperature high)(humidity low))))))
    :effect (and (BatteryN ?battery)(state-battery ?fin-state)(charge-type Solar))
    )
  (:action mix-type-transition
    :parameters (?ini-state ?fin-state ?battery)
    :precondition (and (state-battery Choose-ChgType)(BatteryN ?battery)(connected-battery true)(ScheduleUse true)(state-battery ?ini-state) (transition ?ini-state ?fin-state)(temperature low)(SolarPanel false)(or(and(temperature low)(humidity low))(and(temperature high)(humidity high))))
    :effect (and (charge-type Mix)(BatteryN ?battery)(state-battery ?fin-state))
    )
  (:action oulet-type-transition
    :parameters (?ini-state ?fin-state ?battery)
    :precondition (and (state-battery Choose-ChgType)(BatteryN ?battery)(connected-battery true)(or(charge-speed slow)(and(ScheduleUse true)(state-battery ?ini-state) (SolarPanel false)(transition ?ini-state ?fin-state)(temperature low)(humidity high))))
    :effect (and (charge-type Oulet)(BatteryN ?battery)(state-battery ?fin-state))
    )
)
"""

class Planner:
    def __init__(self, mqtt_client) -> None:
        self.mqtt_client = mqtt_client
        self.charging = False

        self.base_url = "https://solver.planning.domains:5001"
        self.onTrip = False #done
        self.SolarPanel = True # TODO
        self.ScheduleUse = False #done
        self.state_battery = "need-charge" # we dont get this data yet
        self.temperature = "low" # done
        self.humidity = "low" # done
        self.connected_battery = True # we dont get this data yet
        self.BatteryN = "battery1" # we only have one battery in the current system

        self.last_temperature_values = [] # save the last 10 temperature values
        self.last_humidity_values = [] # save the last 10 humidity values
        self.temperature_threshold = 25
        self.humidity_threshold = 50

        self.last_solar_current_values = [] # save the last 10 solar current values
        self.solar_current_threshold = 0.5 # TODO: appropriate value

    def end_trip(self) -> None:
        print('Trip ended', flush=True)
        self.onTrip = False

        # if the user returns from his trip start the planner again
        print('Planner started because Trip ended', flush=True)
        planner_thread = Thread(target=self.get_plan)
        planner_thread.start()

    def start_trip(self) -> None:
        #self.mqtt_client.publish('/charging-controller/stop-charging', '', qos=2) # stop charging the battery
        self.mqtt_client.publish('/iot-backend/charging-status', False, qos=2, retain=True)
        self.onTrip = True
        print('Trip started', flush=True)

    def set_schedule_use(self, schedule_use) -> None:
        print('Setting ScheduleUse to', schedule_use, flush=True)

        # if the schedule use changes, start the planner again
        if self.ScheduleUse != schedule_use:
            if not self.onTrip:
                print('Planner started because ScheduleUse changed', flush=True)
                planner_thread = Thread(target=self.get_plan)
                planner_thread.start()
        
        self.ScheduleUse = schedule_use

    def add_dht_sensor_data(self, temperature, humidity) -> None:
        print('Adding DHT sensor data', flush=True)

        # add the new temperature and humidity values to the list
        self.last_temperature_values.append(temperature)
        self.last_humidity_values.append(humidity)

        # if the list is longer than 10 values, remove the first value
        if len(self.last_temperature_values) > 10:
            self.last_temperature_values.pop(0)
        if len(self.last_humidity_values) > 10:
            self.last_humidity_values.pop(0)

        # calculate the average temperature and humidity
        avg_temperature = sum(self.last_temperature_values) / len(self.last_temperature_values)
        avg_humidity = sum(self.last_humidity_values) / len(self.last_humidity_values)

        old_temperature = self.temperature
        old_humidity = self.humidity
        self.temperature = "high" if avg_temperature > self.temperature_threshold else "low"
        self.humidity = "high" if avg_humidity > self.humidity_threshold else "low"

        # if the temperature or humidity changes, start the planner again
        if old_temperature != self.temperature or old_humidity != self.humidity:
            if not self.onTrip:
                print('Planner started because temperature or humidity changed', flush=True)
                planner_thread = Thread(target=self.get_plan)
                planner_thread.start()

    # we dont get this data yet
    def add_solar_panel_data(self, current) -> None:
        print('Adding solar panel data', flush=True)

        # add the new current value to the list
        self.last_solar_current_values.append(current)

        # if the list is longer than 10 values, remove the first value
        if len(self.last_solar_current_values) > 10:
            self.last_solar_current_values.pop(0)

        # calculate the average current
        avg_current = sum(self.last_solar_current_values) / len(self.last_solar_current_values)

        # if the current changes, start the planner again
        if avg_current > self.solar_current_threshold:
            if not self.onTrip:
                print('Planner started because solar current changed', flush=True)
                planner_thread = Thread(target=self.get_plan)
                planner_thread.start()

    # state_battery: Whether the battery needs to be charged or not (need-charge fullycharge)
    # temperature, humidity: Temperature and humidity recived from the sensors (low high)
    # connected_battery: Whether battery connected to the system (true false)
    # BatteryN: Battery to be charged, multiple cars can be connected (battery1  battery2  battery3)
    # ScheduleUse: Whether we want to use the car in the near future or not (true false)
    # SolarPanel: Whether the solar pannel is returning energy or not -> determine whether to use solar energy or not (true false)
    def get_plan(self):
        print('Getting plan with parameters: state_battery =', self.state_battery, ', temperature =', self.temperature, ', humidity =', self.humidity, ', connected_battery =', self.connected_battery, ', BatteryN =', self.BatteryN, ', ScheduleUse =', self.ScheduleUse, ', SolarPanel =', self.SolarPanel, flush=True)

        #print('Problem: ', problem.format(state_battery = self.state_battery, temperature = self.temperature,
        #                                 humidity = self.humidity, connected_battery = self.connected_battery, 
        #                                 BatteryN = self.BatteryN, ScheduleUse = self.ScheduleUse, SolarPanel = self.SolarPanel), flush=True)

        #TODO: add error handling
        query = {"domain": domain, 
                 "problem": problem.format(state_battery = self.state_battery, temperature = self.temperature,
                                         humidity = self.humidity, connected_battery = self.connected_battery, 
                                         BatteryN = self.BatteryN, ScheduleUse = self.ScheduleUse, SolarPanel = self.SolarPanel)}

        # Send job request to solve endpoint
        solve_request_url = requests.post(f"{self.base_url}/package/delfi/solve", json=query)

        # Query the result in the job
        celery_result = requests.post(self.base_url + solve_request_url.json()['result'])
        while celery_result.json()['status'] == 'PENDING':  
            celery_result = requests.post(self.base_url + solve_request_url.json()['result'])
            time.sleep(0.5)

        plan = celery_result.json()['result']['output']['plan']
        print('Got plan:', plan, flush=True)
        print('type of plan:', type(plan), flush=True) 
        
        # Execute the plan
        plan = plan.split("\n")
        # remove comments and empty lines
        plan = [action for action in plan if action and not action.startswith(";")]
        # remove () from actions
        plan = [action.replace("(", "").replace(")", "") for action in plan]

        charge_speed_plan = plan[0].split(" ")[0]
        print('charge_speed_plan:', charge_speed_plan, flush=True)

        charge_type = plan[1].split(" ")[0]
        print('charge_type:', charge_type, flush=True)

        # publish the plan to the MQTT broker
        charge_speed = 0
        if charge_speed_plan == 'fast-charge-transition':
            charge_speed = 2250
        elif charge_speed_plan == 'medium-charge-transition':
            charge_speed = 1500
        elif charge_speed_plan == 'slow-charge-transition':
            charge_speed = 750

        msg = {'charging_speed_mw': int(charge_speed)}
        current_plan = {'charge_speed': charge_speed_plan, 'charge_type': charge_type}
        if not self.charging:
            print('Starting charging with speed, msg: ', msg, flush=True)
            self.mqtt_client.publish('/charging-controller/start-charging', json.dumps(msg), qos=2)
            self.mqtt_client.publish('/iot-backend/charging-status', True, qos=2, retain=True)
            self.mqtt_client.publish('/iot-backend/current-plan', json.dumps(current_plan), qos=2, retain=True)
            self.charging = True
        else:
            print('Changing charging speed to, msg: ', msg, flush=True)
            self.mqtt_client.publish('/charging-controller/change-charging-speed', json.dumps(msg), qos=2)
            self.mqtt_client.publish('/iot-backend/charging-status', True, qos=2, retain=True)
            self.mqtt_client.publish('/iot-backend/current-plan', json.dumps(current_plan), qos=2, retain=True)
