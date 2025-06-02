from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from django.http import HttpResponse
from reportlab.lib.units import inch

def generate_test_report_pdf(report):
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='TitleCenter', parent=styles['Title'], alignment=TA_CENTER, spaceAfter=20))
    styles.add(ParagraphStyle(name='Heading2Blue', parent=styles['Heading2'], textColor=colors.HexColor('#1E3A8A'), spaceAfter=10))

    # Titre principal
    p.setTitle(f"Rapport de Test Technique - {report.session.candidate.full_name}")
    title = Paragraph("Rapport d'Évaluation Technique", styles['TitleCenter'])
    title.wrapOn(p, width - 2*inch, height)
    title.drawOn(p, inch, height - 1*inch)

    # Infos générales
    info_data = [
        ["Candidat :", report.session.candidate.full_name],
        ["Test :", report.session.test.title],
        ["Date :", report.generated_at.strftime('%d/%m/%Y')],
        ["Score Global :", f"{round(report.overall_score, 1)}/{report.session.max_score or '100'} ({round(report.overall_score/(report.session.max_score or 100)*100)}%)"]
    ]

    info_table = Table(info_data, colWidths=[1.8*inch, 4.5*inch])
    info_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,0), (-1,-1), 10),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    info_table.wrapOn(p, width - 2*inch, height)
    info_table.drawOn(p, inch, height - 2.2*inch)

    # Titre section compétences
    p.setFont("Helvetica-Bold", 12)
    p.setFillColor(colors.HexColor('#1E3A8A'))
    p.drawString(inch, height - 2.9*inch, "Évaluation par Compétence")

    # Tableau compétences
    skills_data = [['Compétence', 'Score', 'Pourcentage']]
    for skill, evaluation in report.skills_evaluation.items():
        if isinstance(evaluation, dict):
            score_percent = evaluation.get('score', 0)
            score_display = f"{evaluation.get('total', 0)}/{evaluation.get('max', 0)}"
        else:
            score_percent = evaluation
            score_display = f"{evaluation}/100"

        skills_data.append([
            skill.capitalize(),
            score_display,
            f"{round(float(score_percent), 1)} %"
        ])

    skills_table = Table(skills_data, colWidths=[2.5*inch, 1.5*inch, 1.2*inch])
    skills_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1E3A8A')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('BOTTOMPADDING', (0,0), (-1,0), 6),
        ('BACKGROUND', (0,1), (-1,-1), colors.HexColor('#F9FAFB')),
        ('GRID', (0,0), (-1,-1), 0.4, colors.grey),
    ]))
    skills_table.wrapOn(p, width - 2*inch, height)
    skills_table.drawOn(p, inch, height - 4.0*inch)

    # Sections texte (points forts/faibles)
    def draw_paragraph(title, content, y_pos):
        p.setFont("Helvetica-Bold", 11)
        p.setFillColor(colors.HexColor('#1E3A8A'))
        p.drawString(inch, y_pos, title)
        p.setFont("Helvetica", 10)
        text = p.beginText(inch, y_pos - 0.2*inch)
        text.setLeading(14)
        for line in content.strip().split('\n'):
            text.textLine(line)
        p.drawText(text)
        return y_pos - 0.2*inch - (content.count('\n') + 1)*14

    y = height - 5.2*inch
    #y = draw_paragraph("Points Forts", report.strengths, y)
    #y = draw_paragraph("Points Faibles", report.weaknesses, y)
    #y = draw_paragraph("Recommandations", report.recommendations, y)

    # Pied de page
    p.setFont("Helvetica", 8)
    p.setFillColor(colors.grey)
    p.drawString(inch, 0.5*inch, f"Généré le {report.generated_at.strftime('%d/%m/%Y %H:%M')}")
    p.drawRightString(width - inch, 0.5*inch, "Page 1/1")

    p.showPage()
    p.save()
    buffer.seek(0)
    return buffer
