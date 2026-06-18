import re
import os


async def seed_checklist(conn) -> int:
    """
    Lee normativa_aduana_vigente.txt y carga los items en core.checklist.
    Cada item representa un codigo unico (RD, Circular, Ley, DS, Articulo, etc.)
    vinculado a su indice alfabetico (tema).
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    txt_path = os.path.join(base_dir, "data", "normativa_aduana_vigente.txt")

    items: list[dict] = []
    seen: set[tuple[str, str]] = set()

    with open(txt_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            parts = line.split("|")
            if len(parts) != 7:
                continue

            indice = parts[0].strip()
            lga_raw = parts[1].strip()
            rlga_raw = parts[2].strip()
            regl_raw = parts[3].strip()
            inst_raw = parts[4].strip()
            ctb_raw = parts[5].strip()
            otros_raw = parts[6].strip()

            # Col 1: Ley General de Aduanas
            _extract_articulos(items, seen, indice, lga_raw, "LGA")
            # Col 2: Reglamento LGA
            _extract_articulos(items, seen, indice, rlga_raw, "RLGA")
            # Col 3: Reglamentos (RD)
            _extract_docs(items, seen, indice, regl_raw, "RD")
            # Col 3: Circulares (mixed in Reglamentos column)
            _extract_docs(items, seen, indice, regl_raw, "Circular")
            # Col 4: Instructivos
            _extract_docs(items, seen, indice, inst_raw, "Instructivo")
            # Col 5: CTB
            _extract_articulos(items, seen, indice, ctb_raw, "CTB")
            # Col 6: Otros - Leyes
            _extract_docs(items, seen, indice, otros_raw, "Ley")
            # Col 6: Otros - Decretos Supremos
            _extract_docs(items, seen, indice, otros_raw, "DS")
            # Col 6: Otros - Convenios
            _extract_docs(items, seen, indice, otros_raw, "Convenio")
            # Col 6: Otros - generic
            _extract_docs(items, seen, indice, otros_raw, "Otros")

    from sqlalchemy import text as sa_text
    count = 0
    for item in items:
        await conn.execute(
            sa_text(
                "INSERT INTO core.checklist (indice, categoria, codigo) "
                "VALUES (:indice, :cat, :cod) "
                "ON CONFLICT DO NOTHING"
            ),
            {"indice": item["indice"], "cat": item["categoria"], "cod": item["codigo"]},
        )
        count += 1

    return count


def _extract_articulos(items, seen, indice, raw, categoria):
    """Extract individual articles like Art. 153, 154, 155"""
    if not raw or raw == "-":
        return
    nums = re.findall(r"\d+(?:[-–]\d+)?", raw.replace(" ", ""))
    for n in nums:
        codigo = f"Art. {n}"
        key = (categoria, codigo)
        if key not in seen:
            seen.add(key)
            items.append({"indice": indice, "categoria": categoria, "codigo": codigo})


def _extract_docs(items, seen, indice, raw, categoria):
    """Extract document codes like RD 01-078-25, Cir. 323/2024, D.S. 572"""
    if not raw or raw == "-":
        return

    # Patterns for each category
    patterns = {
        "RD": r"RD\s*\d{2}[-–]\d{3}[-–]\d{2}",
        "Circular": r"Cir\.?\s*\d{2,4}/\d{2,4}",
        "Instructivo": r"(?:GEGPC|DTA|DNP|PE/INST|AN/PE/MI|PREDC-INST|DVA)\s*\S+",
        "Ley": r"Ley\s+(?:N[°º]\s*)?\d+",
        "DS": r"D\.?S\.?\s*(?:N[°º]\s*)?\d+",
        "Convenio": r"(?:Convenio|Acuerdo|Tratado)\s+(?:de\s+)?[A-ZÁÉÍÓÚa-záéíóú]+(?:\s+[A-ZÁÉÍÓÚa-záéíóú]+)*",
        "Otros": r"(?:Res\.?\s*(?:Min\.?|Bi\s*Min)\s*\S+|R\.?M\.?\s*\S+|RBM\s*\S+|Sala\s+Plena|GATT\s+\d+|Decision\s+\d+|NB\d{5}|Cartilla|Errata\s+\d+)",
    }

    if categoria in patterns:
        matches = re.findall(patterns[categoria], raw, re.IGNORECASE)
        for m in matches:
            codigo = m.strip()
            key = (categoria, codigo)
            if key not in seen:
                seen.add(key)
                items.append({"indice": indice, "categoria": categoria, "codigo": codigo})
    else:
        # Fallback: split by comma
        for part in re.split(r"\s*,\s*", raw):
            part = part.strip()
            if part and len(part) > 2:
                key = (categoria, part)
                if key not in seen:
                    seen.add(key)
                    items.append({"indice": indice, "categoria": categoria, "codigo": part})
