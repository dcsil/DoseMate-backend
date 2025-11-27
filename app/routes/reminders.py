from datetime import datetime, date, time, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import func, and_, or_
from app.db.database import get_db
from app.db.models import Medication, MedicationSchedule, DoseLog
from app.core.auth import get_current_user
import pytz

router = APIRouter()

# ============================================================================
# EXISTING ENDPOINT - Keep as is
# ============================================================================
@router.get("/today")
async def get_todays_reminders(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    tz = pytz.timezone("America/Toronto")
    today = date.today()
    now_naive = datetime.now(tz).replace(tzinfo=None)

    result = await db.execute(
        select(MedicationSchedule)
        .where(MedicationSchedule.user_id == current_user.user_id)
        .options(selectinload(MedicationSchedule.medication))
    )
    schedules = result.scalars().all()

    reminders = []

    for sched in schedules:
        if not sched.days or today.strftime("%A") not in sched.days:
            continue

        for t in (sched.time_of_day or []):
            parsed = parse_time_12h(t)
            scheduled_dt = datetime(
                today.year, today.month, today.day,
                parsed.hour, parsed.minute
            )

            log_result = await db.execute(
                select(DoseLog).where(
                    DoseLog.user_id == current_user.user_id,
                    DoseLog.schedule_id == sched.id,
                    DoseLog.scheduled_time == scheduled_dt
                )
            )
            log = log_result.scalar_one_or_none()

            if not log:
                log = DoseLog(
                    user_id=current_user.user_id,
                    schedule_id=sched.id,
                    scheduled_time=scheduled_dt,
                    status="pending"
                )
                db.add(log)
                await db.commit()
                await db.refresh(log)

            overdue = log.status == "pending" and now_naive > scheduled_dt

            reminders.append({
                "id": log.id,
                "name": sched.medication.brand_name,
                "strength": sched.strength,
                "quantity": sched.quantity,
                "time": t,
                "status": log.status,
                "overdue": overdue,
                "instructions": sched.food_instructions,
            })

    return reminders


# ============================================================================
# NEW ENDPOINT 1: TODAY'S ADHERENCE STATS
# ============================================================================
@router.get("/adherence/today")
async def get_today_adherence(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """
    Get today's adherence statistics
    """
    today = date.today()
    start_of_day = datetime.combine(today, time.min)
    end_of_day = datetime.combine(today, time.max)

    # Get all dose logs for today
    result = await db.execute(
        select(DoseLog)
        .where(
            DoseLog.user_id == current_user.user_id,
            DoseLog.scheduled_time >= start_of_day,
            DoseLog.scheduled_time <= end_of_day
        )
    )
    logs = result.scalars().all()

    # Count by status
    total = len(logs)
    taken = sum(1 for log in logs if log.status == "taken")
    missed = sum(1 for log in logs if log.status == "missed")
    pending = sum(1 for log in logs if log.status == "pending")

    percentage = round((taken / total * 100)) if total > 0 else 0

    return {
        "date": today.isoformat(),
        "taken": taken,
        "missed": missed,
        "pending": pending,
        "total": total,
        "percentage": percentage
    }


# ============================================================================
# NEW ENDPOINT 2: WEEKLY ADHERENCE (Last 7 Days)
# ============================================================================
@router.get("/adherence/week")
async def get_weekly_adherence(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """
    Get adherence for the last 7 days
    Returns daily breakdown + overall stats
    """
    today = date.today()
    days_data = []
    
    total_taken = 0
    total_scheduled = 0
    perfect_days = 0  # Days with 100% adherence

    for i in range(6, -1, -1):  # Last 7 days (oldest to newest)
        target_date = today - timedelta(days=i)
        start_of_day = datetime.combine(target_date, time.min)
        end_of_day = datetime.combine(target_date, time.max)

        # Get all dose logs for this day
        result = await db.execute(
            select(DoseLog)
            .where(
                DoseLog.user_id == current_user.user_id,
                DoseLog.scheduled_time >= start_of_day,
                DoseLog.scheduled_time <= end_of_day
            )
        )
        logs = result.scalars().all()

        taken = sum(1 for log in logs if log.status == "taken")
        total = len(logs)
        percentage = round((taken / total * 100)) if total > 0 else 0

        if percentage == 100 and total > 0:
            perfect_days += 1

        total_taken += taken
        total_scheduled += total

        days_data.append({
            "date": target_date.isoformat(),
            "day": target_date.strftime("%a"),  # Mon, Tue, etc
            "taken": taken,
            "total": total,
            "percentage": percentage,
            "is_today": target_date == today
        })

    # Calculate overall weekly percentage
    weekly_percentage = round((total_taken / total_scheduled * 100)) if total_scheduled > 0 else 0

    # Calculate current streak (consecutive days with 100% adherence)
    current_streak = 0
    for day in reversed(days_data):
        if day["percentage"] == 100 and day["total"] > 0:
            current_streak += 1
        else:
            break

    return {
        "days": days_data,
        "summary": {
            "taken": total_taken,
            "total": total_scheduled,
            "percentage": weekly_percentage,
            "perfect_days": perfect_days,
            "current_streak": current_streak
        }
    }


# ============================================================================
# NEW ENDPOINT 3: MONTHLY ADHERENCE (Last 30 Days)
# ============================================================================
@router.get("/adherence/month")
async def get_monthly_adherence(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """
    Get adherence for the last 30 days
    """
    today = date.today()
    start_date = today - timedelta(days=29)  # Last 30 days including today
    start_of_period = datetime.combine(start_date, time.min)
    end_of_period = datetime.combine(today, time.max)

    # Get all dose logs for the period
    result = await db.execute(
        select(DoseLog)
        .where(
            DoseLog.user_id == current_user.user_id,
            DoseLog.scheduled_time >= start_of_period,
            DoseLog.scheduled_time <= end_of_period
        )
    )
    logs = result.scalars().all()

    taken = sum(1 for log in logs if log.status == "taken")
    missed = sum(1 for log in logs if log.status == "missed")
    total = len(logs)

    percentage = round((taken / total * 100)) if total > 0 else 0

    # Calculate weekly breakdown within the month
    weeks_data = []
    for week_start in range(0, 30, 7):
        week_end = min(week_start + 6, 29)
        week_start_date = today - timedelta(days=29 - week_start)
        week_end_date = today - timedelta(days=29 - week_end)
        
        week_logs = [
            log for log in logs
            if week_start_date <= log.scheduled_time.date() <= week_end_date
        ]
        
        week_taken = sum(1 for log in week_logs if log.status == "taken")
        week_total = len(week_logs)
        week_percentage = round((week_taken / week_total * 100)) if week_total > 0 else 0
        
        weeks_data.append({
            "week": f"Week {len(weeks_data) + 1}",
            "start_date": week_start_date.isoformat(),
            "end_date": week_end_date.isoformat(),
            "taken": week_taken,
            "total": week_total,
            "percentage": week_percentage
        })

    return {
        "period": {
            "start_date": start_date.isoformat(),
            "end_date": today.isoformat(),
            "days": 30
        },
        "summary": {
            "taken": taken,
            "missed": missed,
            "total": total,
            "percentage": percentage
        },
        "weeks": weeks_data
    }


# ============================================================================
# NEW ENDPOINT 4: RECENT ACTIVITY (Last Taken Doses)
# ============================================================================
@router.get("/recent-activity")
async def get_recent_activity(
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """
    Get recently taken doses with timestamps
    """
    result = await db.execute(
        select(DoseLog)
        .where(
            DoseLog.user_id == current_user.user_id,
            DoseLog.status == "taken",
            DoseLog.taken_time.isnot(None)
        )
        .order_by(DoseLog.taken_time.desc())
        .limit(limit)
        .options(selectinload(DoseLog.schedule).selectinload(MedicationSchedule.medication))
    )
    logs = result.scalars().all()

    activities = []
    for log in logs:
        sched = log.schedule
        med = sched.medication

        # Format the taken time
        taken_dt = log.taken_time
        if isinstance(taken_dt, datetime):
            time_str = taken_dt.strftime("%I:%M %p")
            date_str = taken_dt.strftime("%b %d")
            
            # Check if today
            if taken_dt.date() == date.today():
                display_time = f"Today at {time_str}"
            elif taken_dt.date() == date.today() - timedelta(days=1):
                display_time = f"Yesterday at {time_str}"
            else:
                display_time = f"{date_str} at {time_str}"
        else:
            display_time = "Recently"

        activities.append({
            "id": str(log.id),
            "medication_name": med.brand_name,
            "strength": sched.strength,
            "quantity": sched.quantity,
            "taken_at": log.taken_time.isoformat() if log.taken_time else None,
            "scheduled_time": log.scheduled_time.strftime("%I:%M %p"),
            "display_time": display_time,
            "status": "taken"
        })

    return activities


# ============================================================================
# EXISTING ENDPOINTS - Keep as is
# ============================================================================
@router.post("/{dose_id}/mark-taken")
async def mark_taken(
    dose_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    result = await db.execute(
        select(DoseLog).where(DoseLog.id == dose_id, DoseLog.user_id == current_user.user_id)
    )
    log = result.scalar_one_or_none()
    if not log:
        raise HTTPException(status_code=404, detail="Dose log not found")

    log.status = "taken"
    log.taken_time = datetime.utcnow()  # Use taken_time instead of taken_at
    await db.commit()
    await db.refresh(log)

    return {"success": True, "status": log.status}


@router.post("/{dose_id}/snooze")
async def snooze_dose(
    dose_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    result = await db.execute(
        select(DoseLog).where(DoseLog.id == dose_id, DoseLog.user_id == current_user.user_id)
    )
    log = result.scalar_one_or_none()
    if not log:
        raise HTTPException(status_code=404, detail="Dose log not found")

    log.scheduled_time += timedelta(minutes=15)
    log.snoozed = True
    await db.commit()
    await db.refresh(log)

    return {
        "success": True,
        "snoozed": log.snoozed,
        "new_scheduled_time": log.scheduled_time.isoformat()
    }


# ============================================================================
# HELPER FUNCTION
# ============================================================================
def parse_time_12h(time_str: str):
    return datetime.strptime(time_str, "%I:%M %p").time()