from datetime import datetime, date, time, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from app.db.database import get_db
from app.db.models import Medication, MedicationSchedule, DoseLog
from app.core.auth import get_current_user
import pytz
from typing import Optional, List
from pydantic import BaseModel
import statistics
import uuid

router = APIRouter()

@router.get("/today")
async def get_todays_reminders(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    tz = pytz.timezone("America/Toronto")  # user timezone (later dynamic)
    today = date.today()

    # Make "now" naive so comparisons always work consistently
    now_naive = datetime.now(tz).replace(tzinfo=None)

    # 1. Fetch schedules + meds
    result = await db.execute(
        select(MedicationSchedule)
        .where(MedicationSchedule.user_id == current_user.user_id)
        .options(selectinload(MedicationSchedule.medication))
    )
    schedules = result.scalars().all()

    reminders = []

    for sched in schedules:
        # Skip days that don't apply
        if not sched.days or today.strftime("%A") not in sched.days:
            continue

        for t in (sched.time_of_day or []):
            # Parse time strings safely (support multiple formats)
            try:
                parsed = parse_time_12h(t)
            except Exception as e:
                # Skip malformed time entries instead of raising a 500
                print(f"⚠️ Skipping invalid scheduled time '{t}' for schedule {sched.id}:", e)
                continue

            # Build scheduled datetime as NAIVE to match DB
            scheduled_dt = datetime(
                today.year, today.month, today.day,
                parsed.hour, parsed.minute
            )

            # 2. Lookup or create dose log
            # Look for any dose log for this schedule on this day (not just exact time match)
            # This handles snoozed doses where scheduled_time has been shifted
            day_start = datetime(today.year, today.month, today.day, 0, 0, 0)
            day_end = datetime(today.year, today.month, today.day, 23, 59, 59)
            
            log_result = await db.execute(
                select(DoseLog).where(
                    DoseLog.user_id == current_user.user_id,
                    DoseLog.schedule_id == sched.id,
                    DoseLog.scheduled_time >= day_start,
                    DoseLog.scheduled_time <= day_end
                ).order_by(DoseLog.scheduled_time.desc())
            )
            # Get all logs for this schedule today
            all_logs_today = log_result.scalars().all()
            
            # Find the log that matches this specific time slot (within 2 hours window)
            log = None
            for candidate in all_logs_today:
                time_diff_minutes = abs((candidate.scheduled_time - scheduled_dt).total_seconds() / 60)
                if time_diff_minutes <= 120:  # Within 2 hour window (handles snoozes)
                    log = candidate
                    break

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

            # 3. Overdue logic using naive datetime
            overdue = log.status == "pending" and now_naive > scheduled_dt

            reminders.append({
                "id": log.id,
                "name": sched.medication.brand_name,
                "strength": sched.strength,
                "quantity": sched.quantity,
                "time": log.scheduled_time,
                "status": log.status,
                "overdue": overdue,
                "instructions": sched.food_instructions,
            })

    return reminders


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


# ---------------- MARK AS TAKEN ----------------
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
    log.taken_time = datetime.utcnow()
    
    # Detect if dose was taken >20 minutes late (auto-snooze detection)
    LATE_THRESHOLD_MINUTES = 20
    if log.scheduled_time:
        # Make both naive for comparison
        scheduled_naive = log.scheduled_time.replace(tzinfo=None) if log.scheduled_time.tzinfo else log.scheduled_time
        taken_naive = log.taken_time.replace(tzinfo=None) if log.taken_time.tzinfo else log.taken_time
        time_diff = (taken_naive - scheduled_naive).total_seconds() / 60
        
        if time_diff > LATE_THRESHOLD_MINUTES:
            log.snoozed = True
    
    await db.commit()
    await db.refresh(log)

    return {"success": True, "status": log.status, "snoozed": log.snoozed}


# ---------------- SNOOZE ----------------
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

    # Shift scheduled time forward by 15 minutes
    log.scheduled_time += timedelta(minutes=15)
    log.status = "snoozed"
    log.snoozed = True  # Mark as snoozed for pattern detection
    await db.commit()
    await db.refresh(log)

    return {
        "success": True,
        "status": log.status,
        "snoozed": log.snoozed,
        "new_scheduled_time": log.scheduled_time.isoformat()
    }


# ------------------ LOGS ------------------

@router.get("/logs")
async def get_dose_logs(
    schedule_id: Optional[str] = None,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """
    View all DoseLogs for the current user.
    Optionally filter by schedule_id.
    
    Examples:
    - GET /reminders/logs
    - GET /reminders/logs?schedule_id=e66ed58a-d77d-4486-9cd0-712a941dcf8a
    - GET /reminders/logs?schedule_id=e66ed58a-d77d-4486-9cd0-712a941dcf8a&limit=10
    """
    query = select(DoseLog).where(DoseLog.user_id == current_user.user_id)
    
    if schedule_id:
        query = query.where(DoseLog.schedule_id == schedule_id)
    
    query = query.order_by(DoseLog.scheduled_time.desc()).limit(limit)
    
    result = await db.execute(query)
    logs = result.scalars().all()
    
    # Format the response
    formatted_logs = []
    for log in logs:
        # Calculate minutes late if taken
        minutes_late = None
        if log.taken_time and log.scheduled_time:
            scheduled_naive = log.scheduled_time.replace(tzinfo=None) if log.scheduled_time.tzinfo else log.scheduled_time
            taken_naive = log.taken_time.replace(tzinfo=None) if log.taken_time.tzinfo else log.taken_time
            minutes_late = int((taken_naive - scheduled_naive).total_seconds() / 60)
        
        formatted_logs.append({
            "id": str(log.id),
            "schedule_id": str(log.schedule_id),
            "scheduled_time": log.scheduled_time.isoformat() if log.scheduled_time else None,
            "taken_time": log.taken_time.isoformat() if log.taken_time else None,
            "status": log.status,
            "snoozed": log.snoozed,
            "minutes_late": minutes_late
        })
    
    return {
        "total": len(formatted_logs),
        "logs": formatted_logs
    }


@router.delete("/logs")
async def delete_dose_logs(
    schedule_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """
    TEST HELPER: Delete all DoseLogs for testing.
    Optionally filter by schedule_id.
    
    WARNING: This will delete dose logs!
    
    Examples:
    - DELETE /reminders/logs  (deletes ALL your dose logs)
    - DELETE /reminders/logs?schedule_id=e66ed58a-d77d-4486-9cd0-712a941dcf8a
    """
    query = select(DoseLog).where(DoseLog.user_id == current_user.user_id)
    
    if schedule_id:
        query = query.where(DoseLog.schedule_id == schedule_id)
    
    result = await db.execute(query)
    logs = result.scalars().all()
    
    count = len(logs)
    
    for log in logs:
        await db.delete(log)
    
    await db.commit()
    
    return {
        "success": True,
        "message": f"Deleted {count} dose logs",
        "deleted_count": count
    }

# ---------------- ADAPTATION SUGGESTIONS ----------------

class AdaptationSuggestion(BaseModel):
    schedule_id: str
    medication_name: str
    current_time: str
    suggested_time: str
    confidence_score: int
    snooze_count: int
    total_doses: int
    median_actual_time: str


async def detect_snooze_pattern(
    schedule_id: uuid.UUID,
    specific_time: Optional[str],
    db: AsyncSession
) -> Optional[dict]:
    """
    Analyzes recent DoseLogs to detect snooze patterns for a specific schedule and time.
    Returns suggestion dict if pattern found, None otherwise.
    
    Args:
        schedule_id: The medication schedule to analyze
        specific_time: The specific time of day to analyze (e.g., "9:00 AM")
        db: Database session
    
    Returns:
        Dict with suggestion details or None if no pattern detected
    """
    LOOKBACK_WINDOW = 5
    SNOOZE_THRESHOLD_COUNT = 3
    MIN_CONFIDENCE_SCORE = 60
    
    # Fetch the schedule to check if it's PRN
    sched_result = await db.execute(
        select(MedicationSchedule).where(MedicationSchedule.id == schedule_id)
    )
    schedule = sched_result.scalar_one_or_none()
    if not schedule or schedule.as_needed:
        return None  # Skip PRN medications
    
    # Fetch last N DoseLogs for this schedule, ordered by scheduled_time descending
    result = await db.execute(
        select(DoseLog)
        .where(
            DoseLog.schedule_id == schedule_id,
            DoseLog.status == "taken",
            DoseLog.taken_time != None
        )
        .order_by(DoseLog.scheduled_time.desc())
        .limit(LOOKBACK_WINDOW * 2)  # Get more to filter by specific time
    )
    all_logs = result.scalars().all()
    
    # Filter logs for the specific time of day if provided
    if specific_time:
        try:
            target_time = parse_time_12h(specific_time)
            logs = []
            for log in all_logs:
                if log.scheduled_time:
                    log_time = log.scheduled_time.time()
                    # Match if within 5 minutes of target time
                    time_diff = abs((datetime.combine(date.today(), log_time) - 
                                   datetime.combine(date.today(), target_time)).total_seconds() / 60)
                    if time_diff <= 5:
                        logs.append(log)
                        if len(logs) >= LOOKBACK_WINDOW:
                            break
        except ValueError:
            logs = all_logs[:LOOKBACK_WINDOW]
    else:
        logs = all_logs[:LOOKBACK_WINDOW]
    
    if len(logs) < LOOKBACK_WINDOW:
        return None  # Not enough data
    
    # Count snoozes
    snooze_count = sum(1 for log in logs if log.snoozed)
    
    if snooze_count < SNOOZE_THRESHOLD_COUNT:
        return None  # Not enough snoozes to suggest adaptation
    
    # Calculate median actual taken time
    taken_times = []
    for log in logs:
        if log.taken_time:
            taken_naive = log.taken_time.replace(tzinfo=None) if log.taken_time.tzinfo else log.taken_time
            taken_times.append(taken_naive.time())
    
    if not taken_times:
        return None
    
    # Convert times to minutes since midnight for median calculation
    minutes_list = [(t.hour * 60 + t.minute) for t in taken_times]
    median_minutes = int(statistics.median(minutes_list))
    median_hour = median_minutes // 60
    median_minute = median_minutes % 60
    median_time = time(median_hour, median_minute)
    
    # Check if suggested time is earlier than scheduled (skip if so)
    if logs[0].scheduled_time:
        scheduled_time = logs[0].scheduled_time.time()
        if median_time < scheduled_time:
            return None  # Don't suggest earlier times
    
    # Calculate confidence score
    # Higher snooze rate = higher confidence
    snooze_rate = (snooze_count / len(logs)) * 100
    # Consistency of taken times (lower std dev = higher confidence)
    if len(minutes_list) > 1:
        time_std = statistics.stdev(minutes_list)
        consistency_score = max(0, 100 - time_std)  # Lower std = higher score
        confidence = int((snooze_rate * 0.6) + (consistency_score * 0.4))
    else:
        confidence = int(snooze_rate)
    
    if confidence < MIN_CONFIDENCE_SCORE:
        return None
    
    return {
        "suggested_time": median_time.strftime("%I:%M %p"),
        "confidence_score": min(confidence, 100),
        "snooze_count": snooze_count,
        "total_doses": len(logs),
        "median_actual_time": median_time.strftime("%I:%M %p")
    }



@router.get("/adaptation-suggestions", response_model=List[AdaptationSuggestion])
async def get_adaptation_suggestions(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """
    Check all active schedules for snooze patterns and return adaptation suggestions.
    """
    # Fetch all active schedules for the user
    result = await db.execute(
        select(MedicationSchedule)
        .where(MedicationSchedule.user_id == current_user.user_id)
        .options(selectinload(MedicationSchedule.medication))
    )
    schedules = result.scalars().all()
    
    suggestions = []
    
    for sched in schedules:
        # Skip if already adapted or PRN
        if sched.as_needed or sched.preferred_time:
            continue
        print("Schedule: ", sched)
        # Check each time of day independently
        for time_str in (sched.time_of_day or []):
            pattern = await detect_snooze_pattern(sched.id, time_str, db)
            
            if pattern:
                suggestions.append(AdaptationSuggestion(
                    schedule_id=str(sched.id),
                    medication_name=sched.medication.brand_name,
                    current_time=time_str,
                    suggested_time=pattern["suggested_time"],
                    confidence_score=pattern["confidence_score"],
                    snooze_count=pattern["snooze_count"],
                    total_doses=pattern["total_doses"],
                    median_actual_time=pattern["median_actual_time"]
                ))
    
    return suggestions



class AcceptAdaptationRequest(BaseModel):
    current_time: str
    suggested_time: str
    confidence_score: int


@router.post("/adaptation-suggestions/{schedule_id}/accept")
async def accept_adaptation(
    schedule_id: str,
    request: AcceptAdaptationRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """
    Accept an adaptation suggestion and update the schedule.
    
    Body:
    {
        "current_time": "9:00 AM",
        "suggested_time": "09:30 AM",
        "confidence_score": 75
    }
    """
    result = await db.execute(
        select(MedicationSchedule).where(
            MedicationSchedule.id == schedule_id,
            MedicationSchedule.user_id == current_user.user_id
        )
    )
    schedule = result.scalar_one_or_none()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    
    # Update the time_of_day array
    if schedule.time_of_day and request.current_time in schedule.time_of_day:
        # Replace the old time with the new suggested time
        new_times = [request.suggested_time if t == request.current_time else t for t in schedule.time_of_day]
        schedule.time_of_day = new_times
        
        # Store adaptation metadata
        schedule.preferred_time = request.suggested_time
        schedule.adapted_from_time = request.current_time
        schedule.adaptation_score = request.confidence_score
        
        await db.commit()
        await db.refresh(schedule)
        
        return {
            "success": True,
            "message": f"Reminder time updated from {request.current_time} to {request.suggested_time}",
            "new_times": schedule.time_of_day
        }
    else:
        raise HTTPException(status_code=400, detail="Current time not found in schedule")


@router.post("/adaptation-suggestions/{schedule_id}/reject")
async def reject_adaptation(
    schedule_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """
    Reject an adaptation suggestion and reset the adaptation score.
    """
    result = await db.execute(
        select(MedicationSchedule).where(
            MedicationSchedule.id == schedule_id,
            MedicationSchedule.user_id == current_user.user_id
        )
    )
    schedule = result.scalar_one_or_none()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    
    # Reset adaptation tracking
    schedule.adaptation_score = 0
    
    await db.commit()
    
    return {
        "success": True,
        "message": "Adaptation suggestion rejected"
    }

# ---------------- TEST HELPER ENDPOINTS ----------------

class CreateTestDoseRequest(BaseModel):
    schedule_id: str
    scheduled_date: str  # Format: "2025-11-22"
    scheduled_time: str  # Format: "9:00 AM"
    taken_time: str      # Format: "9:30 AM" or "9:30" (24h)
    days_ago: Optional[int] = 0  # Alternative to scheduled_date

@router.post("/test/create-pattern")
async def create_test_pattern(
    schedule_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """
    TEST HELPER: Create a full snooze pattern (5 doses) for testing.
    Creates doses for the last 5 days with a pattern of taking meds ~30 min late.
    
    Example: POST /reminders/test/create-pattern?schedule_id=e66ed58a-d77d-4486-9cd0-712a941dcf8a
    """
    # Verify schedule exists
    result = await db.execute(
        select(MedicationSchedule).where(
            MedicationSchedule.id == schedule_id,
            MedicationSchedule.user_id == current_user.user_id
        )
    )
    schedule = result.scalar_one_or_none()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    
    # Get the first scheduled time from the schedule
    if not schedule.time_of_day or len(schedule.time_of_day) == 0:
        raise HTTPException(status_code=400, detail="Schedule has no time_of_day set")
    
    scheduled_time_str = schedule.time_of_day[0]
    scheduled_time_obj = parse_time_12h(scheduled_time_str)
    
    # Create pattern: 5 doses over last 5 days, taken ~25-35 min late
    tz = pytz.timezone("America/Toronto")
    today = datetime.now(tz).date()
    
    late_minutes = [28, 32, 25, 35, 22]  # Pattern of lateness
    created_logs = []
    
    for i in range(5):
        days_ago = 4 - i  # 4, 3, 2, 1, 0
        dose_date = today - timedelta(days=days_ago)
        
        scheduled_dt = datetime(
            dose_date.year, dose_date.month, dose_date.day,
            scheduled_time_obj.hour, scheduled_time_obj.minute
        )
        
        taken_dt = scheduled_dt + timedelta(minutes=late_minutes[i])
        is_snoozed = late_minutes[i] > 20
        
        log = DoseLog(
            user_id=current_user.user_id,
            schedule_id=schedule_id,
            scheduled_time=scheduled_dt,
            taken_time=taken_dt,
            status="taken",
            snoozed=is_snoozed
        )
        
        db.add(log)
        created_logs.append({
            "date": dose_date.isoformat(),
            "scheduled": scheduled_dt.strftime("%I:%M %p"),
            "taken": taken_dt.strftime("%I:%M %p"),
            "minutes_late": late_minutes[i],
            "snoozed": is_snoozed
        })
    
    await db.commit()
    
    return {
        "success": True,
        "message": f"Created {len(created_logs)} test doses with snooze pattern",
        "pattern": created_logs,
        "next_step": f"Call GET /reminders/adaptation-suggestions to see the suggestion"
    }

def parse_time_12h(time_str: str):
    """
    Try several common time formats and return a time object.
    Raises ValueError if no format matches.
    """
    fmts = ["%I:%M %p", "%H:%M", "%I:%M%p", "%I %p"]
    for f in fmts:
        try:
            return datetime.strptime(time_str, f).time()
        except Exception:
            continue
    # As a last resort, try to strip whitespace and lowercase AM/PM spacing issues
    normalized = time_str.replace(".", "").replace("am", " AM").replace("pm", " PM").strip()
    for f in fmts:
        try:
            return datetime.strptime(normalized, f).time()
        except Exception:
            continue
    raise ValueError(f"Unrecognized time format: '{time_str}'")