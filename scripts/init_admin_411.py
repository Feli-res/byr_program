"""Write the isolated stack's admin init payload without printing credentials."""
import json
from pathlib import Path

ENV = Path("/home/sunxiang/youzhihui/acceptance411/test.env")
values = dict(line.split("=", 1) for line in ENV.read_text(encoding="utf-8").splitlines() if "=" in line)
payload = {
    "account": values["LOAD411_ADMIN"],
    "nickname": "压测管理员",
    "password": values["LOAD411_PASSWORD"],
}
Path("/tmp/admin411.json").write_text(json.dumps(payload), encoding="utf-8")
print("ADMIN_JSON_OK")
