from unittest.mock import Mock

import pytest
import requests

from backend.services import noaa


@pytest.mark.parametrize(
    ("value", "expected"),
    [("12.5", 12.5), ("0", 0.0), ("invalid", None), (None, None)],
)
def test_safe_float(value, expected):
    assert noaa._safe_float(value) == expected


def test_latest_observation_returns_last_record(monkeypatch):
    records = [{"v": "10"}, {"v": "15"}]
    fetch = Mock(return_value={"data": records})
    monkeypatch.setattr(noaa, "_get_json", fetch)

    assert noaa.coops_latest("123", "water_temperature") == records[-1]
    assert fetch.call_args.kwargs["params"]["station"] == "123"


def test_latest_observation_handles_empty_data(monkeypatch):
    monkeypatch.setattr(noaa, "_get_json", Mock(return_value={"data": []}))

    assert noaa.coops_latest("123", "wind") is None


def test_missing_station_does_not_request_data(monkeypatch):
    fetch = Mock()
    monkeypatch.setattr(noaa, "_get_json", fetch)

    result = noaa.get_coops_station_conditions(None)

    assert result["available"] is False
    assert result["observations"] == {}
    fetch.assert_not_called()


def test_http_failure_is_propagated(monkeypatch):
    response = Mock()
    response.raise_for_status.side_effect = requests.HTTPError("Unavailable")
    monkeypatch.setattr(noaa.requests, "get", Mock(return_value=response))

    with pytest.raises(requests.HTTPError):
        noaa._get_json("https://example.com")

    response.json.assert_not_called()


def test_extract_risk_signals_handles_missing_forecasts():
    result = noaa.extract_risk_signals({})

    assert result["max_forecast_wind_mph"] is None
    assert result["active_alerts"] == []


def test_extract_risk_signals_combines_forecasts():
    snapshot = {
        "nws": {
            "origin": {
                "hourly": [{"windSpeed": "10 mph"}],
                "alerts": [{"event": "Strong wind"}],
            },
            "destination": {
                "hourly": [{"windSpeed": "20 mph"}],
                "alerts": [],
            },
        }
    }

    result = noaa.extract_risk_signals(snapshot)

    assert result["max_forecast_wind_mph"] == 20.0
    assert result["active_alerts"] == [{"event": "Strong wind"}]
