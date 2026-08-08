import re
import tempfile
import os
import unicodedata
from io import BytesIO

import xlrd
from xlutils.copy import copy as xl_copy
from xlwt import XFStyle, Font, Alignment, Borders, Pattern, Protection
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

STOPWORDS = {
    "de", "la", "el", "los", "las", "del", "en", "con", "por", "para", "sin",
    "que", "y", "o", "a", "e", "u", "un", "una", "su", "al", "lo", "se",
    "no", "le", "es", "son", "ha", "han",
}


def _extract_style(rb: xlrd.Book, sheet: xlrd.sheet.Sheet, row: int, col: int) -> XFStyle:
    cell = sheet.cell(row, col)
    xf_idx = cell.xf_index
    if xf_idx is None or xf_idx >= len(rb.xf_list):
        return XFStyle()

    xf = rb.xf_list[xf_idx]
    style = XFStyle()

    font_obj = rb.font_list[xf.font_index]
    f = Font()
    f.bold = bool(font_obj.bold)
    f.italic = bool(font_obj.italic)
    f.underline = bool(font_obj.underline_type)
    f.struck_out = bool(font_obj.struck_out)
    f.outline = bool(font_obj.outline)
    f.shadow = bool(font_obj.shadow)
    f.name = font_obj.name
    f.height = font_obj.height
    f.escapement = font_obj.escapement
    f.family = font_obj.family
    f.charset = font_obj.character_set
    if font_obj.colour_index is not None:
        f.colour_index = font_obj.colour_index
    style.font = f

    align = Alignment()
    align.horz = xf.alignment.hor_align
    align.vert = xf.alignment.vert_align
    align.text_direction = xf.alignment.text_direction
    align.rotation = xf.alignment.rotation
    align.wrap = xf.alignment.text_wrapped
    align.shirnk = xf.alignment.shrink_to_fit
    align.indent = xf.alignment.indent_level
    style.alignment = align

    borders = Borders()
    borders.left = xf.border.left_line_style
    borders.right = xf.border.right_line_style
    borders.top = xf.border.top_line_style
    borders.bottom = xf.border.bottom_line_style
    if xf.border.left_colour_index is not None:
        borders.left_colour = xf.border.left_colour_index
    if xf.border.right_colour_index is not None:
        borders.right_colour = xf.border.right_colour_index
    if xf.border.top_colour_index is not None:
        borders.top_colour = xf.border.top_colour_index
    if xf.border.bottom_colour_index is not None:
        borders.bottom_colour = xf.border.bottom_colour_index
    style.borders = borders

    pat = Pattern()
    pat.pattern = xf.background.fill_pattern
    if xf.background.background_colour_index is not None:
        pat.pattern_back_colour = xf.background.background_colour_index
    if xf.background.pattern_colour_index is not None:
        pat.pattern_fore_colour = xf.background.pattern_colour_index
    style.pattern = pat

    prot = Protection()
    prot.cell_locked = xf.protection.cell_locked
    prot.formula_hidden = xf.protection.formula_hidden
    style.protection = prot

    return style


def _normalize(text: str) -> str:
    t = text.lower()
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    t = re.sub(r"\s+", " ", t)
    return t.strip()


def _text_similarity(desc_colombia: str, desc_arancel: str) -> float:
    a = _normalize(desc_colombia)
    b = _normalize(desc_arancel)
    words_a = {w for w in a.split() if len(w) > 1 and w not in STOPWORDS}
    words_b = [w for w in b.split() if len(w) > 1]
    if not words_a:
        return 0.0
    matches = sum(1 for w in words_b if w in words_a)
    return matches / len(words_a)


def _format_with_dots(codigo: str) -> str:
    if len(codigo) != 10:
        return codigo
    return f"{codigo[:4]}.{codigo[4:6]}.{codigo[6:8]}.{codigo[8:10]}"


def _clean_description(desc: str) -> str:
    return re.sub(r"^[\s\-–—]+", "", desc).strip()


async def _find_match(db: AsyncSession, codigo_colombia: str, descripcion_colombia: str) -> dict | None:
    codigo_sin_puntos = codigo_colombia.replace(".", "")
    prefijo6 = codigo_sin_puntos[:6]

    result = await db.execute(
        text(
            "SELECT codigo, descripcion, ga_reducido, iva "
            "FROM core.arancel_nacional WHERE prefijo6 = :p6"
        ),
        {"p6": prefijo6},
    )
    rows = result.fetchall()
    if not rows:
        return None

    scored = []
    for row in rows:
        score = _text_similarity(descripcion_colombia, row.descripcion)
        scored.append((row, score))

    scored.sort(key=lambda x: (-x[1], len(x[0].codigo)))

    best = scored[0][0]
    return {
        "codigo": _format_with_dots(best.codigo),
        "descripcion_partida": _clean_description(best.descripcion),
        "arancel": round(best.ga_reducido * 100) if best.ga_reducido is not None else None,
        "iva": float(best.iva) if best.iva is not None else 14.94,
        "score": round(scored[0][1], 2),
    }


async def process_excel(
    db: AsyncSession, file_bytes: bytes, original_filename: str
) -> tuple[bytes, str]:
    tmp = tempfile.NamedTemporaryFile(suffix=".xls", delete=False)
    try:
        tmp.write(file_bytes)
        tmp.close()

        rb = xlrd.open_workbook(tmp.name, formatting_info=True)
        sn = None
        for name in rb.sheet_names():
            if "FICHA" in name.upper() or "COMEX" in name.upper():
                sn = name
                break
        if sn is None:
            sn = rb.sheet_names()[0]
        ws = rb.sheet_by_name(sn)

        if ws.nrows < 18:
            raise ValueError("El archivo no tiene el formato esperado")

        col_bol = 2
        col_col = 4

        codigo_co = str(ws.cell(11, col_col).value).strip() if ws.cell(11, col_col).ctype != 0 else ""
        descripcion_co = str(ws.cell(12, col_col).value).strip() if ws.cell(12, col_col).ctype != 0 else ""
        cert_origen_co = str(ws.cell(14, col_col).value).strip() if ws.cell(14, col_col).ctype != 0 else ""

        if not codigo_co:
            raise ValueError("No se encontro la partida arancelaria de Colombia (fila 12, columna E)")

        match = await _find_match(db, codigo_co, descripcion_co)

        wb = xl_copy(rb)
        wws = wb.get_sheet(sn)

        row_fill = [
            (12, match["codigo"] if match else "No encontrado"),
            (13, descripcion_co),
            (14, match["descripcion_partida"] if match else ""),
            (15, cert_origen_co or "NA"),
            (16, "-"),
            (17, str(match["arancel"]) if (match and match["arancel"] is not None) else "-"),
            (18, "14.94"),
            (19, "-"),
            (20, "-"),
            (21, "-"),
            (22, "-"),
        ]

        for r, val in row_fill:
            style = _extract_style(rb, ws, r - 1, col_col)
            wws.write(r - 1, col_bol, val, style)

        for r in range(23, 87):
            style = _extract_style(rb, ws, r - 1, col_col)
            wws.write(r - 1, col_bol, "-", style)

        out = BytesIO()
        wb.save(out)
        out.seek(0)

        base = os.path.splitext(original_filename)[0]
        download_name = f"{base} - Procesado.xls"

        return out.getvalue(), download_name
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
