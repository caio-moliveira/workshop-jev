"""System prompts por etapa, para o LLM no modo `native` (SPEC-12).

Ficam em config/prompts/<node>.md, escritos como se escreveria em produção. O Jev não usa
prompt: continua recebendo o NodeSpec. A saída do LLM segue o mesmo schema nos dois modos.
"""

from app.config import CONFIG_DIR
from app.tools import TOOLS

PROMPTS_DIR = CONFIG_DIR / "prompts"
DECISION_NODES = ("guardrail", "triage", "verify")


def load_prompt(node: str) -> str:
    text = (PROMPTS_DIR / f"{node}.md").read_text(encoding="utf-8").strip()
    # A lista de consultas vem do registro de tools: uma fonte só para o roteador e o código.
    tools = "\n".join(f"- `{t.name}`: {t.description}" for t in TOOLS.values())
    return text.replace("{tools}", tools)


def load_prompts() -> dict[str, str]:
    return {node: load_prompt(node) for node in DECISION_NODES}
