import uuid
from decimal import Decimal
from types import SimpleNamespace

import pytest

from controlb.modules.projects import schemas, service


def test_work_order_project_is_optional_and_type_alias_is_accepted():
    order_type_id = uuid.uuid4()

    payload = schemas.WorkOrderCreate.model_validate(
        {
            "title": "Ordem avulsa",
            "project_id": "",
            "work_order_type_id": str(order_type_id),
        }
    )

    assert payload.project_id is None
    assert payload.order_type_id == order_type_id


def test_task_accepts_work_order_without_direct_project_and_maps_assignees():
    work_order_id = uuid.uuid4()
    user_id = uuid.uuid4()

    payload = schemas.TaskCreate.model_validate(
        {
            "title": "Executar inspeção",
            "project_id": "",
            "work_order_id": str(work_order_id),
            "assigned_user_ids": [str(user_id)],
        }
    )

    assert payload.project_id is None
    assert payload.work_order_id == work_order_id
    assert payload.assignee_ids == [user_id]


def test_task_update_keeps_explicit_empty_assignee_list():
    payload = schemas.TaskUpdate.model_validate({"assigned_user_ids": []})

    assert payload.model_dump(exclude_unset=True)["assignee_ids"] == []


def test_project_and_issue_form_fields_are_part_of_the_api_contract():
    project = schemas.ProjectCreate.model_validate(
        {"name": "Projeto piloto", "notes": "Acesso restrito", "is_billable": False}
    )
    issue = schemas.IssueCreate.model_validate(
        {
            "title": "Atraso de material",
            "description": "Entrega não realizada",
            "impact_cost": "1250.50",
            "impact_days": 3,
        }
    )

    assert project.title == "Projeto piloto"
    assert project.notes == "Acesso restrito"
    assert project.is_billable is False
    assert issue.impact_cost == Decimal("1250.50")
    assert issue.impact_days == 3


def test_issue_update_can_clear_links_and_accept_legacy_resolution_name():
    payload = schemas.IssueUpdate.model_validate(
        {
            "project_id": "",
            "work_order_id": "",
            "task_id": "",
            "assigned_to_id": "",
            "resolution_notes": "Material substituído",
        }
    )

    values = payload.model_dump(exclude_unset=True)
    assert values["project_id"] is None
    assert values["work_order_id"] is None
    assert values["task_id"] is None
    assert values["assigned_to_id"] is None
    assert values["resolution"] == "Material substituído"


def test_task_service_requires_one_operational_link():
    payload = schemas.TaskCreate(title="Tarefa sem vínculo")

    with pytest.raises(ValueError, match="projeto ou ordem de trabalho"):
        service.create_task(
            object(),
            org_id=uuid.uuid4(),
            data=payload,
            current_user=SimpleNamespace(id=uuid.uuid4()),
        )


def test_task_service_rejects_assignee_from_another_organization():
    class EmptyScalarResult:
        @staticmethod
        def all():
            return []

    class FakeSession:
        @staticmethod
        def scalars(_statement):
            return EmptyScalarResult()

    payload = schemas.TaskCreate(
        title="Tarefa atribuída",
        project_id=uuid.uuid4(),
        assignee_ids=[uuid.uuid4()],
    )

    with pytest.raises(ValueError, match="não pertencem à organização"):
        service.create_task(
            FakeSession(),
            org_id=uuid.uuid4(),
            data=payload,
            current_user=SimpleNamespace(id=uuid.uuid4()),
        )


@pytest.mark.parametrize(
    ("getter", "message"),
    [
        (service.get_project_type, "Tipo de projeto não encontrado"),
        (service.get_work_order_type, "Tipo de OS não encontrado"),
    ],
)
def test_configuration_getters_report_missing_record(monkeypatch, getter, message):
    repository_getter = "get_project_type" if getter is service.get_project_type else "get_work_order_type"
    monkeypatch.setattr(service.repo, repository_getter, lambda *_args, **_kwargs: None)

    with pytest.raises(ValueError, match=message):
        getter(object(), org_id=uuid.uuid4(), type_id=uuid.uuid4())


def test_workflow_stage_cannot_be_changed_through_another_organization(monkeypatch):
    stage = SimpleNamespace(id=uuid.uuid4(), workflow_id=uuid.uuid4())
    monkeypatch.setattr(service.repo, "get_workflow_stage", lambda *_args, **_kwargs: stage)
    monkeypatch.setattr(service.repo, "get_workflow", lambda *_args, **_kwargs: None)

    with pytest.raises(ValueError, match="Etapa não encontrada"):
        service.update_workflow_stage(
            object(),
            org_id=uuid.uuid4(),
            stage_id=stage.id,
            data=schemas.WorkflowStageUpdate(name="Etapa indevida"),
        )
