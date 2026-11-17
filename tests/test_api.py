import json
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import api
import dashboard
import sensor_simulator


SAMPLE_MEASUREMENT = {
    "Timestamp": "2026-11-01T00:00:00Z",
    "Turbine_ID": "WT-001",
    "Wind_Speed_m_s": 7.31,
    "Wind_Direction_deg": 221.9,
    "Ambient_Temp_C": 4.8,
    "Rotor_Speed_RPM": 8.06,
    "Power_Output_kW": 313.4,
    "Expected_Power_kW": 328.4,
    "Gearbox_Temp_C": 40.8,
    "Generator_Temp_C": 49.1,
    "Vibration_mm_s": 1.87,
    "Alarm_Flag": False,
    "Status": "OK",
    "Maintenance_Required": "NO",
}


class SensorApiTests(unittest.TestCase):
    def test_api_receives_measurement_and_saves_it_to_mongodb(self) -> None:
        saved: dict = {}

        def insert_one(document: dict) -> SimpleNamespace:
            saved.update(document)
            return SimpleNamespace(inserted_id="received-id")

        measurement = api.SensorMeasurement.model_validate(SAMPLE_MEASUREMENT)
        with patch(
            "api.get_collection",
            return_value=SimpleNamespace(insert_one=insert_one),
        ):
            response = api.create_measurement(measurement)

        self.assertEqual(response["id"], "received-id")
        self.assertEqual(saved, SAMPLE_MEASUREMENT)

    def test_api_returns_measurements_from_mongodb(self) -> None:
        document = {"_id": "mongo-id", **SAMPLE_MEASUREMENT}
        cursor = MagicMock()
        cursor.sort.return_value = cursor
        cursor.limit.return_value = cursor
        cursor.__iter__.return_value = iter([document.copy()])
        collection = MagicMock()
        collection.find.return_value = cursor

        with patch("api.get_collection", return_value=collection):
            response = api.list_measurements(limit=100)

        self.assertEqual(
            response,
            [{"id": "mongo-id", **SAMPLE_MEASUREMENT}],
        )
        collection.find.assert_called_once_with({})

    def test_dashboard_fetches_measurements_from_api(self) -> None:
        response = MagicMock()
        response.read.return_value = json.dumps(
            [{"id": "mongo-id", **SAMPLE_MEASUREMENT}]
        ).encode()
        response.__enter__.return_value = response

        with patch("dashboard.urlopen", return_value=response) as urlopen:
            measurements = dashboard.load_measurements(
                "http://localhost:8000/measurements", 500
            )

        self.assertEqual(
            measurements,
            [{"id": "mongo-id", **SAMPLE_MEASUREMENT}],
        )
        urlopen.assert_called_once_with(
            "http://localhost:8000/measurements?limit=500", timeout=10
        )
        dashboard.load_measurements.clear()

    def test_simulator_generates_and_posts_all_three_turbines(self) -> None:
        sent_records: list[dict] = []

        def receive_request(request, timeout):
            self.assertEqual(request.full_url, "http://localhost:8000/measurements")
            self.assertEqual(request.get_method(), "POST")
            self.assertEqual(timeout, 10)
            record = json.loads(request.data)
            api.SensorMeasurement.model_validate(record)
            sent_records.append(record)
            response = MagicMock()
            response.status = 201
            response.__enter__.return_value = response
            return response

        with patch("sensor_simulator.urlopen", side_effect=receive_request):
            sent = sensor_simulator.simulate(
                "http://localhost:8000/measurements",
                interval=0,
                repeat=False,
                limit=0,
            )

        self.assertEqual(sent, 3)
        self.assertEqual(
            [record["Turbine_ID"] for record in sent_records],
            ["WT-001", "WT-002", "WT-003"],
        )
        self.assertTrue(all(record["Timestamp"] for record in sent_records))


if __name__ == "__main__":
    unittest.main()
