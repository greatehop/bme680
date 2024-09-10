import os

from flask import Flask, Response
from prometheus_client import Counter, Gauge, start_http_server, generate_latest


location = 'home'
content_type = 'text/plain; version=0.0.4; charset=utf-8'

if 'LOCATION' in os.environ:
    location = os.environ['LOCATION']


# read sensor data (repeatedly)
def get_measurements():
    response = {"uptime": get_uptime(),
                "pi_temprature": get_pi_temprature()}
    return response


def get_uptime():
    pass


def get_pi_temprature():
    pass


# configure webapp
app = Flask(__name__)

pi_temprature = Gauge(
        'pi_temprature',
        'current pi_temprature in degree celsius, this is a gauge as the value '
        'can increase or decrease',
        ['location']
)

uptime = Gauge(
        'uptime',
        'current uptime as percentage, this is a gauge as the value can '
        'increase or decrease',
        ['location']
)


@app.route('/metrics')
def metrics():

    metrics = get_measurements()

    uptime.labels(location).set(metrics['uptime'])
    pi_temprature.labels(location).set(metrics['pi_temprature'])

    return Response(generate_latest(), mimetype=content_type)


@app.route('/')
def root():
    # TODO: redirect to /metrics
    pass


if __name__ == '__main__':
    from waitress import serve
    serve(app, host='0.0.0.0', port=9101)
