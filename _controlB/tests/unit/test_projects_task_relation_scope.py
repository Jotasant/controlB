"""Regressões do acompanhamento de tarefas dentro de projetos e ordens."""

import uuid

from controlb.modules.projects import repository


class _EmptyResult:
    def scalar(self):
        return 0

    def scalars(self):
        return self

    def all(self):
        return []


class _CapturingSession:
    def __init__(self):
        self.statements = []

    def execute(self, statement):
        self.statements.append(statement)
        return _EmptyResult()


def test_project_task_list_includes_tasks_from_its_work_orders():
    session = _CapturingSession()

    repository.list_tasks(
        session,
        org_id=uuid.uuid4(),
        project_id=uuid.uuid4(),
    )

    query = str(session.statements[0])
    assert "task.project_id" in query
    assert "task.work_order_id IN" in query
    assert "work_order.project_id" in query
    assert " OR " in query


def test_project_task_count_uses_the_same_aggregate_scope():
    session = _CapturingSession()

    repository.count_tasks(
        session,
        org_id=uuid.uuid4(),
        project_id=uuid.uuid4(),
    )

    query = str(session.statements[0])
    assert "task.project_id" in query
    assert "task.work_order_id IN" in query
    assert "work_order.organization_id" in query
