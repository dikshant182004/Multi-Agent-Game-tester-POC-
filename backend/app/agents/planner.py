import os
from typing import List, Optional

try:
    from langchain_openai import ChatOpenAI
    exists_openai = True
except Exception:
    exists_openai = False

class PlannerAgent:
    def __init__(self, openai_api_key: Optional[str] = None, use_llm: bool = False):
        self.use_llm = use_llm and exists_openai and openai_api_key is not None
        self.llm = None
        if self.use_llm:
            try:
                self.llm = ChatOpenAI(
                    api_key=openai_api_key,
                    model="gpt-4o-mini",
                    temperature=0.7
                )
            except Exception as e:
                print(f"Failed to initialize LLM: {e}")
                self.use_llm = False

    def generate_tests(self, min_count: int = 20) -> List[dict]:
        languages = ["English", "हिन्दी"]
        directions = ["h", "v", "d"]
        cases: List[dict] = []
        case_id = 1

        def add_case(title: str, steps: List[str], tags: List[str]):
            nonlocal case_id
            cases.append({
                "id": f"TC{case_id:03d}",
                "title": title,
                "goal": "Reach board and click adjacent tiles summing to 10",
                "steps": steps,
                "expected_outcome": "Board visible; two tiles summing to 10 clicked successfully",
                "tags": tags,
            })
            case_id += 1

        if self.use_llm and self.llm:
            # Use LLM to generate dynamic test case descriptions
            for lang in languages:
                for d in directions:
                    try:
                        prompt = (
                            f"Generate a test case description for a game where the user selects {lang} language "
                            f"and clicks two adjacent tiles (direction: {d.upper()}) summing to 10. "
                            "Provide a concise title and a list of steps as a JSON object."
                        )
                        response = self.llm.invoke(prompt)
                        # Assuming response is a stringified JSON
                        import json
                        llm_case = json.loads(response.content)
                        add_case(
                            title=llm_case.get("title", f"Sum 10 adjacent {d.upper()} ({lang}) - LLM"),
                            steps=llm_case.get("steps", [
                                "navigate:https://play.ezygamers.com/",
                                f"select_language:{lang}",
                                "start_new_game",
                                "wait_for_board",
                                f"click_adjacent_sum:10:{d}",
                                "screenshot",
                            ]),
                            tags=["sum10", d, lang, "llm"],
                        )
                    except Exception as e:
                        print(f"LLM generation failed: {e}")
                        # Fallback to deterministic case
                        add_case(
                            title=f"Sum 10 adjacent {d.upper()} ({lang}) - fallback",
                            steps=[
                                "navigate:https://play.ezygamers.com/",
                                f"select_language:{lang}",
                                "start_new_game",
                                "wait_for_board",
                                f"click_adjacent_sum:10:{d}",
                                "screenshot",
                            ],
                            tags=["sum10", d, lang, "fallback"],
                        )
        else:
            # Deterministic test case generation (original logic)
            for lang in languages:
                for d in directions:
                    # Baseline
                    add_case(
                        title=f"Sum 10 adjacent {d.upper()} ({lang}) - baseline",
                        steps=[
                            "navigate:https://play.ezygamers.com/",
                            f"select_language:{lang}",
                            "start_new_game",
                            "wait_for_board",
                            f"click_adjacent_sum:10:{d}",
                            "screenshot",
                        ],
                        tags=["sum10", d, lang],
                    )
                    # With small wait
                    add_case(
                        title=f"Sum 10 adjacent {d.upper()} ({lang}) - delayed",
                        steps=[
                            "navigate:https://play.ezygamers.com/",
                            f"select_language:{lang}",
                            "start_new_game",
                            "wait_for_board",
                            "wait_for:domcontentloaded",
                            f"click_adjacent_sum:10:{d}",
                            "screenshot",
                        ],
                        tags=["sum10", d, lang, "delayed"],
                    )
                    # Shuffle then attempt
                    add_case(
                        title=f"Sum 10 adjacent {d.upper()} ({lang}) - after shuffle",
                        steps=[
                            "navigate:https://play.ezygamers.com/",
                            f"select_language:{lang}",
                            "start_new_game",
                            "wait_for_board",
                            "shuffle",
                            f"click_adjacent_sum:10:{d}",
                            "screenshot",
                        ],
                        tags=["sum10", d, lang, "shuffle"],
                    )

        # Ensure at least min_count by duplicating with minor tags
        while len(cases) < max(min_count, 20):
            for lang in languages:
                for d in directions:
                    add_case(
                        title=f"Sum 10 adjacent {d.upper()} ({lang}) - variant {len(cases)+1}",
                        steps=[
                            "navigate:https://play.ezygamers.com/",
                            f"select_language:{lang}",
                            "start_new_game",
                            "wait_for_board",
                            f"click_adjacent_sum:10:{d}",
                            "screenshot",
                        ],
                        tags=["sum10", d, lang, "variant"],
                    )
                    if len(cases) >= max(min_count, 20):
                        break
                if len(cases) >= max(min_count, 20):
                    break

        return cases