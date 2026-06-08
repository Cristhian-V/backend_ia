from app.services.window_service import WindowService


class TestWindowService:
    def test_empty_pages(self):
        ws = WindowService(window_size=5, overlap=1)
        windows = ws.create_windows([])
        assert windows == []

    def test_single_window(self):
        ws = WindowService(window_size=5, overlap=1)
        pages = ["a", "b", "c"]
        windows = ws.create_windows(pages)
        assert len(windows) == 1
        assert windows[0].page_start == 0
        assert windows[0].page_end == 2
        assert windows[0].pages == ["a", "b", "c"]

    def test_exact_window(self):
        ws = WindowService(window_size=3, overlap=1)
        pages = ["a", "b", "c"]
        windows = ws.create_windows(pages)
        assert len(windows) == 1
        assert windows[0].pages == ["a", "b", "c"]

    def test_two_windows_with_overlap(self):
        ws = WindowService(window_size=3, overlap=1)
        pages = ["a", "b", "c", "d", "e"]
        windows = ws.create_windows(pages)
        assert len(windows) == 2
        assert windows[0].pages == ["a", "b", "c"]
        assert windows[0].page_start == 0
        assert windows[0].page_end == 2
        assert windows[1].pages == ["c", "d", "e"]
        assert windows[1].page_start == 2
        assert windows[1].page_end == 4

    def test_window_indices_correct(self):
        ws = WindowService(window_size=5, overlap=1)
        pages = ["p0", "p1", "p2", "p3", "p4", "p5", "p6", "p7", "p8", "p9"]
        windows = ws.create_windows(pages)
        assert len(windows) == 3
        assert windows[0].page_start == 0
        assert windows[0].page_end == 4
        assert windows[1].page_start == 4
        assert windows[1].page_end == 8
        assert windows[2].page_start == 8
        assert windows[2].page_end == 9

    def test_overlap_one(self):
        ws = WindowService(window_size=5, overlap=1)
        pages = list(range(12))
        windows = ws.create_windows(pages)
        assert len(windows) == 3
        assert windows[0].pages[-5:] == [0, 1, 2, 3, 4]
        assert windows[1].pages[0] == 4
        assert windows[1].pages[-1] == 8
        assert windows[2].pages[0] == 8
