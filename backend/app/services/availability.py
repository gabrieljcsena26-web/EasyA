"""Availability Engine - EPIC LEVEL
Calculates available slots automatically based on:
- Establishment working hours
- Professional schedules (individual overrides)
- Service duration + buffers
- Existing appointments
- Breaks and closures
- Timezone handling
- Confirmation policies (minLeadHours, quietHours)
"""
import logging
from datetime import datetime, timedelta, time as dt_time
from typing import List, Dict, Optional, Tuple
from zoneinfo import ZoneInfo
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.models.models import Establishment, Professional, Service, Appointment, AppointmentStatus

logger = logging.getLogger(__name__)


class AvailabilityEngine:
    """EPIC availability calculation engine."""
    
    def __init__(self, db: Session, establishment_id: str):
        """Initialize engine with establishment context."""
        self.db = db
        self.establishment = db.query(Establishment).filter(
            Establishment.id == establishment_id
        ).first()
        
        if not self.establishment:
            raise ValueError(f"Establishment not found: {establishment_id}")
        
        # Parse booking settings
        self.booking_settings = self.establishment.booking_settings or {}
        self.min_lead_hours = self.booking_settings.get('min_lead_hours', 4)
        self.quiet_hours_start = self._parse_time(self.booking_settings.get('quiet_hours_start', '21:00'))
        self.quiet_hours_end = self._parse_time(self.booking_settings.get('quiet_hours_end', '08:00'))
        
        # Get timezone
        try:
            self.tz = ZoneInfo(self.establishment.timezone)
        except Exception:
            logger.warning(f"Invalid timezone {self.establishment.timezone}, using UTC")
            self.tz = ZoneInfo('UTC')
    
    @staticmethod
    def _parse_time(time_str: str) -> dt_time:
        """Parse HH:MM to time object."""
        try:
            hour, minute = map(int, time_str.split(':'))
            return dt_time(hour, minute)
        except Exception:
            return dt_time(8, 0)  # Default 08:00
    
    def get_available_slots(
        self,
        service_id: str,
        professional_id: str,
        date: datetime.date,
        slot_duration_minutes: int = 30
    ) -> List[Dict]:
        """Get available time slots for a specific day.
        
        Args:
            service_id: Service ID
            professional_id: Professional ID
            date: Date to check
            slot_duration_minutes: Slot granularity (default 30min)
            
        Returns:
            List of slots with availability info
        """
        # Get service
        service = self.db.query(Service).filter(Service.id == service_id).first()
        if not service:
            raise ValueError(f"Service not found: {service_id}")
        
        # Get professional
        professional = self.db.query(Professional).filter(
            Professional.id == professional_id
        ).first()
        if not professional:
            raise ValueError(f"Professional not found: {professional_id}")
        
        # Total duration needed (service + buffers)
        total_duration = (
            service.duration_minutes +
            service.buffer_before_minutes +
            service.buffer_after_minutes
        )
        
        # Get working hours for this day
        working_hours = self._get_working_hours(professional, date)
        if not working_hours:
            return []  # Not a working day
        
        # Get breaks for this day
        breaks = self._get_breaks(professional, date)
        
        # Get existing appointments
        existing_appointments = self._get_existing_appointments(professional_id, date)
        
        # Generate slots
        slots = []
        current_dt = datetime.combine(date, working_hours['start'], tzinfo=self.tz)
        end_dt = datetime.combine(date, working_hours['end'], tzinfo=self.tz)
        
        while current_dt + timedelta(minutes=total_duration) <= end_dt:
            slot_end = current_dt + timedelta(minutes=total_duration)
            
            # Check if slot is available
            is_available, reason = self._is_slot_available(
                current_dt,
                slot_end,
                breaks,
                existing_appointments,
                total_duration
            )
            
            # Apply minimum lead time policy
            now = datetime.now(self.tz)
            min_booking_time = now + timedelta(hours=self.min_lead_hours)
            if current_dt < min_booking_time:
                is_available = False
                reason = \"too_soon\"
            
            # Apply quiet hours policy
            if self._is_in_quiet_hours(current_dt.time()):
                is_available = False
                reason = \"quiet_hours\"
            
            slots.append({
                'time': current_dt.strftime('%H:%M'),
                'datetime': current_dt.isoformat(),
                'available': is_available,
                'reason': reason if not is_available else None
            })
            
            # Move to next slot
            current_dt += timedelta(minutes=slot_duration_minutes)
        
        return slots
    
    def _get_working_hours(
        self,
        professional: Professional,
        date: datetime.date
    ) -> Optional[Dict[str, dt_time]]:
        """Get working hours for professional on specific date.
        
        Returns:
            Dict with 'start' and 'end' times, or None if not working
        """
        day_name = date.strftime('%A').lower()  # monday, tuesday, etc.
        
        # Check professional's individual schedule first
        weekly_schedule = professional.weekly_schedule or []
        for day_config in weekly_schedule:
            if day_config.get('day') == day_name:
                if not day_config.get('enabled', True):
                    return None  # Not working this day
                
                return {
                    'start': self._parse_time(day_config.get('start_time', '09:00')),
                    'end': self._parse_time(day_config.get('end_time', '18:00'))
                }
        
        # Fallback to establishment default schedule
        establishment_schedule = self.booking_settings.get('weekly_schedule', [])
        for day_config in establishment_schedule:
            if day_config.get('day') == day_name:
                if not day_config.get('enabled', True):
                    return None
                
                return {
                    'start': self._parse_time(day_config.get('start_time', '09:00')),
                    'end': self._parse_time(day_config.get('end_time', '18:00'))
                }
        
        # Default: 9am-6pm if nothing configured
        return {
            'start': dt_time(9, 0),
            'end': dt_time(18, 0)
        }
    
    def _get_breaks(
        self,
        professional: Professional,
        date: datetime.date
    ) -> List[Tuple[datetime, datetime]]:
        """Get break periods for professional on specific date.
        
        Returns:
            List of (break_start, break_end) tuples
        """
        breaks = []
        
        # Professional's individual breaks
        break_periods = professional.breaks or []
        for break_info in break_periods:
            start_time = self._parse_time(break_info.get('start_time', '12:00'))
            end_time = self._parse_time(break_info.get('end_time', '13:00'))
            
            break_start = datetime.combine(date, start_time, tzinfo=self.tz)
            break_end = datetime.combine(date, end_time, tzinfo=self.tz)
            
            breaks.append((break_start, break_end))
        
        # If no individual breaks, use establishment defaults
        if not breaks:
            daily_breaks = self.booking_settings.get('daily_breaks', [])
            for break_info in daily_breaks:
                start_time = self._parse_time(break_info.get('start_time', '12:00'))
                end_time = self._parse_time(break_info.get('end_time', '13:00'))
                
                break_start = datetime.combine(date, start_time, tzinfo=self.tz)
                break_end = datetime.combine(date, end_time, tzinfo=self.tz)
                
                breaks.append((break_start, break_end))
        
        return breaks
    
    def _get_existing_appointments(
        self,
        professional_id: str,
        date: datetime.date
    ) -> List[Tuple[datetime, datetime]]:
        """Get existing confirmed appointments for professional on date.
        
        Returns:
            List of (appointment_start, appointment_end) tuples
        """
        start_of_day = datetime.combine(date, dt_time(0, 0), tzinfo=self.tz)
        end_of_day = datetime.combine(date, dt_time(23, 59, 59), tzinfo=self.tz)
        
        appointments = self.db.query(Appointment).filter(
            and_(
                Appointment.professional_id == professional_id,
                Appointment.start_time >= start_of_day,
                Appointment.start_time < end_of_day,
                Appointment.status.in_([
                    AppointmentStatus.CONFIRMED,
                    AppointmentStatus.PENDING
                ])
            )
        ).all()
        
        return [(apt.start_time, apt.end_time) for apt in appointments]
    
    def _is_slot_available(
        self,
        slot_start: datetime,
        slot_end: datetime,
        breaks: List[Tuple[datetime, datetime]],
        appointments: List[Tuple[datetime, datetime]],
        duration_minutes: int
    ) -> Tuple[bool, Optional[str]]:
        """Check if slot is available.
        
        Returns:
            (is_available, reason_if_not_available)
        """
        # Check overlap with breaks
        for break_start, break_end in breaks:
            if self._overlaps(slot_start, slot_end, break_start, break_end):
                return False, \"break\"
        
        # Check overlap with existing appointments
        for apt_start, apt_end in appointments:
            if self._overlaps(slot_start, slot_end, apt_start, apt_end):
                return False, \"booked\"
        
        return True, None
    
    @staticmethod
    def _overlaps(
        start1: datetime,
        end1: datetime,
        start2: datetime,
        end2: datetime
    ) -> bool:
        """Check if two time ranges overlap."""
        return start1 < end2 and end1 > start2
    
    def _is_in_quiet_hours(self, check_time: dt_time) -> bool:
        """Check if time is in quiet hours."""
        if self.quiet_hours_start < self.quiet_hours_end:
            # Normal case: 21:00 - 08:00 (crosses midnight)
            return check_time >= self.quiet_hours_start or check_time <= self.quiet_hours_end
        else:
            # Edge case: quiet hours don't cross midnight
            return self.quiet_hours_start <= check_time <= self.quiet_hours_end
    
    def get_availability_summary(
        self,
        service_id: str,
        professional_id: str,
        start_date: datetime.date,
        days: int = 30
    ) -> List[Dict]:
        """Get availability summary for multiple days.
        
        Args:
            service_id: Service ID
            professional_id: Professional ID
            start_date: Start date
            days: Number of days to check
            
        Returns:
            List of daily summaries with available slot count
        """
        summary = []
        
        for day_offset in range(days):
            check_date = start_date + timedelta(days=day_offset)
            slots = self.get_available_slots(service_id, professional_id, check_date)
            
            available_count = sum(1 for slot in slots if slot['available'])
            
            summary.append({
                'date': check_date.isoformat(),
                'total_slots': len(slots),
                'available_slots': available_count,
                'has_availability': available_count > 0
            })
        
        return summary
