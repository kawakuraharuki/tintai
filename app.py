from flask import Flask, render_template, jsonify
from csv_manager import CSVManager
import logging

app = Flask(__name__)
csv_manager = CSVManager()

# Disable Flask logging to keep console clean
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

@app.route('/')
def index():
    properties = csv_manager.get_all_properties()
    return render_template('index.html', properties=properties)

@app.route('/api/properties')
def get_properties():
    properties = csv_manager.get_all_properties()
    return jsonify(properties)

if __name__ == '__main__':
    print("Starting Web Server at http://localhost:8081")
    app.run(debug=True, host='0.0.0.0', port=8081)
