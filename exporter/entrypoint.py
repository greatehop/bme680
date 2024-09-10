import bme680
import os
import time
from flask import Flask, Response
from prometheus_client import Counter, Gauge, start_http_server, generate_latest

i2c_address = 0x77
location = 'home'
content_type = 'text/plain; version=0.0.4; charset=utf-8'

if 'I2C_ADDRESS' in os.environ:
    i2c_address = os.environ['I2C_ADDRESS']
if 'LOCATION' in os.environ:
    location = os.environ['LOCATION']

# setup BME680 sensor (once)
sensor = bme680.BME680(i2c_address)

sensor.set_humidity_oversample(bme680.OS_2X)
sensor.set_pressure_oversample(bme680.OS_4X)
sensor.set_temperature_oversample(bme680.OS_8X)
sensor.set_filter(bme680.FILTER_SIZE_3)

sensor.set_gas_status(bme680.ENABLE_GAS_MEAS)
sensor.set_gas_heater_temperature(320)
sensor.set_gas_heater_duration(150)
sensor.select_gas_heater_profile(0)


# read sensor data (repeatedly)
def get_measurements():
    if not sensor.get_sensor_data() or not sensor.data.heat_stable:
        time.sleep(5)

    response = {"temperature": sensor.data.temperature,
                "humidity": sensor.data.humidity,
                "pressure": sensor.data.pressure,
                "gas_resistance": sensor.data.gas_resistance}
    return response


def calculate_air_quality(data):
    # calculate humidity contribution to IAQ index
    humidity = data['humidity']
    hum_reference = 40
    if 38 <= humidity <= 42:
        hum_score = 0.25 * 100  # Humidity +/-5% around optimum
    else:
        # sub-optimal
        if humidity < 38:
            hum_score = 0.25 / hum_reference * humidity * 100
        else:
            hum_score = ((-0.25/(100-hum_reference)*humidity) + 0.416666) * 100

    # calculate gas contribution to IAQ index
    gas_reference = 250000
    gas_lower_limit = 5000  # bad air quality limit
    gas_upper_limit = 50000  # good air quality limit

    if gas_reference > gas_upper_limit:
        gas_reference = gas_upper_limit
    if gas_reference < gas_lower_limit:
        gas_reference = gas_lower_limit

    gas_score = (
            (0.75 / (gas_upper_limit - gas_lower_limit) * gas_reference
             - (gas_lower_limit * (0.75 / (gas_upper_limit - gas_lower_limit))))
            * 100)

    return hum_score + gas_score


def calculate_air_quality_v2(data):

    # calculate humidity contribution to IAQ index
    humidity = data['humidity']
    hum_reference = 40
    if 38 <= humidity <= 42:
        hum_score = 0.25 * 100  # Humidity +/-5% around optimum
    else:
        # sub-optimal
        if humidity < 38:
            hum_score = 0.25 / hum_reference * humidity * 100
        else:
            hum_score = ((-0.25 / (
                        100 - hum_reference) * humidity) + 0.416666) * 100

    # calculate gas contribution to IAQ index
    #gas_reference = 250000
    gas_reference = data['gas_resistance']
    gas_lower_limit = 5000  # bad air quality limit
    gas_upper_limit = 50000  # good air quality limit

    if gas_reference > gas_upper_limit:
        gas_reference = gas_upper_limit
    if gas_reference < gas_lower_limit:
        gas_reference = gas_lower_limit

    gas_score = (
            (0.75 / (gas_upper_limit - gas_lower_limit) * gas_reference
             - (gas_lower_limit * (0.75 / (
                                gas_upper_limit - gas_lower_limit))))
            * 100)

    return hum_score + gas_score


# configure webapp
app = Flask(__name__)

current_temperature = Gauge(
        'current_temperature',
        'current temperature in degree celsius, this is a gauge as the value '
        'can increase or decrease',
        ['location']
)

current_humidity = Gauge(
        'current_humidity',
        'current humidity as percentage, this is a gauge as the value can '
        'increase or decrease',
        ['location']
)

current_air_pressure = Gauge(
        'current_air_pressure',
        'current air pressure in hPa, this is a gauge as the value can increase'
        ' or decrease',
        ['location']
)

current_gas_resistance = Gauge(
        'current_gas_resistance',
        'current gas resistance in ohm, this is a gauge as the value can '
        'increase or decrease',
        ['location']
)

current_air_quality = Gauge(
        'current_air_quality',
        'current air_quality, can increase or decrease',
        ['location']
)

current_air_quality_v2 = Gauge(
        'current_air_quality_v2',
        'current air_quality v2, can increase or decrease',
        ['location']
)


@app.route('/metrics')
def metrics():

    metrics = get_measurements()
    air_quality = calculate_air_quality(metrics)
    air_quality_v2 = calculate_air_quality_v2(metrics)

    current_air_quality.labels(location).set(air_quality)
    current_air_quality_v2.labels(location).set(air_quality_v2)
    current_temperature.labels(location).set(metrics['temperature'])
    current_humidity.labels(location).set(metrics['humidity'])
    current_air_pressure.labels(location).set(metrics['pressure'])
    current_gas_resistance.labels(location).set(metrics['gas_resistance'])
    return Response(generate_latest(), mimetype=content_type)


@app.route('/')
def root():
    return ("<html>"
            "<head><title>BME680 Exporter</title>"
            "<style type=\"text/css\"></style></head>"
            "<body>"
            "<h1>BME680 Exporter</h1><p><a href=\"/metrics\">Metrics</a></p>"
            "</body></html>")


if __name__ == '__main__':
    from waitress import serve
    serve(app, host='0.0.0.0', port=9100)
