import requests

key_test = "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"
key_feeder = "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"

models = [
    "minimaxai/minimax-m3",
    "meta/llama-3.3-70b-instruct",
    "nvidia/llama-3.1-nemotron-70b-instruct"
]

for name, key in [("TEST (RAG)", key_test), ("FEEDER (Ingest)", key_feeder)]:
    print(f"\n--- Probando Key: {name} ---")
    for m in models:
        try:
            r = requests.post(
                "https://integrate.api.nvidia.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Accept": "application/json"},
                json={
                    "model": m,
                    "messages": [{"role": "user", "content": "Responde OK"}],
                    "temperature": 0.1,
                    "max_tokens": 10
                },
                timeout=10
            )
            print(f"  Modelo [{m}]: HTTP {r.status_code} -> {r.text[:120]}")
        except Exception as e:
            print(f"  Modelo [{m}]: Error {e}")
