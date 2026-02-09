"""ICS Calendar Generator"""
from datetime import datetime
from icalendar import Calendar, Event, Alarm
import pytz

class ICSGenerator:
    @staticmethod
    def generate_ics(appointment: dict, establishment: dict) -> str:
        """Generate .ics file content."""
        cal = Calendar()
        cal.add('prodid', '-//EasyAgenda//EN')
        cal.add('version', '2.0')
        
        event = Event()
        event.add('summary', f"Appointment - {appointment.get('service_name', 'Service')}")
        event.add('dtstart', appointment['start_time'])
        event.add('dtend', appointment['end_time'])
        event.add('location', establishment.get('address', ''))
        event.add('description', f"Professional: {appointment.get('professional_name', '')}")
        
        # Add alarms
        alarm_24h = Alarm()
        alarm_24h.add('trigger', '-P1D')
        alarm_24h.add('action', 'DISPLAY')
        event.add_component(alarm_24h)
        
        alarm_2h = Alarm()
        alarm_2h.add('trigger', '-PT2H')
        alarm_2h.add('action', 'DISPLAY')
        event.add_component(alarm_2h)
        
        cal.add_component(event)
        return cal.to_ical().decode('utf-8')