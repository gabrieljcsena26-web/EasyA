import base64, json, datetime

# Token gerado (7 dias)
TOK = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzbHVnIjoiY2xpbGljYTEyMyIsInJvbGUiOiJhZG1pbiIsImV4cCI6MTc2OTAzMDUxOH0.M_xMXNhHz0uCmnBvClxTqvH7KV-snck8JvoCrJOXSIE"

payload = TOK.split('.')[1]
# pad base64
payload += '=' * (-len(payload) % 4)
data = json.loads(base64.urlsafe_b64decode(payload).decode())
exp = data.get('exp')
now_ts = int(datetime.datetime.now(datetime.timezone.utc).timestamp())
print('payload:', json.dumps(data, indent=2, ensure_ascii=False))
print('\nexp (unix):', exp)
print('exp (UTC):', datetime.datetime.fromtimestamp(exp, datetime.timezone.utc).isoformat())
print('exp (local):', datetime.datetime.fromtimestamp(exp).astimezone().isoformat())
print('now (unix UTC):', now_ts)
print('now (UTC):', datetime.datetime.fromtimestamp(now_ts, datetime.timezone.utc).isoformat())
print('now (local):', datetime.datetime.fromtimestamp(now_ts).astimezone().isoformat())
remaining = exp - now_ts
if remaining >= 0:
    days = remaining // 86400
    hours = (remaining % 86400) // 3600
    minutes = (remaining % 3600) // 60
    seconds = remaining % 60
    print(f"\nRemaining: {remaining} seconds (~{days}d {hours}h {minutes}m {seconds}s) ")
else:
    print(f"\nExpired {abs(remaining)} seconds ago")
