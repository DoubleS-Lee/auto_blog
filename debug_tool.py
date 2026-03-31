from tools import NaverDataLabTool
import json

t = NaverDataLabTool()
print("name:", repr(t.name))

try:
    schema = t.openai_schema
    print("openai_schema:", json.dumps(schema, indent=2, ensure_ascii=False))
except Exception as e:
    print("openai_schema error:", e)
