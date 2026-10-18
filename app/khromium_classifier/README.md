# Khromium classifier

A small companion for the in-browser classifier. It uses the same system prompt as `components/khromium/system_prompt.cc` so a DOM snippet can be classified without rebuilding Chromium.

The default path is local heuristics. It does not need an API key. Live mode calls OpenAI or xAI Grok.

## Run

From this directory, with Python 3.10 or newer and no extra packages:

```bash
python3 -m khromium_classifier serve --port 8765
```

Open http://127.0.0.1:8765 and paste HTML.

Classify a file from the shell:

```bash
python3 -m khromium_classifier classify --html snippet.html
```

Live model calls:

```bash
export KHROMIUM_OPENAI_API_KEY=...
python3 -m khromium_classifier classify --html snippet.html --live --provider openai

export KHROMIUM_XAI_API_KEY=...
python3 -m khromium_classifier classify --html snippet.html --live --provider grok
```

The key is read from the environment and sent only as an `Authorization` header. It is not written to logs and it is not accepted from the web form.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

The live-call test mocks HTTP. No key and no network are required.
