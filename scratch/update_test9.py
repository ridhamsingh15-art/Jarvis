with open('tests/test_result_grounding.py', 'r', encoding='utf-8') as f:
    text = f.read()

old_assert = '        assert "Permission denied" in resp_task.result'
new_assert = '        assert "step2.txt" in resp_task.result'

assert old_assert in text, "old_assert not found"
text = text.replace(old_assert, new_assert, 1)

with open('tests/test_result_grounding.py', 'w', encoding='utf-8', newline='') as f:
    f.write(text)
print("Updated test 9 in test_result_grounding.py")
