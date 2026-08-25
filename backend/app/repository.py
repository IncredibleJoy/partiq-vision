from uuid import UUID

from psycopg.types.json import Jsonb

from .db import get_conn
from .schemas import AgentTrace, DetectionLabelUpdate, JobResponse, PartDetection, PartRecommendation, TokenUsageSummary


def save_job(job: JobResponse) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO analysis_jobs (id, model_mode, vehicle_context, token_usage) VALUES (%s, %s, %s, %s)",
            (job.job_id, job.model_mode, job.vehicle_context, Jsonb(job.token_usage.model_dump())),
        )
        for detection in job.detections:
            conn.execute(
                """
                INSERT INTO detections (
                  id, job_id, source_image, part_name, category, material, condition,
                  visible_part_no, minute_details, confidence, bbox, crop_url
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    detection.id,
                    job.job_id,
                    detection.source_image or "",
                    detection.part_name,
                    detection.category,
                    detection.material,
                    detection.condition,
                    detection.visible_part_no,
                    detection.minute_details,
                    detection.confidence,
                    Jsonb(detection.bbox.model_dump()),
                    detection.crop_url,
                ),
            )
        for recommendation in job.recommendations:
            conn.execute(
                """
                INSERT INTO recommendations (
                  id, job_id, part_name, reason, recommendation_type, confidence, related_parts
                )
                VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, %s)
                """,
                (
                    job.job_id,
                    recommendation.part_name,
                    recommendation.reason,
                    recommendation.recommendation_type,
                    recommendation.confidence,
                    Jsonb(recommendation.related_parts),
                ),
            )
        for trace in job.agent_trace:
            conn.execute(
                """
                INSERT INTO agent_traces (job_id, agent, action, status, detail)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (job.job_id, trace.agent, trace.action, trace.status, trace.detail),
            )
        conn.commit()


def get_job(job_id: UUID) -> dict | None:
    with get_conn() as conn:
        job = conn.execute("SELECT * FROM analysis_jobs WHERE id = %s", (job_id,)).fetchone()
        if not job:
            return None
        rows = conn.execute(
            "SELECT * FROM detections WHERE job_id = %s ORDER BY confidence DESC", (job_id,)
        ).fetchall()
        rec_rows = conn.execute(
            "SELECT * FROM recommendations WHERE job_id = %s ORDER BY confidence DESC", (job_id,)
        ).fetchall()
        trace_rows = conn.execute(
            "SELECT agent, action, status, detail FROM agent_traces WHERE job_id = %s ORDER BY id ASC",
            (job_id,),
        ).fetchall()
        detections = [
            PartDetection(
                id=str(row["id"]),
                source_image=row["source_image"],
                part_name=row["part_name"],
                category=row["category"],
                material=row["material"],
                condition=row["condition"],
                visible_part_no=row["visible_part_no"],
                minute_details=row["minute_details"],
                confidence=row["confidence"],
                bbox=row["bbox"],
                crop_url=row["crop_url"],
            )
            for row in rows
        ]
        return {
            "job": job,
            "token_usage": TokenUsageSummary.model_validate(job["token_usage"]),
            "detections": detections,
            "recommendations": [
                PartRecommendation(
                    part_name=row["part_name"],
                    reason=row["reason"],
                    recommendation_type=row["recommendation_type"],
                    confidence=row["confidence"],
                    related_parts=row["related_parts"],
                )
                for row in rec_rows
            ],
            "agent_trace": [AgentTrace(**row) for row in trace_rows],
        }


def update_job_token_usage(job_id: UUID | str, token_usage: TokenUsageSummary) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE analysis_jobs SET token_usage = %s WHERE id = %s",
            (Jsonb(token_usage.model_dump()), job_id),
        )
        conn.commit()


def update_detection_labels(job_id: UUID, updates: list[DetectionLabelUpdate]) -> None:
    editable_columns = {
        "part_name",
        "category",
        "material",
        "condition",
        "visible_part_no",
        "minute_details",
    }
    with get_conn() as conn:
        for update in updates:
            data = update.model_dump(exclude_unset=True, exclude={"id"})
            data = {key: value for key, value in data.items() if key in editable_columns}
            if not data:
                continue
            assignments = ", ".join(f"{key} = %s" for key in data)
            values = list(data.values())
            values.extend([update.id, job_id])
            conn.execute(
                f"UPDATE detections SET {assignments} WHERE id = %s AND job_id = %s",
                values,
            )
        conn.execute("DELETE FROM recommendations WHERE job_id = %s", (job_id,))
        conn.execute(
            """
            INSERT INTO agent_traces (job_id, agent, action, status, detail)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                job_id,
                "orchestrator_agent",
                "apply_user_label_updates",
                "complete",
                f"Applied {len(updates)} label update(s)",
            ),
        )
        conn.commit()


def replace_recommendations(job_id: UUID | str, recommendations: list[PartRecommendation]) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM recommendations WHERE job_id = %s", (job_id,))
        for recommendation in recommendations:
            conn.execute(
                """
                INSERT INTO recommendations (
                  id, job_id, part_name, reason, recommendation_type, confidence, related_parts
                )
                VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, %s)
                """,
                (
                    job_id,
                    recommendation.part_name,
                    recommendation.reason,
                    recommendation.recommendation_type,
                    recommendation.confidence,
                    Jsonb(recommendation.related_parts),
                ),
            )
        conn.commit()
