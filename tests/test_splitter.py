from app.services.article_splitter import article_splitter


class TestArticleSplitter:
    def test_empty_text(self):
        assert article_splitter.split("") == []

    def test_no_articles(self):
        result = article_splitter.split("Este es un texto sin articulos")
        assert len(result) == 1
        assert "Este es un texto" in result[0]

    def test_single_article(self):
        text = "ARTICULO 1.- (OBJETIVO). Este es el objetivo del reglamento."
        result = article_splitter.split(text)
        assert len(result) == 1
        assert "ARTICULO 1" in result[0]
        assert "objetivo" in result[0]

    def test_multiple_articles(self):
        text = "ARTICULO 1.- (OBJETIVO). Texto uno.\nARTICULO 2.- (ALCANCE). Texto dos."
        result = article_splitter.split(text)
        assert len(result) == 2

    def test_reference_not_split(self):
        text = "ARTICULO 9.- (EJERCICIO).\nConforme al Articulo 70 de la Ley Nro 2492.\nARTICULO 10.- (MODALIDADES).\nSiguiente articulo."
        result = article_splitter.split(text)
        assert len(result) == 2

    def test_articulo_with_accent(self):
        text = "ARTÍCULO 9.- (EJERCICIO).\nTexto del articulo 9."
        result = article_splitter.split(text)
        assert len(result) == 1

    def test_header_before_articles(self):
        text = "RESOLUCION\nVISTOS\nARTICULO 1.- Texto uno.\nARTICULO 2.- Texto dos."
        result = article_splitter.split(text)
        assert len(result) >= 2

    def test_footer_stripped(self):
        text = "ARTICULO 30.- (FINAL).\nTexto final.\nAl momento de ser impreso este documento deja de ser controlado."
        result = article_splitter.split(text)
        assert len(result) == 1
        assert "deja de ser controlado" not in result[0]
        assert "Texto final" in result[0]
