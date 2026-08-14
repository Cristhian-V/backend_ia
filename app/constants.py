TOOL_KEYS = ("agente_aduanero_ia", "liquidador_ia", "herramientas_transbel", "fnning")

ROLES = ("consultor", "gestor")

RELATION_TYPES = ("deroga", "modifica", "referencia", "complementa", "base_legal")

REF_TYPES = ("resolucion", "circular", "ley", "decreto", "reglamento", "otro")

CATEGORIA_LABELS: dict[str, str] = {
    "LGA": "Ley General de Aduanas",
    "RLGA": "Reglamento LGA",
    "RD": "Resolucion de Directorio",
    "Circular": "Circular",
    "Instructivo": "Instructivo/Minuta",
    "CTB": "Codigo Tributario Boliviano",
    "Ley": "Ley",
    "DS": "Decreto Supremo",
    "Convenio": "Convenio Internacional",
    "Otros": "Otros",
}
