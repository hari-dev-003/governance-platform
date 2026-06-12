"""PDF report generation (reportlab) for AI governance artifacts.

Produces self-contained PDF bytes for model cards, bias-test reports and risk
assessments. Kept dependency-light: pure reportlab platypus, no external assets.
"""
from __future__ import annotations

import io
from datetime import datetime, timezone
from typing import Any


def _styles():
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_LEFT

    ss = getSampleStyleSheet()
    ss.add(ParagraphStyle(name="H", parent=ss["Heading1"], fontSize=18, spaceAfter=6,
                          textColor="#1e293b"))
    ss.add(ParagraphStyle(name="Sub", parent=ss["Normal"], fontSize=9, textColor="#64748b",
                          spaceAfter=12))
    ss.add(ParagraphStyle(name="Sec", parent=ss["Heading2"], fontSize=12, spaceBefore=12,
                          spaceAfter=4, textColor="#4338ca"))
    ss.add(ParagraphStyle(name="Body", parent=ss["Normal"], fontSize=9.5, alignment=TA_LEFT,
                          leading=14))
    return ss


def _kv_table(rows: list[tuple[str, Any]]):
    from reportlab.lib import colors
    from reportlab.platypus import Table, TableStyle

    data = [[str(k), "" if v is None else str(v)] for k, v in rows]
    t = Table(data, colWidths=[150, 330])
    t.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#475569")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#e2e8f0")),
    ]))
    return t


def _build(title: str, subtitle: str, flowables_fn) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

    ss = _styles()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=48, rightMargin=48,
                            topMargin=48, bottomMargin=48, title=title)
    story = [Paragraph(title, ss["H"]), Paragraph(subtitle, ss["Sub"])]
    flowables_fn(story, ss, Paragraph, Spacer)
    story.append(Spacer(1, 18))
    story.append(Paragraph(
        f"Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} · "
        "Data + AI Governance Platform", ss["Sub"]))
    doc.build(story)
    return buf.getvalue()


def model_card_pdf(card: dict) -> bytes:
    def body(story, ss, P, Spacer):
        story.append(_kv_table([
            ("Owner", card.get("owner")),
            ("Business domain", card.get("business_domain")),
            ("Framework", card.get("framework")),
            ("Model type", card.get("model_type")),
            ("Risk tier", card.get("risk_tier")),
            ("Deployment status", card.get("deployment_status")),
        ]))
        story.append(P("Intended use", ss["Sec"]))
        story.append(P(str(card.get("intended_use") or "—"), ss["Body"]))
        story.append(P("Description", ss["Sec"]))
        story.append(P(str(card.get("description") or "—"), ss["Body"]))
        versions = card.get("versions") or []
        story.append(P(f"Versions ({len(versions)})", ss["Sec"]))
        if versions:
            story.append(_kv_table([(f"v{v.get('version_number')}",
                                     f"stage={v.get('stage')} · metrics={v.get('metrics')}")
                                    for v in versions]))
        else:
            story.append(P("No versions registered.", ss["Body"]))
        ra = card.get("risk_assessment")
        story.append(P("Risk assessment", ss["Sec"]))
        if ra:
            story.append(_kv_table([
                ("Risk tier", ra.get("risk_tier")),
                ("EU AI Act category", ra.get("category")),
                ("Risk factors", ", ".join(ra.get("risk_factors") or []) or "—"),
            ]))
            story.append(P("Required actions", ss["Sec"]))
            for a in (ra.get("required_actions") or []):
                story.append(P(f"• {a}", ss["Body"]))
        else:
            story.append(P("Not yet assessed.", ss["Body"]))
    return _build(f"Model Card — {card.get('name', 'Model')}",
                  "AI model governance summary", body)


def bias_report_pdf(run: dict) -> bytes:
    def body(story, ss, P, Spacer):
        story.append(_kv_table([
            ("Verdict", run.get("verdict")),
            ("Status", run.get("status")),
            ("Summary", run.get("summary")),
        ]))
        for label, key in [("Demographic parity (selection rate)", "demographic_parity"),
                           ("Equal opportunity (TPR)", "equal_opportunity"),
                           ("Predictive parity", "predictive_parity")]:
            story.append(P(label, ss["Sec"]))
            metric = run.get(key) or {}
            if metric:
                story.append(_kv_table([(g, v) for g, v in metric.items()]))
            else:
                story.append(P("—", ss["Body"]))
    return _build("Bias & Fairness Report", "Engine: Fairlearn", body)


def risk_assessment_pdf(ra: dict) -> bytes:
    def body(story, ss, P, Spacer):
        story.append(_kv_table([
            ("Risk tier", ra.get("risk_tier")),
            ("EU AI Act category", ra.get("eu_ai_act_category")),
            ("Status", ra.get("status")),
        ]))
        story.append(P("Identified risk factors", ss["Sec"]))
        for f in (ra.get("risk_factors") or []):
            story.append(P(f"• {f}", ss["Body"]))
        if not ra.get("risk_factors"):
            story.append(P("—", ss["Body"]))
        story.append(P("Required actions", ss["Sec"]))
        for a in (ra.get("required_actions") or []):
            story.append(P(f"• {a}", ss["Body"]))
    return _build("EU AI Act Risk Assessment", "Engine: weighted questionnaire", body)
