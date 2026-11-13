import threading

import pytest
from fastapi.testclient import TestClient

from everything_agent import envfile, paths
from everything_agent.runtime import Runtime
from everything_agent.server.api import COOKIE, build_app

DESKTOP = {"Authorization": "Bearer desk-token"}
LOCAL = "http://127.0.0.1"


class NoRobot:
    input_rate = 16000
    media_lock = threading.Lock()
    asleep = threading.Event()
    out = None


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("EVERYTHING_AGENT_DESKTOP_TOKEN", "desk-token")
    runtime = Runtime(NoRobot())
    with TestClient(build_app(runtime), base_url=LOCAL) as c:
        c.runtime = runtime
        yield c


def test_everything_needs_signing_in(client):
    assert client.get("/api/status").status_code == 401
    assert client.get("/api/auth").json() == {"signed_in": False, "pin_set": False}


def test_the_desktop_window_signs_in_with_its_token(client):
    r = client.get("/api/status", headers=DESKTOP)
    assert r.status_code == 200 and r.json()["session"] == "starting"
    assert client.get("/api/status", headers={"Authorization": "Bearer nope"}).status_code == 401


def test_first_visitor_sets_the_pin_then_everyone_needs_it(client):
    assert client.post("/api/auth/pin", json={"pin": "1234"}).status_code == 400
    assert client.post("/api/auth/pin", json={"pin": "432198"}).status_code == 200
    assert client.get("/api/status").status_code == 200

    other = TestClient(client.app, base_url=LOCAL)
    assert other.get("/api/status").status_code == 401
    assert other.post("/api/auth/pin", json={"pin": "999999"}).status_code == 401
    assert other.post("/api/auth/login", json={"pin": "000000"}).status_code == 401
    assert other.post("/api/auth/login", json={"pin": "432198"}).status_code == 200
    assert COOKIE in other.cookies


def test_changing_the_pin_in_a_browser_needs_the_current_one(client):
    client.post("/api/auth/pin", json={"pin": "432198"})
    assert client.post("/api/auth/pin", json={"pin": "555555"}).status_code == 403
    assert client.post("/api/auth/pin", json={"pin": "555555", "current": "432198"}).status_code == 200
    assert client.post("/api/auth/pin", headers=DESKTOP, json={"pin": "666666"}).status_code == 200


def test_the_desktop_app_sets_its_first_pin_only_from_its_window(monkeypatch):
    monkeypatch.setenv("EVERYTHING_AGENT_DESKTOP", "1")
    monkeypatch.setenv("EVERYTHING_AGENT_DESKTOP_TOKEN", "desk-token")
    with TestClient(build_app(Runtime(NoRobot())), base_url=LOCAL) as c:
        assert c.post("/api/auth/pin", json={"pin": "432198"}).status_code == 403
        assert c.post("/api/auth/pin", headers=DESKTOP, json={"pin": "432198"}).status_code == 200


def test_other_sites_and_unknown_host_names_are_turned_away(client):
    assert client.get("/api/auth", headers={"Host": "attacker.example"}).status_code == 421
    assert client.get("/api/auth", headers={"Host": "localhost:8042"}).status_code == 200
    evil = {"Origin": "http://attacker.example", **DESKTOP}
    assert client.post("/api/mute", headers=evil, json={"mic": True}).status_code == 403
    assert client.post("/api/auth/login", content=b"x" * 300_000, headers={"Content-Type": "application/json"}).status_code == 413


def test_too_many_wrong_pins_lock_everyone_out_for_a_while():
    from everything_agent.server.auth import Auth, LockedOut, hash_pin

    auth = Auth(hash_pin("432198"), "", "", None)
    for i in range(30):
        assert auth.login("000000", f"10.0.0.{i}") is None
    with pytest.raises(LockedOut):
        auth.login("432198", "10.0.1.1")


def test_settings_hide_secrets_and_keep_them_when_left_blank(client):
    r = client.post("/api/settings", headers=DESKTOP, json={"values": {"CARTESIA_API_KEY": "sk_car_1234567890", "LLM_MODEL": "m1"}})
    assert r.status_code == 200
    fields = {f["key"]: f for f in client.get("/api/settings", headers=DESKTOP).json()["fields"]}
    assert fields["CARTESIA_API_KEY"]["value"] == "••••••••7890" and fields["CARTESIA_API_KEY"]["is_set"]
    assert fields["LLM_MODEL"]["value"] == "m1"

    client.post("/api/settings", headers=DESKTOP, json={"values": {"CARTESIA_API_KEY": "", "LLM_MODEL": "m2"}})
    saved = envfile.read_values(paths.env_path())
    assert saved["CARTESIA_API_KEY"] == "sk_car_1234567890" and saved["LLM_MODEL"] == "m2"
    assert client.post("/api/settings", headers=DESKTOP, json={"values": {"WEB_PIN": "1"}}).status_code == 400


def test_mute_and_conversation(client):
    assert client.post("/api/mute", headers=DESKTOP, json={"mic": True}).json() == {"mic": True, "speaker": False}
    assert client.get("/api/status", headers=DESKTOP).json()["mic_muted"] is True
    assert client.get("/api/conversation", headers=DESKTOP).json() == {"messages": []}
    assert client.post("/api/say", headers=DESKTOP, json={"text": "hi"}).status_code == 503


def test_live_feed_checks_the_token_sent_first(client):
    with client.websocket_connect("/api/events", headers={"Host": "127.0.0.1"}) as ws:
        ws.send_json({"token": "desk-token"})
        first = ws.receive_json()
        assert first["type"] == "state" and first["session"] == "starting"
    with client.websocket_connect("/api/events", headers={"Host": "127.0.0.1"}) as ws:
        ws.send_json({"token": "wrong"})
        with pytest.raises(Exception):
            ws.receive_json()


def test_robot_model_paths_cant_escape(client):
    assert client.get("/robot/../settings.py").status_code == 404
    assert client.get("/robot/assets/../../x").status_code == 404
