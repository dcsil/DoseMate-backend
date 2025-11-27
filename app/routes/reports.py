from datetime import datetime, date, time, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from app.db.database import get_db
from app.db.models import MedicationSchedule, DoseLog, User, UserProfile
from jose import jwt, JWTError
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.enums import TA_CENTER
from io import BytesIO
from app.core.config import settings

router = APIRouter()

# Add this helper function to decode token from query param
async def get_current_user_from_token(
    token: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Get current user from token query parameter (for mobile PDF downloads)
    """
    try:
        
        payload = jwt.decode(token, settings.jwt_secret_key,algorithms=[settings.jwt_algorithm])
        user_id: str = payload.get("sub")
        
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        # Fetch user from database
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        
        if user is None:
            raise HTTPException(status_code=401, detail="User not found")
        
        return user
        
    except JWTError:
        raise HTTPException(status_code=401, detail="Could not validate credentials")


@router.get("/reports/weekly")
async def generate_weekly_report(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user_from_token)
):
    """
    Generate a comprehensive weekly adherence report for healthcare providers
    Returns PDF file
    
    Usage: GET /reminders/reports/weekly?token=YOUR_JWT_TOKEN
    """
    
    # Fetch user info
    user_result = await db.execute(
        select(User).where(User.id == current_user.id)
    )
    user = user_result.scalar_one_or_none()
    
    # Fetch user profile
    profile_result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == current_user.id)
    )
    profile = profile_result.scalar_one_or_none()
    
    # Calculate weekly data
    today = date.today()
    days_data = []
    total_taken = 0
    total_scheduled = 0
    missed_doses = []
    
    for i in range(6, -1, -1):
        target_date = today - timedelta(days=i)
        start_of_day = datetime.combine(target_date, time.min)
        end_of_day = datetime.combine(target_date, time.max)
        
        result = await db.execute(
            select(DoseLog)
            .where(
                DoseLog.user_id == current_user.id,
                DoseLog.scheduled_time >= start_of_day,
                DoseLog.scheduled_time <= end_of_day
            )
            .options(selectinload(DoseLog.schedule).selectinload(MedicationSchedule.medication))
        )
        logs = result.scalars().all()
        
        taken = sum(1 for log in logs if log.status == "taken")
        total = len(logs)
        percentage = round((taken / total * 100)) if total > 0 else 0
        
        total_taken += taken
        total_scheduled += total
        
        days_data.append({
            "date": target_date,
            "day": target_date.strftime("%A"),
            "taken": taken,
            "total": total,
            "percentage": percentage
        })
        
        # Collect missed doses
        for log in logs:
            if log.status == "missed":
                missed_doses.append({
                    "date": target_date,
                    "medication": log.schedule.medication.brand_name,
                    "strength": log.schedule.strength,
                    "time": log.scheduled_time.strftime("%I:%M %p")
                })
    
    weekly_percentage = round((total_taken / total_scheduled * 100)) if total_scheduled > 0 else 0
    
    # Calculate streak
    current_streak = 0
    for day in reversed(days_data):
        if day["percentage"] == 100 and day["total"] > 0:
            current_streak += 1
        else:
            break
    
    # Get all active medications
    meds_result = await db.execute(
        select(MedicationSchedule)
        .where(MedicationSchedule.user_id == current_user.id)
        .options(selectinload(MedicationSchedule.medication))
    )
    schedules = meds_result.scalars().all()
    
    # Generate PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#E85D5B'),
        spaceAfter=30,
        alignment=TA_CENTER
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=colors.HexColor('#2C2C2C'),
        spaceAfter=12,
        spaceBefore=20
    )
    
    # Title
    elements.append(Paragraph("Weekly Medication Adherence Report", title_style))
    elements.append(Spacer(1, 0.2 * inch))
    
    # Patient Information
    elements.append(Paragraph("Patient Information", heading_style))
    patient_data = [
        ["Name:", user.name or "Not provided"],
        ["Email:", user.email],
        ["Report Period:", f"{days_data[0]['date'].strftime('%B %d, %Y')} - {days_data[-1]['date'].strftime('%B %d, %Y')}"],
        ["Generated:", datetime.now().strftime("%B %d, %Y at %I:%M %p")],
    ]
    
    if profile:
        if profile.age:
            patient_data.append(["Age:", str(profile.age)])
        if profile.conditions:
            patient_data.append(["Medical Conditions:", ", ".join(profile.conditions) if isinstance(profile.conditions, list) else profile.conditions])
        if profile.allergies:
            patient_data.append(["Allergies:", profile.allergies])
    
    patient_table = Table(patient_data, colWidths=[2*inch, 4*inch])
    patient_table.setStyle(TableStyle([
        ('FONT', (0, 0), (0, -1), 'Helvetica-Bold', 10),
        ('FONT', (1, 0), (-1, -1), 'Helvetica', 10),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#2C2C2C')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(patient_table)
    elements.append(Spacer(1, 0.3 * inch))
    
    # Adherence Summary
    elements.append(Paragraph("Adherence Summary", heading_style))
    summary_data = [
        ["Overall Weekly Adherence:", f"{weekly_percentage}%"],
        ["Doses Taken:", f"{total_taken} of {total_scheduled}"],
        ["Doses Missed:", str(total_scheduled - total_taken)],
        ["Current Streak:", f"{current_streak} day(s)" if current_streak > 0 else "No active streak"],
    ]
    
    summary_table = Table(summary_data, colWidths=[2.5*inch, 3.5*inch])
    summary_table.setStyle(TableStyle([
        ('FONT', (0, 0), (0, -1), 'Helvetica-Bold', 10),
        ('FONT', (1, 0), (-1, -1), 'Helvetica', 10),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#2C2C2C')),
        ('BACKGROUND', (0, 0), (0, 0), colors.HexColor('#F0F0F0') if weekly_percentage >= 90 else colors.HexColor('#FFE5E5')),
        ('BACKGROUND', (1, 0), (1, 0), colors.HexColor('#E8F5E9') if weekly_percentage >= 90 else colors.HexColor('#FFEBEE')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 0.3 * inch))
    
    # Daily Breakdown
    elements.append(Paragraph("Daily Breakdown", heading_style))
    daily_data = [["Date", "Day", "Taken", "Total", "Adherence"]]
    
    for day in days_data:
        status_color = colors.HexColor('#4CAF50') if day['percentage'] >= 90 else (
            colors.HexColor('#FF9800') if day['percentage'] >= 70 else colors.HexColor('#F44336')
        )
        daily_data.append([
            day['date'].strftime("%m/%d/%Y"),
            day['day'],
            str(day['taken']),
            str(day['total']),
            f"{day['percentage']}%"
        ])
    
    daily_table = Table(daily_data, colWidths=[1.2*inch, 1.2*inch, 1*inch, 1*inch, 1.2*inch])
    daily_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E85D5B')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold', 10),
        ('FONT', (0, 1), (-1, -1), 'Helvetica', 9),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8F9FA')]),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(daily_table)
    elements.append(Spacer(1, 0.3 * inch))
    
    # Current Medications
    elements.append(Paragraph("Current Medications", heading_style))
    med_data = [["Medication", "Strength", "Frequency", "Times"]]
    
    for sched in schedules:
        med_data.append([
            sched.medication.brand_name,
            sched.strength or "N/A",
            sched.frequency or "N/A",
            ", ".join(sched.time_of_day) if sched.time_of_day else "N/A"
        ])
    
    med_table = Table(med_data, colWidths=[2*inch, 1.2*inch, 1.2*inch, 2.2*inch])
    med_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E85D5B')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold', 10),
        ('FONT', (0, 1), (-1, -1), 'Helvetica', 9),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('ALIGN', (0, 1), (0, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8F9FA')]),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(med_table)
    
    # Missed Doses (if any)
    if missed_doses:
        elements.append(Spacer(1, 0.3 * inch))
        elements.append(Paragraph("Missed Doses", heading_style))
        missed_data = [["Date", "Medication", "Strength", "Scheduled Time"]]
        
        for missed in missed_doses[:20]:  # Limit to 20 entries
            missed_data.append([
                missed['date'].strftime("%m/%d/%Y"),
                missed['medication'],
                missed['strength'],
                missed['time']
            ])
        
        missed_table = Table(missed_data, colWidths=[1.5*inch, 2*inch, 1.5*inch, 1.5*inch])
        missed_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F44336')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold', 10),
            ('FONT', (0, 1), (-1, -1), 'Helvetica', 9),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#FFEBEE')]),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
        ]))
        elements.append(missed_table)
    
    # Footer
    elements.append(Spacer(1, 0.5 * inch))
    footer_text = "This report was generated by DoseMate. For questions, please consult with your healthcare provider."
    elements.append(Paragraph(footer_text, styles['Normal']))
    
    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    
    filename = f"weekly_report_{user.name or 'patient'}_{today.strftime('%Y%m%d')}.pdf"
    
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

# Add this to your reports_routes.py file after the weekly report

@router.get("/reports/monthly")
async def generate_monthly_report(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user_from_token)
):
    """
    Generate a comprehensive monthly adherence report for healthcare providers
    Returns PDF file - covers last 30 days
    
    Usage: GET /reminders/reports/monthly?token=YOUR_JWT_TOKEN
    """
    
    # Fetch user info
    user_result = await db.execute(
        select(User).where(User.id == current_user.id)
    )
    user = user_result.scalar_one_or_none()
    
    # Fetch user profile
    profile_result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == current_user.id)
    )
    profile = profile_result.scalar_one_or_none()
    
    # Calculate monthly data (30 days)
    today = date.today()
    days_data = []
    total_taken = 0
    total_scheduled = 0
    missed_doses = []
    
    # Get last 30 days
    for i in range(29, -1, -1):  # 30 days total
        target_date = today - timedelta(days=i)
        start_of_day = datetime.combine(target_date, time.min)
        end_of_day = datetime.combine(target_date, time.max)
        
        result = await db.execute(
            select(DoseLog)
            .where(
                DoseLog.user_id == current_user.id,
                DoseLog.scheduled_time >= start_of_day,
                DoseLog.scheduled_time <= end_of_day
            )
            .options(selectinload(DoseLog.schedule).selectinload(MedicationSchedule.medication))
        )
        logs = result.scalars().all()
        
        taken = sum(1 for log in logs if log.status == "taken")
        total = len(logs)
        percentage = round((taken / total * 100)) if total > 0 else 0
        
        total_taken += taken
        total_scheduled += total
        
        days_data.append({
            "date": target_date,
            "day": target_date.strftime("%A"),
            "taken": taken,
            "total": total,
            "percentage": percentage
        })
        
        # Collect missed doses
        for log in logs:
            if log.status == "missed":
                missed_doses.append({
                    "date": target_date,
                    "medication": log.schedule.medication.brand_name,
                    "strength": log.schedule.strength,
                    "time": log.scheduled_time.strftime("%I:%M %p")
                })
    
    monthly_percentage = round((total_taken / total_scheduled * 100)) if total_scheduled > 0 else 0
    
    # Calculate streak
    current_streak = 0
    for day in reversed(days_data):
        if day["percentage"] == 100 and day["total"] > 0:
            current_streak += 1
        else:
            break
    
    # Calculate weekly breakdowns within the month
    weeks_data = []
    for week_num in range(4):  # 4 weeks
        week_start_idx = week_num * 7
        week_end_idx = min(week_start_idx + 7, 30)
        week_days = days_data[week_start_idx:week_end_idx]
        
        week_taken = sum(d['taken'] for d in week_days)
        week_total = sum(d['total'] for d in week_days)
        week_percentage = round((week_taken / week_total * 100)) if week_total > 0 else 0
        
        weeks_data.append({
            "week_num": week_num + 1,
            "start_date": week_days[0]['date'],
            "end_date": week_days[-1]['date'],
            "taken": week_taken,
            "total": week_total,
            "percentage": week_percentage
        })
    
    # Get all active medications
    meds_result = await db.execute(
        select(MedicationSchedule)
        .where(MedicationSchedule.user_id == current_user.id)
        .options(selectinload(MedicationSchedule.medication))
    )
    schedules = meds_result.scalars().all()
    
    # Generate PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#E85D5B'),
        spaceAfter=30,
        alignment=TA_CENTER
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=colors.HexColor('#2C2C2C'),
        spaceAfter=12,
        spaceBefore=20
    )
    
    # Title
    elements.append(Paragraph("Monthly Medication Adherence Report", title_style))
    elements.append(Spacer(1, 0.2 * inch))
    
    # Patient Information
    elements.append(Paragraph("Patient Information", heading_style))
    patient_data = [
        ["Name:", user.name or "Not provided"],
        ["Email:", user.email],
        ["Report Period:", f"{days_data[0]['date'].strftime('%B %d, %Y')} - {days_data[-1]['date'].strftime('%B %d, %Y')}"],
        ["Generated:", datetime.now().strftime("%B %d, %Y at %I:%M %p")],
    ]
    
    if profile:
        if profile.age:
            patient_data.append(["Age:", str(profile.age)])
        if profile.conditions:
            patient_data.append(["Medical Conditions:", ", ".join(profile.conditions) if isinstance(profile.conditions, list) else profile.conditions])
        if profile.allergies:
            patient_data.append(["Allergies:", profile.allergies])
    
    patient_table = Table(patient_data, colWidths=[2*inch, 4*inch])
    patient_table.setStyle(TableStyle([
        ('FONT', (0, 0), (0, -1), 'Helvetica-Bold', 10),
        ('FONT', (1, 0), (-1, -1), 'Helvetica', 10),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#2C2C2C')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(patient_table)
    elements.append(Spacer(1, 0.3 * inch))
    
    # Adherence Summary
    elements.append(Paragraph("Adherence Summary", heading_style))
    summary_data = [
        ["Overall Monthly Adherence:", f"{monthly_percentage}%"],
        ["Doses Taken:", f"{total_taken} of {total_scheduled}"],
        ["Doses Missed:", str(total_scheduled - total_taken)],
        ["Current Streak:", f"{current_streak} day(s)" if current_streak > 0 else "No active streak"],
        ["Perfect Days:", str(sum(1 for d in days_data if d['percentage'] == 100 and d['total'] > 0))]
    ]
    
    summary_table = Table(summary_data, colWidths=[2.5*inch, 3.5*inch])
    summary_table.setStyle(TableStyle([
        ('FONT', (0, 0), (0, -1), 'Helvetica-Bold', 10),
        ('FONT', (1, 0), (-1, -1), 'Helvetica', 10),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#2C2C2C')),
        ('BACKGROUND', (0, 0), (0, 0), colors.HexColor('#F0F0F0') if monthly_percentage >= 90 else colors.HexColor('#FFE5E5')),
        ('BACKGROUND', (1, 0), (1, 0), colors.HexColor('#E8F5E9') if monthly_percentage >= 90 else colors.HexColor('#FFEBEE')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 0.3 * inch))
    
    # Weekly Breakdown
    elements.append(Paragraph("Weekly Breakdown", heading_style))
    weekly_data = [["Week", "Period", "Taken", "Total", "Adherence"]]
    
    for week in weeks_data:
        weekly_data.append([
            f"Week {week['week_num']}",
            f"{week['start_date'].strftime('%m/%d')} - {week['end_date'].strftime('%m/%d')}",
            str(week['taken']),
            str(week['total']),
            f"{week['percentage']}%"
        ])
    
    weekly_table = Table(weekly_data, colWidths=[1*inch, 1.8*inch, 1*inch, 1*inch, 1.2*inch])
    weekly_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E85D5B')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold', 10),
        ('FONT', (0, 1), (-1, -1), 'Helvetica', 9),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8F9FA')]),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(weekly_table)
    elements.append(Spacer(1, 0.3 * inch))
    
    # Current Medications
    elements.append(Paragraph("Current Medications", heading_style))
    med_data = [["Medication", "Strength", "Frequency", "Times"]]
    
    for sched in schedules:
        med_data.append([
            sched.medication.brand_name,
            sched.strength or "N/A",
            sched.frequency or "N/A",
            ", ".join(sched.time_of_day) if sched.time_of_day else "N/A"
        ])
    
    med_table = Table(med_data, colWidths=[2*inch, 1.2*inch, 1.2*inch, 2.2*inch])
    med_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E85D5B')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold', 10),
        ('FONT', (0, 1), (-1, -1), 'Helvetica', 9),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('ALIGN', (0, 1), (0, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8F9FA')]),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(med_table)
    
    # Missed Doses (if any) - Show more for monthly report
    if missed_doses:
        elements.append(Spacer(1, 0.3 * inch))
        elements.append(Paragraph("Missed Doses", heading_style))
        missed_data = [["Date", "Medication", "Strength", "Scheduled Time"]]
        
        for missed in missed_doses[:50]:  # Show up to 50 for monthly
            missed_data.append([
                missed['date'].strftime("%m/%d/%Y"),
                missed['medication'],
                missed['strength'],
                missed['time']
            ])
        
        if len(missed_doses) > 50:
            missed_data.append([
                f"... and {len(missed_doses) - 50} more",
                "", "", ""
            ])
        
        missed_table = Table(missed_data, colWidths=[1.5*inch, 2*inch, 1.5*inch, 1.5*inch])
        missed_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F44336')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold', 10),
            ('FONT', (0, 1), (-1, -1), 'Helvetica', 9),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#FFEBEE')]),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
        ]))
        elements.append(missed_table)
    
    # Footer
    elements.append(Spacer(1, 0.5 * inch))
    footer_text = "This report was generated by DoseMate. For questions, please consult with your healthcare provider."
    elements.append(Paragraph(footer_text, styles['Normal']))
    
    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    
    filename = f"monthly_report_{user.name or 'patient'}_{today.strftime('%Y%m%d')}.pdf"
    
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )