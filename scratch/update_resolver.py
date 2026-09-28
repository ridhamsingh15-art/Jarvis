with open('core/tool_intelligence/resolver.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace('"read_file": ("file", "open_file")', '"read_file": ("file", "read_file")')
text = text.replace('"read": "open_file"', '"read": "read_file"')

with open('core/tool_intelligence/resolver.py', 'w', encoding='utf-8', newline='') as f:
    f.write(text)
print("Updated resolver.py")
