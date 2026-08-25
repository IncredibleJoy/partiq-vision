import hashlib
import math
import re

from openai import OpenAI, OpenAIError

from .config import settings
from .db import get_conn
from .schemas import PartDetection, TokenUsageItem


EMBEDDING_DIM = 1536

TOKEN_SYNONYMS = {
    "bumper": ["fascia", "cover", "reinforcement", "absorber"],
    "headlamp": ["headlight", "lamp", "lighting"],
    "headlight": ["headlamp", "lamp", "lighting"],
    "grille": ["grill", "radiator", "trim"],
    "hood": ["bonnet", "panel"],
    "bonnet": ["hood", "panel"],
    "clip": ["retainer", "fastener", "rivet"],
    "clips": ["retainer", "fastener", "rivet"],
    "screw": ["bolt", "fastener", "flange"],
    "screws": ["bolt", "fastener", "flange"],
    "washer": ["fastener", "body", "m6"],
    "wiring": ["harness", "connector", "electrical"],
    "wire": ["harness", "connector", "electrical"],
    "sensor": ["parking", "pdc", "electrical"],
    "oil": ["fluid", "lubrication", "engine"],
    "coolant": ["fluid", "radiator", "cooling"],
    "grease": ["lubricant", "latch", "hinge"],
}


def _tokens(text: str) -> list[str]:
    raw_tokens = re.findall(r"[a-z0-9]+", text.lower())
    expanded: list[str] = []
    for token in raw_tokens:
        expanded.append(token)
        expanded.extend(TOKEN_SYNONYMS.get(token, []))
    expanded.extend(f"{left}_{right}" for left, right in zip(raw_tokens, raw_tokens[1:]))
    return expanded


def _fallback_embedding(text: str) -> list[float]:
    values = [0.0] * EMBEDDING_DIM
    for token in _tokens(text):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % EMBEDDING_DIM
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        weight = 1.8 if "_" in token else 1.0
        values[index] += sign * weight
    norm = math.sqrt(sum(value * value for value in values)) or 1
    return [value / norm for value in values]


def embed_text(text: str) -> list[float]:
    if not settings.openai_api_key:
        return _fallback_embedding(text)
    client = OpenAI(api_key=settings.openai_api_key)
    try:
        response = client.embeddings.create(model=settings.embedding_model, input=text)
        return response.data[0].embedding
    except OpenAIError:
        return _fallback_embedding(text)


def embed_text_local(text: str) -> list[float]:
    return _fallback_embedding(text)


def _vector_literal(embedding: list[float]) -> str:
    return "[" + ",".join(f"{value:.8f}" for value in embedding[:EMBEDDING_DIM]) + "]"


def detection_text(detection: PartDetection) -> str:
    return " | ".join(
        [
            detection.part_name,
            detection.category,
            detection.material,
            detection.condition,
            detection.visible_part_no or "",
            detection.minute_details,
        ]
    )


def save_detection_vectors(job_id: str, detections: list[PartDetection]) -> TokenUsageItem:
    contents = [detection_text(detection) for detection in detections]
    purpose = "Embedding detected part labels, material, condition, OCR text, and minute details for PostgreSQL pgvector similarity search."
    usage_item = TokenUsageItem(step="part_vector_indexing", model="local-token-cluster", purpose=purpose)

    if settings.openai_api_key and contents:
        client = OpenAI(api_key=settings.openai_api_key)
        try:
            response = client.embeddings.create(model=settings.embedding_model, input=contents)
            embeddings = [item.embedding for item in response.data]
            input_tokens = int(getattr(response.usage, "prompt_tokens", 0) or getattr(response.usage, "input_tokens", 0) or 0)
            total_tokens = int(getattr(response.usage, "total_tokens", 0) or input_tokens)
            usage_item = TokenUsageItem(
                step="part_vector_indexing",
                model=settings.embedding_model,
                purpose=purpose,
                input_tokens=input_tokens,
                output_tokens=0,
                total_tokens=total_tokens,
            )
        except OpenAIError:
            embeddings = [_fallback_embedding(content) for content in contents]
            usage_item = TokenUsageItem(
                step="part_vector_indexing_fallback",
                model=settings.embedding_model,
                purpose="OpenAI embedding failed, so local deterministic vectors were used without consuming additional tokens.",
            )
    else:
        embeddings = [_fallback_embedding(content) for content in contents]

    with get_conn() as conn:
        for detection, content, embedding in zip(detections, contents, embeddings):
            vector = _vector_literal(embedding)
            conn.execute(
                """
                INSERT INTO part_vectors (detection_id, job_id, content, embedding)
                VALUES (%s, %s, %s, %s::vector)
                ON CONFLICT (detection_id) DO UPDATE
                SET content = EXCLUDED.content, embedding = EXCLUDED.embedding
                """,
                (detection.id, job_id, content, vector),
            )
        conn.commit()
    return usage_item


def search_parts(query: str, limit: int = 10) -> list[dict]:
    embedding = embed_text(query)
    vector = _vector_literal(embedding)
    with get_conn() as conn:
        return conn.execute(
            """
            SELECT d.*, 1 - (pv.embedding <=> %s::vector) AS similarity
            FROM part_vectors pv
            JOIN detections d ON d.id = pv.detection_id
            ORDER BY pv.embedding <=> %s::vector
            LIMIT %s
            """,
            (vector, vector, limit),
        ).fetchall()
