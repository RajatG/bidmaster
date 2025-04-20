import json
import copy

# Your sample sensor data (as a Python dictionary)
sample_data = {
    "vehicle_sensors": {
        "gps": [37.7749, -122.4194],
        "camera_left": "PLACEHOLDER_LEFT",
        "camera_right": "PLACEHOLDER_RIGHT",
        "lidar_points": [
            {"distance": 3.2, "angle": 45},
            {"distance": 5.0, "angle": 60}
        ],
        "radar_objects": [
            {"distance": 15, "confidence": 0.8, "position": [100, 200], "velocity": 5}
        ],
        "ultrasonic_readings": [
            {"distance": 1.5}
        ],
        "acceleration": [0.1, 0.0, 0.0],
        "gyro": [0.01, 0.02, 0.0],
        "odometry": 120.5
    },
    "map_data": {
        "hd_map": {
            "nodes": {
                "1": [0, 0],
                "2": [10, 0],
                "3": [10, 10],
                "4": [0, 10]
            },
            "road_network": {
                "1": ["2"],
                "2": ["3"],
                "3": ["4"],
                "4": ["1"]
            },
            "points_of_interest": []
        },
        "roads": [
            {"id": "road1", "geometry": [[0, 0], [10, 0]]},
            {"id": "road2", "geometry": [[10, 0], [10, 10]]}
        ],
        "traffic_lights": [
            {"id": "tl1", "position": [5, 0], "state": "green"}
        ],
        "speed_limits": [30, 50]
    },
    "traffic_data": {
        "flow": {"road1": "moderate", "road2": "heavy"},
        "incidents": []
    },
    "weather_data": {
        "condition": "clear",
        "visibility": 1000
    }
}

# Generate a list with 1,000 entries
entries = []
for i in range(1000):
    # Use deepcopy to ensure each entry is an independent copy of the sample_data
    entry = copy.deepcopy(sample_data)
    # Optionally, you could modify entry here (for example, vary odometry or add a timestamp)
    entry["vehicle_sensors"]["odometry"] += i  # slight variation for each entry
    entries.append(entry)

# Save the generated entries to a JSON file
with open("sensor_data_large.json", "w") as f:
    json.dump(entries, f, indent=2)

print("Generated sensor_data_large.json with 1000 entries.")
