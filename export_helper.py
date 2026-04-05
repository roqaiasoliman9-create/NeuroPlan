import io
import pandas as pd
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


def df_to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


def plan_to_pdf_bytes(title: str, rows: list[dict]) -> bytes:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    y = height - 50
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(40, y, title)
    y -= 30

    pdf.setFont("Helvetica", 10)

    if not rows:
        pdf.drawString(40, y, "No data available.")
    else:
        for row in rows:
            line = " | ".join([f"{k}: {v}" for k, v in row.items()])
            if y < 50:
                pdf.showPage()
                pdf.setFont("Helvetica", 10)
                y = height - 50
            pdf.drawString(40, y, line[:110])
            y -= 16

    pdf.save()
    buffer.seek(0)
    return buffer.read()