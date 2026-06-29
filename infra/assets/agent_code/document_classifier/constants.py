TAG_CATEGORY = 'classification'
TAG_PAGE_COUNT = 'page-count'
TAG_SKIP_CLASSIFICATION = 'skipClassification'
TAG_LAST_CLASSIFICATION_ETAG = 'lastClassificationEtag'

PAGES_TO_READ = 10

LABELS = [
    "technical_specifications",
    "technical_specifications_modifications",
    "legal_clauses",
    "legal_clauses_modifications",
    "economic_requirements",
    'supporting_doc',
    "technical_response",
    "administrative_response",
]

LABELS_TO_STAGE = [
    "technical_specifications",
    "technical_specifications_modifications",
    "legal_clauses",
    "legal_clauses_modifications",
    "economic_requirements"
]

KEYWORDS_MAP = {
    "legal": [
        "pcap", "pliego de cláusulas administrativas", "cláusulas administrativas",
        "solvencia", "garantía", "adjudicación", "procedimiento",
        "licitador", "mesa de contratación", "penalidades", "criterios de adjudicación",
    ],
    "technical": [
        "ppt", "pliego de prescripciones técnicas", "prescripciones técnicas",
        "requisitos técnicos", "especificaciones", "alcance", "sla", "arquitectura",
    ],
    "economic": [
        "presupuesto base de licitación", "pbl", "valor estimado",
        "oferta económica", "precio", "facturación", "pagos", "revisión de precios",
    ],
    "mods": [
        "modificación", "modificaciones", "fe de erratas", "corrección",
        "rectificación", "aclaración", "cambios", "versión", "anexo",
    ],
    "response_common": [
        "oferta", "propuesta", "licitador", "empresa licitadora",
        "presenta la siguiente", "documentación presentada", "sobre a", "sobre b", "sobre 1", "sobre 2",
        "memoria", "propuesta técnica", "propuesta tecnica", "oferta técnica", "oferta tecnica",
        "firma", "representante", "nif", "cif"
    ],
    "tech_response": [
        "memoria técnica", "memoria tecnica", "metodología", "metodologia", "plan de trabajo",
        "cronograma", "equipo", "organigrama", "currículum", "curriculum", "cv",
        "solución", "solucion", "arquitectura propuesta", "cumplimiento", "matriz de cumplimiento"
    ],
    "admin_response": [
        "documentación administrativa", "documentacion administrativa", "declaración responsable",
        "declaracion responsable", "deuc", "espd", "apoderamiento", "poder notarial",
        "escritura", "registro mercantil", "certificado", "hacienda", "seguridad social"
    ]
}