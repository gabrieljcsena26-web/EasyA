from datetime import datetime, timedelta
from fastapi.testclient import TestClient

from main import app


def try_at_time(token: str, date: str, time_str: str, service_id: int, professional_id: int):
    client = TestClient(app)
    payload = {
        "service_id": service_id,
        "professional_id": professional_id,
        "date": date,
        "start_time": time_str,
        "channel": "web",
        "customer_name": "Slot Tester",
        "customer_whatsapp": "+0000000001",
    }
    r = client.post("/appointments", json=payload)
    print(f"Attempt create at {time_str} =>", r.status_code, r.json())
    return r


def find_via_availability(service_id: int, date: str, professional_id: int | None = None):
    client = TestClient(app)
    params = {"date": date, "service_id": service_id}
    if professional_id is not None:
        params["professional_id"] = professional_id
    r = client.get("/availability", params=params)
    print("GET /availability =>", r.status_code)
    return r


def main():
    client = TestClient(app)
    # 1) config
    cfg = client.get("/config").json()
    services = cfg.get("services") or []
    professionals = cfg.get("professionals") or []
    if not services or not professionals:
        print("No services/professionals")
        return

    service_id = services[0]["id"]
    professional_id = professionals[0]["id"]

    date = (datetime.now().date() + timedelta(days=1)).isoformat()

    # 1) Try at 11:00
    print("--- Trying direct 11:00 ---")
    try_at_time(None, date, "11:00", service_id, professional_id)

    # 2) Query availability and try first free slot for the professional
    print("--- Querying availability ---")
    av = find_via_availability(service_id, date, professional_id)
    if av.status_code != 200:
        print("Availability error", av.text)
        return

    data = av.json()
    availability = data.get("availability") or []
    target_slots = []
    for item in availability:
        if str(item.get("professional_id")) == str(professional_id) or int(item.get("professional_id")) == professional_id:
            target_slots = item.get("slots") or []
            break

    if not target_slots:
        print("No free slots found for professional")
        return

    # Try the first slot
    slot = target_slots[0]
    print(f"--- Trying availability slot {slot} ---")
    try_at_time(None, date, slot, service_id, professional_id)


if __name__ == '__main__':
    main()
