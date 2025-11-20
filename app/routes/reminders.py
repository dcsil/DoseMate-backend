from datetime import datetime, date, time, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from app.db.database import get_db
from app.db.models import Medication, MedicationSchedule, DoseLog
from app.core.auth import get_current_user
import pytz

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
            # Parse "8:00 AM" safely
            parsed = parse_time_12h(t)

            # Build scheduled datetime as NAIVE to match DB
            scheduled_dt = datetime(
                today.year, today.month, today.day,
                parsed.hour, parsed.minute
            )

            # 2. Lookup or create dose log
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

            # 3. Overdue logic using naive datetime
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
    log.taken_at = datetime.utcnow()
    await db.commit()
    await db.refresh(log)

    return {"success": True, "status": log.status}


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

    # Shift scheduled time forward by 15 minutes (or any business rule)
    log.scheduled_time += timedelta(minutes=15)
    log.status = "snoozed"
    await db.commit()
    await db.refresh(log)

    return {
        "success": True,
        "status": log.status,
        "new_scheduled_time": log.scheduled_time.isoformat()
    }



def parse_time_12h(time_str: str):
    return datetime.strptime(time_str, "%I:%M %p").time()
