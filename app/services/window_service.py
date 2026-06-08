from dataclasses import dataclass


@dataclass
class PageWindow:
    page_start: int
    pages: list[str]
    page_end: int


class WindowService:
    def __init__(self, window_size: int = 5, overlap: int = 1):
        self.window_size = window_size
        self.overlap = overlap

    def create_windows(self, pages: list[str]) -> list[PageWindow]:
        if not pages:
            return []

        windows = []
        step = self.window_size - self.overlap
        start = 0

        while start < len(pages):
            end = min(start + self.window_size, len(pages))
            window_pages = pages[start:end]
            windows.append(PageWindow(
                page_start=start,
                pages=window_pages,
                page_end=end - 1,
            ))
            if end >= len(pages):
                break
            start += step

        return windows


window_service = WindowService()
