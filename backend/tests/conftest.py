import os

# Must be set before app.main is imported (it builds a default app at import time).
os.environ["DATABASE_URL"] = ":memory:"
os.environ["QLOO_API_KEY"] = ""
os.environ["STATIC_DIR"] = ""
os.environ["GEMINI_API_KEY"] = ""
os.environ["GOOGLE_API_KEY"] = ""
