import importlib
import json
import os
from typing import Any, Dict


ACTIONS = {"FOLD", "CALL", "CHECK", "RAISE", "ALL-IN"}


def _parse_env_file(path: str) -> str:
    if not os.path.exists(path):
        return ""

    with open(path, "r", encoding="utf-8") as env_file:
        for raw_line in env_file:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[len("export ") :].strip()
            if line.startswith("GEMINI_API_KEY="):
                value = line.split("=", 1)[1].strip().strip('"').strip("'")
                if value:
                    return value

    return ""


def load_api_key() -> str:
    """Load GEMINI_API_KEY from environment or local .env file."""
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if key:
        return key

    script_dir = os.path.dirname(os.path.abspath(__file__))
    candidate_paths = [
        os.path.join(script_dir, ".env"),
        os.path.join(os.getcwd(), ".env"),
        os.path.join(script_dir, ".env.local"),
        os.path.join(os.getcwd(), ".env.local"),
    ]

    seen = set()
    for path in candidate_paths:
        normalized = os.path.normpath(path)
        if normalized in seen:
            continue
        seen.add(normalized)
        value = _parse_env_file(path)
        if value:
            return value

    return ""


def save_api_key(api_key: str) -> None:
    """Persist GEMINI_API_KEY into .env next to this script."""
    key = (api_key or "").strip()
    if not key:
        return

    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    lines = []
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as env_file:
            lines = env_file.read().splitlines()

    updated = False
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("GEMINI_API_KEY=") or stripped.startswith("export GEMINI_API_KEY="):
            lines[idx] = f"GEMINI_API_KEY={key}"
            updated = True
            break

    if not updated:
        if lines and lines[-1].strip() != "":
            lines.append("")
        lines.append(f"GEMINI_API_KEY={key}")

    with open(env_path, "w", encoding="utf-8") as env_file:
        env_file.write("\n".join(lines).rstrip() + "\n")


class GeminiPokerAgent:
    def __init__(self, api_key: str, model_name: str = "gemini-2.5-flash") -> None:
        self.model_name = model_name
        self.api_key = api_key.strip() if api_key else ""
        self.client = None

        if not self.api_key:
            return

        try:
            from google import genai

            self.client = genai.Client(api_key=self.api_key)
        except Exception:
            self.client = None

    def _build_prompt(self, game_state: Dict[str, Any]) -> str:
        return f"""
Analyze the current game state and make the best +EV decision.

### CURRENT GAME STATE ###
- Your Hole Cards: {game_state.get('hole_cards')}
- Community Cards: {game_state.get('community_cards')}
- Your Stack: ${game_state.get('my_stack')}
- Pot Size: ${game_state.get('pot_size')}
- Amount to Call: ${game_state.get('amount_to_call')}
- Opponent Actions: {game_state.get('opponent_actions')}
- Number of Players at Table: {game_state.get('num_players')}
- Your Position at Table: {game_state.get('my_position')}

### INSTRUCTIONS ###
1. Evaluate hand strength, pot odds, and opponent behavior.
2. Choose one: \"FOLD\", \"CALL\", \"CHECK\", \"RAISE\", or \"ALL-IN\".
3. If RAISE, specify total raise amount as an integer. Otherwise, use 0.

### REQUIRED JSON OUTPUT FORMAT ###
{{
    \"reasoning\": \"Brief explanation here.\",
    \"action\": \"FOLD\" | \"CALL\" | \"CHECK\" | \"RAISE\" | \"ALL-IN\",
    \"raise_amount\": 0
}}
"""

    def _validate_decision(self, decision: Dict[str, Any], amount_to_call: int, my_stack: int) -> Dict[str, Any]:
        action = str(decision.get("action", "")).upper().strip()
        if action not in ACTIONS:
            action = "CHECK" if amount_to_call == 0 else "CALL"

        raise_amount = decision.get("raise_amount", 0)
        try:
            raise_amount = int(raise_amount)
        except (ValueError, TypeError):
            raise_amount = 0

        raise_amount = max(0, raise_amount)
        raise_amount = min(raise_amount, max(0, my_stack))

        if action in {"RAISE", "ALL-IN"} and raise_amount <= amount_to_call:
            if my_stack > amount_to_call:
                raise_amount = min(my_stack, amount_to_call + max(1, amount_to_call // 2))
            else:
                action = "CALL" if amount_to_call > 0 else "CHECK"
                raise_amount = 0

        if action in {"FOLD", "CALL", "CHECK"}:
            raise_amount = 0

        reasoning = str(decision.get("reasoning", "No reasoning provided.")).strip()
        if not reasoning:
            reasoning = "No reasoning provided."

        return {
            "action": action,
            "raise_amount": raise_amount,
            "reasoning": reasoning,
        }

    def _fallback_decision(self, game_state: Dict[str, Any], reason: str) -> Dict[str, Any]:
        amount_to_call = int(game_state.get("amount_to_call", 0) or 0)
        pot_size = int(game_state.get("pot_size", 0) or 0)
        my_stack = int(game_state.get("my_stack", 0) or 0)

        if amount_to_call <= 0:
            action = "CHECK"
        elif amount_to_call <= max(1, int(0.25 * max(1, pot_size))):
            action = "CALL"
        else:
            action = "FOLD"

        return {
            "action": action,
            "raise_amount": 0,
            "reasoning": f"Fallback strategy used ({reason}).",
        }

    def get_action(self, game_state: Dict[str, Any]) -> Dict[str, Any]:
        amount_to_call = int(game_state.get("amount_to_call", 0) or 0)
        my_stack = int(game_state.get("my_stack", 0) or 0)

        if not self.api_key or self.client is None:
            return self._fallback_decision(game_state, "Gemini client not available")

        prompt = self._build_prompt(game_state)

        try:
            types_module = importlib.import_module("google.genai.types")

            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types_module.GenerateContentConfig(
                    system_instruction="You are an expert No-Limit Texas Hold'em Poker AI. You ONLY respond in valid JSON.",
                    response_mime_type="application/json",
                    temperature=0.2,
                ),
            )

            raw = response.text if hasattr(response, "text") else "{}"
            decision = json.loads(raw)
            return self._validate_decision(decision, amount_to_call, my_stack)

        except Exception as exc:
            return self._fallback_decision(game_state, f"Gemini API error: {exc}")
