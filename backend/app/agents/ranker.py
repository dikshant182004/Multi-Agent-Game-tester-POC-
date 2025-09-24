from typing import List, Tuple
from collections import Counter

LANG_TOKENS = {"English", "हिन्दी"}
ACTION_TYPES = {
	"navigate", "select_language", "start_new_game", "wait_for_board",
	"click_tile_value", "click_two_tiles_sum", "random_clicks", "screenshot",
}

class RankerAgent:
	def rank(self, candidates: List[dict]) -> List[Tuple[dict, float]]:
		tag_counts = Counter(tag for c in candidates for tag in c.get("tags", []))
		seen_titles = set()
		scored: List[Tuple[dict, float]] = []
		for c in candidates:
			title = c.get("title", "")
			if title in seen_titles:
				score = -1
			else:
				seen_titles.add(title)
				steps = c.get("steps", [])
				ops = [s.split(":", 1)[0] for s in steps]
				unique_ops = len(set(ops) & ACTION_TYPES)
				lang_tags = [t for t in c.get("tags", []) if t in LANG_TOKENS]
				language_bonus = 1.5 if lang_tags else 0.0
				coverage_bonus = sum(1.0 / (1 + tag_counts[t]) for t in set(c.get("tags", [])))
				length_penalty = 0.0 if len(steps) <= 8 else (len(steps) - 8) * 0.1
				score = unique_ops + language_bonus + coverage_bonus - length_penalty
			scored.append((c, score))
		return sorted(scored, key=lambda x: x[1], reverse=True)
