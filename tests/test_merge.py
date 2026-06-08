from app.services.merge_service import MergeService


class TestMergeService:
    def test_empty(self):
        ms = MergeService()
        assert ms.merge([]) == []

    def test_single_batch(self):
        ms = MergeService()
        chapters = [{"title": "Cap 1", "content": "Texto uno"}]
        result = ms.merge([chapters])
        assert len(result) == 1
        assert result[0]["title"] == "Cap 1"

    def test_no_overlap(self):
        ms = MergeService()
        batch1 = [{"title": "Cap A", "content": "contenido a"}]
        batch2 = [{"title": "Cap B", "content": "contenido b"}]
        result = ms.merge([batch1, batch2])
        assert len(result) == 2
        assert result[0]["title"] == "Cap A"
        assert result[1]["title"] == "Cap B"

    def test_merge_duplicate_first_chars(self):
        ms = MergeService(match_threshold=10)
        batch1 = [{"title": "Cap 1", "content": "Este es el mismo capitulo que continua"}]
        batch2 = [
            {"title": "Cap 1 cont", "content": "Este es el mismo capitulo que continua con mas texto"},
            {"title": "Cap 2", "content": "Segundo capitulo"},
        ]
        result = ms.merge([batch1, batch2])
        assert len(result) == 2
        assert result[0]["title"] == "Cap 1"
        assert "con mas texto" in result[0]["content"]

    def test_different_first_chars_no_merge(self):
        ms = MergeService(match_threshold=10)
        batch1 = [{"title": "Cap 1", "content": "Primer capitulo completo"}]
        batch2 = [
            {"title": "Cap 2", "content": "Segundo capitulo distinto"},
        ]
        result = ms.merge([batch1, batch2])
        assert len(result) == 2

    def test_three_batches(self):
        ms = MergeService(match_threshold=5)
        b1 = [{"title": "A", "content": "abcde continuacion"}]
        b2 = [{"title": "A cont", "content": "abcde mas texto"}, {"title": "B", "content": "nuevo"}]
        b3 = [{"title": "C", "content": "final"}]
        result = ms.merge([b1, b2, b3])
        assert len(result) == 3
        assert "mas texto" in result[0]["content"]
        assert result[1]["title"] == "B"
        assert result[2]["title"] == "C"

    def test_concat_with_overlap(self):
        ms = MergeService(match_threshold=5)
        b1 = [{"title": "X", "content": "Hola mundo desde el servidor"}]
        b2 = [{"title": "X", "content": "Hola mundo esta es la continuacion"}]
        result = ms.merge([b1, b2])
        assert len(result) == 1
        assert "continuacion" in result[0]["content"]
        assert "servidor" in result[0]["content"]
