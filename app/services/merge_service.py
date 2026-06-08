class MergeService:
    def __init__(self, match_threshold: int = 200):
        self.match_threshold = match_threshold

    def merge(self, all_chapters: list[list[dict]]) -> list[dict]:
        if not all_chapters:
            return []
        if len(all_chapters) == 1:
            return all_chapters[0]

        merged = list(all_chapters[0])

        for batch in all_chapters[1:]:
            if not batch:
                continue
            merged = self._merge_adjacent(merged, batch)

        return merged

    def _merge_adjacent(self, previous: list[dict], current: list[dict]) -> list[dict]:
        if not previous or not current:
            return previous + current

        last_prev = previous[-1]
        first_curr = current[0]

        if self._is_same_chapter(last_prev, first_curr):
            last_prev["content"] = self._concat_unique(
                last_prev["content"], first_curr["content"]
            )
            if not last_prev.get("title") or last_prev["title"] == "Texto":
                last_prev["title"] = first_curr.get("title", last_prev["title"])
            return previous + current[1:]

        return previous + current

    def _is_same_chapter(self, prev: dict, curr: dict) -> bool:
        prev_content = prev.get("content", "")[:self.match_threshold].strip().lower()
        curr_content = curr.get("content", "")[:self.match_threshold].strip().lower()
        return prev_content == curr_content

    def _concat_unique(self, base: str, addition: str) -> str:
        best_overlap = 0
        max_ov = min(len(base), len(addition), 300)

        for ov in range(max_ov, 20, -1):
            if base[-ov:].strip().lower() == addition[:ov].strip().lower():
                best_overlap = ov
                break

        if best_overlap > 0:
            return base + addition[best_overlap:]
        return base + "\n\n" + addition


merge_service = MergeService()
