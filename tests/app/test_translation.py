from app.translation import build_translation_prompt, translate_to_spanish


def test_build_translation_prompt_embeds_the_text():
    prompt = build_translation_prompt("Great villa, very clean.")
    assert "Great villa, very clean." in prompt
    assert "español" in prompt


def test_translate_to_spanish_returns_stripped_client_response(monkeypatch):
    class FakeClient:
        def __init__(self):
            self.received_prompt = None

        def complete(self, prompt, temperature, max_tokens):
            self.received_prompt = prompt
            return "  Gran villa, muy limpia.  "

    monkeypatch.setattr("app.translation.LLMClient", FakeClient)
    translate_to_spanish.clear()

    result = translate_to_spanish("Great villa, very clean.")

    assert result == "Gran villa, muy limpia."
