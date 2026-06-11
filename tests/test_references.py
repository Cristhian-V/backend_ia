import re
from app.services.reference_service import reference_service


class TestNormalize:
    def test_normalize_lowercase(self):
        assert reference_service.normalize("ABC") == reference_service.normalize("abc")

    def test_normalize_spaces(self):
        assert reference_service.normalize("RD 01-098-24") == reference_service.normalize("RD01-098-24")

    def test_normalize_hyphens(self):
        assert reference_service.normalize("RD-01-098-24") == reference_service.normalize("RD0109824")

    def test_normalize_slashes(self):
        assert reference_service.normalize("323/2024") == "3232024"

    def test_normalize_special_chars(self):
        assert reference_service.normalize("Nro 843 (T.O.)") == "nro843to"

    def test_normalize_different_same(self):
        n1 = reference_service.normalize("Resolución RD 01-098-24")
        n2 = reference_service.normalize("Resolucion RD01-098-24")
        assert n1 == n2


class TestLegalFramework:
    def test_marco_legal_is_filtered(self):
        assert reference_service._is_legal_framework("Articulo 3 - Marco Legal") is True
        assert reference_service._is_legal_framework("ARTÍCULO 3.- (MARCO LEGAL)") is True

    def test_marco_normativo_is_filtered(self):
        assert reference_service._is_legal_framework("Capitulo I - Marco Normativo") is True

    def test_base_legal_is_filtered(self):
        assert reference_service._is_legal_framework("Base Legal y Normativa") is True

    def test_other_chapter_not_filtered(self):
        assert reference_service._is_legal_framework("Articulo 5 - Derogaciones") is False
        assert reference_service._is_legal_framework("Objetivo General") is False
        assert reference_service._is_legal_framework("Definiciones y Abreviaturas") is False

    def test_empty_title(self):
        assert reference_service._is_legal_framework("") is False


class TestTitleOneFilter:
    def _filter(self, articles):
        from app.services.vector_store import _filter_title_one_articles
        return _filter_title_one_articles(articles)

    def test_title_one_no_whitelist_removed(self):
        articles = [
            "ARTICULO 1.- (OBJETIVO)\nTexto del articulo 1.",
            "ARTICULO 2.- (OBJETIVOS ESPECIFICOS)\nTexto del articulo 2.",
            "ARTICULO 4.- (DEFINICIONES)\nTexto del articulo 4.",
        ]
        result = self._filter(articles)
        assert len(result) == 0

    def test_whitelisted_articles_kept(self):
        articles = [
            "ARTICULO 5.- (ALCANCE)\nalcance",
            "ARTICULO 6.- (RESPONSABILIDAD)\nresp",
            "ARTICULO 7.- (SANCIONES)\nsanciones",
        ]
        result = self._filter(articles)
        assert len(result) == 3

    def test_mixed_filtered_and_whitelisted(self):
        articles = [
            "ARTICULO 1.- (OBJETIVO)\nobj",
            "ARTICULO 5.- (ALCANCE)\nalc",
            "ARTICULO 8.- (OTRO)\notro",
            "ARTICULO 15.- (VERIFICACION)\nverif",
        ]
        result = self._filter(articles)
        assert len(result) == 2
        first_lines = [r.split("\n")[0] for r in result]
        assert any("ARTICULO 5" in l for l in first_lines)
        assert any("ARTICULO 15" in l for l in first_lines)
        assert not any(re.search(r"ARTICULO 1\b(?!\d)", l) for l in first_lines)
        assert not any(re.search(r"ARTICULO 8\b(?!\d)", l) for l in first_lines)

    def test_article_nine_and_above_kept(self):
        articles = [
            "ARTICULO 1.- (OBJETIVO)\nobj",
            "ARTICULO 9.- (FUNCIONES)\nfunc",
            "ARTICULO 10.- (MODALIDADES)\nmod",
        ]
        result = self._filter(articles)
        assert len(result) == 2
        first_lines = [r.split("\n")[0] for r in result]
        assert any("ARTICULO 9" in l for l in first_lines)
        assert any("ARTICULO 10" in l for l in first_lines)
        assert not any(re.search(r"ARTICULO 1\b(?!\d)", l) for l in first_lines)

    def test_non_article_lines_kept(self):
        articles = [
            "RESOLUCION ADMINISTRATIVA\nVISTOS\nEncabezado del documento.",
        ]
        result = self._filter(articles)
        assert len(result) == 1
