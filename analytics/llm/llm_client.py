"""Setup LLM (Fase 4) -- cliente minimo para Groq.

Groq elegido sobre Azure OpenAI (no requiere aprovisionar ningun recurso) y
Ollama local (no depende de que la VM del proyecto este encendida) -- ver
analytics/contexto.md para el porque.

`llama-3.1-70b-versatile` (el modelo que sugeria el plan original) ya no
existe en Groq -- se sustituyo por `openai/gpt-oss-120b`, comprobado contra
la API real (`client.models.list()`) antes de usarlo.
"""

import os

from dotenv import load_dotenv
from groq import Groq

load_dotenv(override=True)

DEFAULT_MODEL = "openai/gpt-oss-120b"


class LLMClient:
    def __init__(self, model: str = DEFAULT_MODEL):
        self.model = model
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))

    def complete(self, prompt: str, temperature: float = 0.4, max_tokens: int = 1200) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content
