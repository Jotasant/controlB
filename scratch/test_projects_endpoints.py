import json
import urllib.request
import urllib.error
import controlb.main
from controlb.db import get_db
from controlb.modules.identity.models import User
from controlb.modules.identity.security import create_access_token

db = next(get_db())
admin_user = db.query(User).filter(User.is_active == True).first()
token = create_access_token({"sub": str(admin_user.id), "org_id": str(admin_user.organization_id)})
headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

endpoints = [
    ("GET", "http://127.0.0.1:8000/projects/"),
    ("GET", "http://127.0.0.1:8000/projects/types"),
    ("GET", "http://127.0.0.1:8000/projects/order-types"),
    ("GET", "http://127.0.0.1:8000/projects/workflows"),
    ("GET", "http://127.0.0.1:8000/projects/orders"),
    ("GET", "http://127.0.0.1:8000/projects/orders/list"),
    ("GET", "http://127.0.0.1:8000/projects/tasks"),
    ("GET", "http://127.0.0.1:8000/projects/tasks/list"),
    ("GET", "http://127.0.0.1:8000/projects/issues"),
    ("GET", "http://127.0.0.1:8000/projects/issues/list"),
    ("GET", "http://127.0.0.1:8000/projects/checklists"),
]

print("--- TESTANDO ROTAS DO MÓDULO PROJECTS CONTRA O SERVIDOR ATIVO ---")
all_passed = True
for method, url in endpoints:
    req = urllib.request.Request(url, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            data = resp.read().decode('utf-8')
            parsed = json.loads(data)
            count = len(parsed) if isinstance(parsed, list) else len(parsed.get("items", []))
            print(f"✅ {method} {url} -> Status: {resp.status} (itens: {count})")
    except urllib.error.HTTPError as e:
        all_passed = False
        print(f"❌ {method} {url} -> Status: {e.code}")
        print(f"   Detalhe: {e.read().decode('utf-8')}")

if all_passed:
    print("\n🎉 100% DOS ENDPOINTS TESTADOS RESPONDERAM COM STATUS 200 OK! SISTEMA TOTALMENTE ESTÁVEL!")
