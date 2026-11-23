"""Integration tests for the browser API and WebSocket game protocol."""
import importlib
import time

from fastapi.testclient import TestClient
import pytest

api = importlib.import_module('web.backend.app')


def until_type(ws, kind, phase=None, limit=12):
    for _ in range(limit):
        msg = ws.receive_json()
        if msg.get('type') == kind and (phase is None or msg.get('phase') == phase):
            return msg
    raise AssertionError(f'Never received {kind} / {phase}')


def join(ws, name, **kwargs):
    ws.send_json({'type': 'join', 'name': name, **kwargs})
    welcome = until_type(ws, 'welcome')
    state = until_type(ws, 'state')
    return welcome, state


def test_health_and_room_creation():
    with TestClient(api.app) as client:
        assert client.get('/health').json()['status'] == 'ok'
        assert client.get('/').json()['health'] == '/health'
        r = client.post('/api/rooms')
        assert r.status_code == 201
        data = r.json()
        assert len(data['room_code']) == 6
        assert len(data['host_token']) >= 32
        info = client.get('/api/rooms/' + data['room_code']).json()
        assert info['phase'] == 'lobby'
        assert info['question_count'] == 20
        assert client.get('/api/rooms/NOTHERE').status_code == 404


def test_host_player_scoring_chat_and_advance(monkeypatch):
    monkeypatch.setattr(api, 'RESULT_SECONDS', 0.25)
    monkeypatch.setattr(api, 'QUESTION_SECONDS', 0.6)
    with TestClient(api.app) as client:
        created = client.post('/api/rooms').json()
        code = created['room_code']
        with client.websocket_connect('/ws/' + code, headers={'origin': 'http://localhost:5173'}) as host:
            host_welcome, host_state = join(host, 'Alice', host_token=created['host_token'])
            assert host_welcome['is_host'] is True
            assert host_state['phase'] == 'lobby'
            with client.websocket_connect('/ws/' + code) as player:
                player_welcome, player_state = join(player, 'Bob')
                assert player_welcome['is_host'] is False
                assert len(player_state['players']) == 2
                assert len(until_type(host, 'state')['players']) == 2
                player.send_json({'type': 'host_action', 'action': 'start'})
                assert 'Only the room host' in until_type(player, 'error')['message']
                player.send_json({'type': 'chat', 'text': 'Hello everyone'})
                assert until_type(host, 'chat')['text'] == 'Hello everyone'
                assert until_type(player, 'chat')['name'] == 'Bob'
                host.send_json({'type': 'host_action', 'action': 'start'})
                first_host = until_type(host, 'state', 'question')
                first_player = until_type(player, 'state', 'question')
                assert first_host['question_index'] == 0
                assert first_player['question_index'] == 0
                assert 'correct_index' not in first_host['question']
                assert first_host['deadline'] is not None
                # Question 1 is FIFO -> queue -> option index 1.
                host.send_json({'type': 'answer', 'choice': 1})
                assert until_type(host, 'answer_ack')['choice'] == 1
                host_answered = until_type(host, 'state')
                assert host_answered['your_answer'] == 1
                assert 'correct_index' not in host_answered['question']
                until_type(player, 'state')
                player.send_json({'type': 'answer', 'choice': 0})
                assert until_type(player, 'answer_ack')['choice'] == 0
                result_host = until_type(host, 'state', 'results')
                result_player = until_type(player, 'state', 'results')
                assert result_host['result']['correct_index'] == 1
                assert result_host['question']['prompt'].startswith('Which data structure')
                assert result_player['your_answer'] == 0
                scores = {p['name']: p['score'] for p in result_host['players']}
                assert scores == {'Alice': 10, 'Bob': 0}
                second_host = until_type(host, 'state', 'question')
                second_player = until_type(player, 'state', 'question')
                assert second_host['question_index'] == 1
                assert second_player['question_index'] == 1
                host.send_json({'type': 'host_action', 'action': 'stop'})
                assert until_type(host, 'state', 'finished')['phase'] == 'finished'
                until_type(player, 'state', 'finished')
                host.send_json({'type': 'host_action', 'action': 'reset'})
                reset_state = until_type(host, 'state', 'lobby')
                assert all(p['score'] == 0 for p in reset_state['players'])
                until_type(player, 'state', 'lobby')


def test_duplicate_nickname_and_bad_host_key():
    with TestClient(api.app) as client:
        created = client.post('/api/rooms').json()
        code = created['room_code']
        with client.websocket_connect('/ws/' + code) as a:
            join(a, 'PlayerOne')
            with client.websocket_connect('/ws/' + code) as b:
                b.send_json({'type': 'join', 'name': 'playerone'})
                assert 'nickname is already' in until_type(b, 'error')['message']
            with client.websocket_connect('/ws/' + code) as c:
                c.send_json({'type': 'join', 'name': 'Other', 'host_token': 'invalid'})
                assert 'Invalid host key' in until_type(c, 'error')['message']


def test_session_rejoin_after_disconnect():
    with TestClient(api.app) as client:
        created = client.post('/api/rooms').json()
        code = created['room_code']
        with client.websocket_connect('/ws/' + code) as a:
            welcome, _ = join(a, 'ReconnectUser', host_token=created['host_token'])
        with client.websocket_connect('/ws/' + code) as a2:
            rejoined, state = join(a2, 'ReconnectUser', session_token=welcome['session_token'])
            assert rejoined['player_id'] == welcome['player_id']
            assert rejoined['is_host'] is True
            assert len(state['players']) == 1


def test_websocket_origin_rejected():
    with TestClient(api.app) as client:
        created = client.post('/api/rooms').json()
        with pytest.raises(Exception):
            with client.websocket_connect('/ws/' + created['room_code'], headers={'origin': 'https://malicious.example'}) as ws:
                ws.receive_json()


def test_player_leaves_and_nickname_is_reusable():
    with TestClient(api.app) as client:
        created = client.post('/api/rooms').json()
        code = created['room_code']
        with client.websocket_connect('/ws/' + code) as first:
            join(first, 'PlayerX')
            first.send_json({'type': 'leave'})
            # Server closes after processing the leave message.
            with pytest.raises(Exception):
                first.receive_json()
        with client.websocket_connect('/ws/' + code) as second:
            _, state = join(second, 'PlayerX')
            assert len(state['players']) == 1


def test_session_takeover_from_old_tab():
    with TestClient(api.app) as client:
        created = client.post('/api/rooms').json()
        code = created['room_code']
        with client.websocket_connect('/ws/' + code) as old:
            welcome, _ = join(old, 'RefreshPlayer')
            with client.websocket_connect('/ws/' + code) as new:
                new_welcome, state = join(new, 'RefreshPlayer', session_token=welcome['session_token'])
                assert new_welcome['player_id'] == welcome['player_id']
                assert state['players'][0]['connected'] is True
                assert len(state['players']) == 1


def test_host_leave_promotes_another_player():
    with TestClient(api.app) as client:
        created = client.post('/api/rooms').json()
        code = created['room_code']
        with client.websocket_connect('/ws/' + code) as host:
            join(host, 'Host', host_token=created['host_token'])
            with client.websocket_connect('/ws/' + code) as player:
                join(player, 'Friend')
                until_type(host, 'state')
                host.send_json({'type': 'leave'})
                with pytest.raises(Exception):
                    host.receive_json()
                promoted = until_type(player, 'host_promoted')
                assert promoted['type'] == 'host_promoted'
                state = until_type(player, 'state')
                assert state['players'][0]['is_host'] is True
                player.send_json({'type': 'host_action', 'action': 'start'})
                assert until_type(player, 'state', 'question')['phase'] == 'question'
