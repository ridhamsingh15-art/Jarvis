import pytest

from core.exceptions import ParseError
from core.parser import parse_json


def test_parser_extracts_first_object_when_later_json_snippet_follows():
    raw = (
        'Model response: {"tool":"file","action":"read_file","args":{"path":"first.txt"}}\n'
        'Extra diagnostic JSON: {"ignored":true}'
    )

    assert parse_json(raw) == {
        "tool": "file",
        "action": "read_file",
        "args": {"path": "first.txt"},
    }


def test_parser_preserves_nested_objects_and_array_structure():
    fence = chr(96) * 3
    raw = (
        fence + 'json\n'
        '[{"tool":"file","action":"write_file","args":'
        '{"path":"nested.json","content":"{\\"a\\": {\\"b\\": 1}}"}},'
        '{"tool":"system","action":"respond","args":{"message":"ok"}}]\n'
        + fence
    )

    parsed = parse_json(raw)
    assert isinstance(parsed, list)
    assert len(parsed) == 2
    assert parsed[0]["args"]["path"] == "nested.json"
    assert parsed[0]["args"]["content"] == '{"a": {"b": 1}}'


def test_parser_removes_thinking_block_before_selecting_json():
    raw = (
        '<think>{"ignored": true}</think>\n'
        '{"tool":"system","action":"respond","args":{"message":"visible"}}'
    )

    assert parse_json(raw)["args"]["message"] == "visible"


def test_parser_fails_closed_on_malformed_first_json_candidate():
    with pytest.raises(ParseError, match="Malformed JSON"):
        parse_json('Not valid JSON: {"outer": {"tool":"file"} broken} {"tool":"system"}')


def test_parser_reports_output_without_json():
    with pytest.raises(ParseError, match="No JSON found"):
        parse_json("No action was produced.")
