import uuid
import urllib.request
import urllib.error
import json
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

def make_request(url, method="GET", data=None):
    body = json.dumps(data).encode('utf-8') if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            content = resp.read().decode('utf-8')
            return resp.status, json.loads(content) if content else {}
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8')

print("--- TESTANDO CRIAÇÃO DE PROJETO COM 'name' E EXCLUSÃO ---")

# 1. Buscar tipos de projeto existentes
s, types = make_request("http://127.0.0.1:8000/projects/types")
assert s == 200 and len(types) > 0, f"Falha ao obter tipos: {types}"
p_type_id = types[0]["id"]
print(f"1. Usando tipo de projeto: {p_type_id}")

# 2. Criar projeto usando payload com 'name' (igual ao frontend envia)
create_payload = {
    "name": f"Projeto Teste Automação {uuid.uuid4().hex[:6]}",
    "project_type_id": p_type_id,
    "priority": "MEDIUM",
    "estimated_budget": 5000,
    "is_billable": True,
    "tags": ["teste", "delete"]
}
s, created_proj = make_request("http://127.0.0.1:8000/projects/", method="POST", data=create_payload)
print(f"2. POST /projects/ com campo 'name' -> Status: {s}")
assert s == 201, f"Erro ao criar projeto: {created_proj}"
proj_id = created_proj["id"]
print(f"   Projeto criado com sucesso! ID: {proj_id}, Número: {created_proj['project_number']}, Título: {created_proj['title']}")

# 3. Testar exclusão unitária do projeto criado
s, del_resp = make_request(f"http://127.0.0.1:8000/projects/{proj_id}", method="DELETE")
print(f"3. DELETE /projects/{proj_id} -> Status: {s}, Resposta: {del_resp}")
assert s == 200, f"Erro ao excluir projeto: {del_resp}"

# 4. Verificar se realmente foi excluído
s, get_resp = make_request(f"http://127.0.0.1:8000/projects/{proj_id}")
print(f"4. GET /projects/{proj_id} pós-delete -> Status: {s} (Esperado: 404)")
assert s == 404, f"Projeto ainda existe: {get_resp}"

print("\n🎉 FLUXO DE CRIAÇÃO (COM 'name') E EXCLUSÃO VALIDADO COM SUCESSO!")
