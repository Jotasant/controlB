"""Execution configuration alongside the existing Project/WorkOrder services.

Functions flush, never commit. The caller owns the atomic business transaction.
"""
import uuid
from copy import deepcopy

from fastapi import HTTPException
from sqlalchemy import func, select

from controlb.modules.projects.engine_schema import TypeConfiguration, empty, validate_fields
from controlb.modules.projects.models import (
    Checklist, ChecklistItem, ChecklistTemplate, ExecutionTypeRevision, Project,
    ProjectMember, ProjectType, WorkflowTemplate, WorkOrder, WorkOrderType,
)


def invalid(message):
    raise HTTPException(status_code=422, detail=message)


def type_model(kind):
    if kind not in ("project", "work_order"):
        invalid("Tipo de entidade inválido.")
    return ProjectType if kind == "project" else WorkOrderType


def scoped_type(db, org_id, kind, type_id, *, lock=False):
    model = type_model(kind)
    statement = select(model).where(model.id == type_id, model.organization_id == org_id)
    if lock:
        statement = statement.with_for_update()
    obj = db.scalar(statement.execution_options(populate_existing=True))
    if not obj:
        raise HTTPException(404, "Tipo não encontrado.")
    return obj


def publish(db, org_id, kind, type_id, user_id):
    obj = scoped_type(db, org_id, kind, type_id, lock=True)
    if not obj.is_active:
        invalid("Ative o Tipo antes de publicar.")
    definition = TypeConfiguration.model_validate(obj.configuration or {})
    workflow_snapshot = {}
    if obj.default_workflow_id:
        workflow = db.scalar(select(WorkflowTemplate).where(
            WorkflowTemplate.id == obj.default_workflow_id, WorkflowTemplate.organization_id == org_id,
        ).with_for_update())
        if not workflow or workflow.target_entity != kind.upper() or not workflow.is_active:
            invalid("Selecione um workflow ativo da mesma organização e entidade.")
        if not workflow.stages or sum(stage.is_initial for stage in workflow.stages) != 1:
            invalid("O workflow deve ter etapas e exatamente uma etapa inicial.")
        ids = {str(stage.id) for stage in workflow.stages}
        if any(set(map(str, stage.allowed_transitions)) - ids for stage in workflow.stages):
            invalid("Há transições apontando para etapas de outro workflow.")
        workflow_snapshot = {"id": str(workflow.id), "name": workflow.name, "stages": [
            {"id": str(s.id), "name": s.name, "position": s.position, "color": s.color,
             "is_initial": s.is_initial, "is_terminal": s.is_terminal,
             "allowed_transitions": list(map(str, s.allowed_transitions))}
            for s in workflow.stages
        ]}
    ids = {stage["id"] for stage in workflow_snapshot.get("stages", [])}
    if any(set(field.required_stages) - ids for field in definition.fields) or any(gate.stage_id not in ids for gate in definition.gates):
        invalid("As obrigatoriedades e portões devem usar etapas do workflow padrão.")
    snapshots = []
    for raw_id in dict.fromkeys(definition.checklist_template_ids):
        try:
            template_id = uuid.UUID(raw_id)
        except ValueError:
            invalid("Modelo de checklist inválido.")
        template = db.scalar(select(ChecklistTemplate).where(ChecklistTemplate.id == template_id, ChecklistTemplate.organization_id == org_id))
        if not template:
            invalid("Modelo de checklist não encontrado nesta organização.")
        snapshots.append({"id": str(template.id), "name": template.name, "items": [
            {"text": item.text, "position": item.position, "is_required": item.is_required} for item in template.items
        ]})
    if any(gate.checklist_required for gate in definition.gates) and not any(s["items"] for s in snapshots):
        invalid("Portão de checklist exige um modelo com itens.")
    version = (db.scalar(select(func.max(ExecutionTypeRevision.version)).where(
        ExecutionTypeRevision.organization_id == org_id, ExecutionTypeRevision.kind == kind,
        ExecutionTypeRevision.type_id == type_id,
    )) or 0) + 1
    revision = ExecutionTypeRevision(organization_id=org_id, kind=kind, type_id=type_id, version=version,
        configuration=definition.model_dump(mode="json"), workflow_snapshot=workflow_snapshot,
        checklist_snapshot=snapshots, published_by_id=user_id)
    db.add(revision)
    db.flush()
    obj.published_revision_id = revision.id
    db.flush()
    return revision


def serialize_revision(revision):
    return None if not revision else {"id": str(revision.id), "version": revision.version,
        "configuration": revision.configuration, "workflow": revision.workflow_snapshot}


def latest(db, org_id, kind, type_id):
    obj = scoped_type(db, org_id, kind, type_id)
    return db.get(ExecutionTypeRevision, obj.published_revision_id) if obj.published_revision_id else None


def validate_references(db, org_id, fields, values):
    from controlb.modules.identity.models import Contact, Team, User
    from controlb.modules.purchasing.models import Supplier
    from controlb.modules.sales.models import SalesCustomer
    models = {"contact": Contact, "customer": SalesCustomer, "team": Team, "user": User, "supplier": Supplier}
    for field in fields:
        value = values.get(field.key)
        if empty(value):
            continue
        if field.type == "table":
            for row in value:
                validate_references(db, org_id, field.columns, row)
        if field.type != "reference":
            continue
        try:
            target_id = uuid.UUID(value)
        except (ValueError, TypeError):
            invalid(f"{field.label}: referência inválida.")
        model = models[field.reference]
        if not db.scalar(select(model.id).where(model.id == target_id, model.organization_id == org_id)):
            invalid(f"{field.label}: registro não encontrado nesta organização.")


def roles_for(db, record, user_id):
    roles = set()
    if user_id in (record.created_by_id, getattr(record, "manager_id", None), getattr(record, "responsible_id", None)):
        roles.add("manager")
    project_id = record.id if isinstance(record, Project) else record.project_id
    if project_id:
        roles.update(db.scalars(select(ProjectMember.role).where(ProjectMember.project_id == project_id, ProjectMember.user_id == user_id)))
    return roles


def validate(db, revision, values, stage_id, *, previous=None, roles=None, creating=False):
    if not revision:
        return values
    definition = TypeConfiguration.model_validate(revision.configuration)
    try:
        result = validate_fields(definition.fields, values, stage_id=stage_id, previous=previous, roles=roles, creating=creating)
    except ValueError as exc:
        invalid(str(exc))
    validate_references(db, revision.organization_id, definition.fields, result)
    for gate in definition.gates:
        if gate.stage_id != str(stage_id):
            continue
        if any(empty(result.get(key)) for key in gate.required_fields):
            labels = [f.label for f in definition.fields if f.key in gate.required_fields and empty(result.get(f.key))]
            invalid("Preencha os campos do portão: " + ", ".join(labels))
        if gate.allowed_roles and not set(gate.allowed_roles) & set(roles or []):
            invalid("Seu papel não permite entrar nesta etapa.")
        if gate.checklist_required and creating:
            invalid("Crie na etapa inicial e conclua o checklist antes desta etapa.")
    return result


def prepare_create(db, org_id, kind, data):
    type_id = data.project_type_id if kind == "project" else data.order_type_id
    if not type_id:
        return None
    revision = latest(db, org_id, kind, type_id)
    if revision:
        workflow_id = revision.workflow_snapshot.get("id")
        if data.workflow_id and str(data.workflow_id) != workflow_id:
            invalid("O Tipo publicado utiliza seu próprio workflow versionado.")
        data.workflow_id = uuid.UUID(workflow_id) if workflow_id else None
        stages = revision.workflow_snapshot.get("stages", [])
        if data.current_stage_id and str(data.current_stage_id) not in {s["id"] for s in stages}:
            invalid("Etapa não pertence à versão publicada.")
        if not data.current_stage_id:
            initial = next((s for s in stages if s["is_initial"]), None)
            data.current_stage_id = uuid.UUID(initial["id"]) if initial else None
        data.custom_fields = validate(db, revision, data.custom_fields, data.current_stage_id, creating=True, roles={"manager"})
    return revision


def validate_update(db, record, changes, user_id, *, stage_id=None, status=None):
    revision = record.type_revision
    if not revision:
        return
    type_key = "project_type_id" if isinstance(record, Project) else "order_type_id"
    if type_key in changes and changes[type_key] != getattr(record, type_key):
        invalid("Troca de Tipo requer migração explícita; a versão deste registro está preservada.")
    if "workflow_id" in changes and changes["workflow_id"] != record.workflow_id:
        invalid("O workflow deste registro está fixado pela versão do Tipo.")
    target = stage_id if stage_id is not None else changes.get("current_stage_id", record.current_stage_id)
    stages = {s["id"]: s for s in revision.workflow_snapshot.get("stages", [])}
    if stages and str(target) not in stages:
        invalid("Selecione uma etapa da versão publicada.")
    old = stages.get(str(record.current_stage_id))
    if target != record.current_stage_id and old and old["allowed_transitions"] and str(target) not in old["allowed_transitions"]:
        invalid("Transição não permitida pela versão do Tipo.")
    if status in ("completed", "cancelled") and stages and not stages.get(str(target), {}).get("is_terminal"):
        invalid("Entre em uma etapa terminal antes de encerrar o registro.")
    values = validate(db, revision, changes.get("custom_fields", record.custom_fields) or {}, target,
        previous=record.custom_fields, roles=roles_for(db, record, user_id))
    if "custom_fields" in changes:
        changes["custom_fields"] = values
    gate = next((g for g in revision.configuration["gates"] if g["stage_id"] == str(target)), None)
    if gate and gate["checklist_required"]:
        link = Checklist.project_id == record.id if isinstance(record, Project) else Checklist.work_order_id == record.id
        checklists = db.scalars(select(Checklist).where(link, Checklist.organization_id == record.organization_id, Checklist.engine_key.is_not(None))).all()
        if not checklists or any(not item.is_checked for c in checklists for item in c.items):
            invalid("Conclua os checklists do Tipo antes de entrar nesta etapa.")


def instantiate_checklists(db, record, revision):
    if not revision:
        return
    for snapshot in revision.checklist_snapshot:
        link = {"project_id" if isinstance(record, Project) else "work_order_id": record.id}
        key = f"{revision.id}:{snapshot['id']}"
        existing = db.scalar(select(Checklist.id).filter_by(**link, engine_key=key))
        if existing:
            continue
        checklist = Checklist(organization_id=record.organization_id, name=snapshot["name"],
            engine_key=key, total_items=len(snapshot["items"]), **link)
        db.add(checklist)
        db.flush()
        for item in snapshot["items"]:
            db.add(ChecklistItem(checklist_id=checklist.id, **deepcopy(item)))
    db.flush()


def protect_workflow_deletion(db, workflow_id):
    # Deletion would invalidate stage FKs held by published revisions, even with no records yet.
    revisions = db.scalars(select(ExecutionTypeRevision).join(WorkflowTemplate,
        WorkflowTemplate.organization_id == ExecutionTypeRevision.organization_id).where(WorkflowTemplate.id == workflow_id))
    if any(r.workflow_snapshot.get("id") == str(workflow_id) for r in revisions):
        invalid("Workflow publicado: desative-o; não exclua suas etapas históricas.")


def reorder_stages(db, org_id, workflow_id, ids):
    workflow = db.scalar(select(WorkflowTemplate).where(WorkflowTemplate.id == workflow_id, WorkflowTemplate.organization_id == org_id).with_for_update())
    if not workflow:
        raise HTTPException(404, "Workflow não encontrado.")
    if len(set(ids)) != len(ids) or set(ids) != {s.id for s in workflow.stages}:
        invalid("Informe todas as etapas, sem repetições.")
    stages = {s.id: s for s in workflow.stages}
    offset = max((s.position for s in stages.values()), default=0) + len(ids) + 1
    for index, stage_id in enumerate(ids):
        stages[stage_id].position = offset + index
    db.flush()
    for index, stage_id in enumerate(ids):
        stages[stage_id].position = index
    db.flush()
    return workflow
