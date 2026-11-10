from gitcoach.explain import cache, ollama, prompts, templates
from gitcoach.models import Explanation


def explain(rule_id: str, title: str, facts: dict) -> Explanation:
    key = cache.make_key(rule_id, facts)
    cached = cache.get(key)
    if cached is not None:
        return Explanation(text=cached, llm_used=True)

    messages = prompts.build_messages(title, facts)
    try:
        text = ollama.ask(messages)
    except ollama.OllamaError:
        return Explanation(text=templates.fallback(rule_id, facts), llm_used=False)

    cache.set(key, text)
    return Explanation(text=text, llm_used=True)
