"""
repository.py - Camada de Acesso a Dados (Data Access Layer)

Responsabilidade única: Executar consultas e operações diretas de banco de dados (SQLAlchemy)
para as entidades do módulo Identity (User, Organization, Role, Permission).
Não contém regras de negócio (as regras ficam na camada 'service').
"""

import uuid
from sqlalchemy import select
from sqlalchemy.orm import Session
from controlb.modules.identity.models import User, Organization, Role, Permission, Team
from controlb.modules.identity.schemas import (
    UserCreate, UserUpdate,
    OrganizationCreate, OrganizationUpdate,
    RoleCreate, RoleUpdate,
    TeamCreate, TeamUpdate
)


# ==============================================================================
# 1. CONSULTAS E OPERAÇÕES DE PERMISSÃO (Permission)
# ==============================================================================

def get_all_permissions(db: Session) -> list[Permission]:
    """Retorna todas as permissões cadastradas no catálogo do sistema."""
    stmt = select(Permission).order_by(Permission.module, Permission.code)
    return db.execute(stmt).scalars().all()


def get_permissions_by_ids(db: Session, permission_ids: list[uuid.UUID]) -> list[Permission]:
    """Busca uma lista de objetos Permission a partir de seus IDs UUID."""
    if not permission_ids:
        return []
    stmt = select(Permission).where(Permission.id.in_(permission_ids))
    return db.execute(stmt).scalars().all()


def get_permission_by_code(db: Session, code: str) -> Permission | None:
    """Busca uma permissão pelo seu código único (ex: 'users:view')."""
    stmt = select(Permission).where(Permission.code == code)
    return db.execute(stmt).scalar_one_or_none()


def create_permission_if_not_exists(db: Session, code: str, name: str, module: str, description: str | None = None) -> Permission:
    """Cria uma permissão padrão caso ela ainda não exista no banco."""
    existing = get_permission_by_code(db, code)
    if not existing:
        perm = Permission(code=code, name=name, module=module, description=description)
        db.add(perm)
        db.commit()
        db.refresh(perm)
        return perm
    return existing


# ==============================================================================
# 2. CONSULTAS E OPERAÇÕES DE USUÁRIO (User)
# ==============================================================================

def get_user_by_email(db: Session, email: str) -> User | None:
    """Busca um usuário pelo seu e-mail único."""
    stmt = select(User).where(User.email == email)
    return db.execute(stmt).scalar_one_or_none()


def get_all_users(db: Session, organization_id: uuid.UUID | None = None) -> list[User]:
    """Retorna a lista de usuários, com filtro opcional por organização."""
    stmt = select(User)
    if organization_id:
        stmt = stmt.where(User.organization_id == organization_id)
    return db.execute(stmt).scalars().all()


def get_user_by_id(db: Session, id: uuid.UUID) -> User | None:
    """Busca um usuário pelo seu identificador UUID."""
    stmt = select(User).where(User.id == id)
    return db.execute(stmt).scalar_one_or_none()


def create_user(db: Session, user_data: UserCreate, hashed_password: str) -> User:
    """Cria e persiste um novo usuário no banco de dados com a senha hasheada."""
    db_user = User(
        organization_id=user_data.organization_id,
        role_id=user_data.role_id,
        email=user_data.email,
        full_name=user_data.full_name,
        hashed_password=hashed_password,
        is_seller=user_data.is_seller if hasattr(user_data, 'is_seller') else False,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def update_user(db: Session, db_user: User, user_data: UserUpdate, hashed_password: str | None = None) -> User:
    """Atualiza os campos do perfil do usuário e desvincula se necessário."""
    if user_data.full_name is not None:
        db_user.full_name = user_data.full_name
    if user_data.email is not None:
        db_user.email = user_data.email
    if user_data.organization_id is not None:
        db_user.organization_id = user_data.organization_id
    if user_data.role_id is not None:
        db_user.role_id = user_data.role_id
    if user_data.is_active is not None:
        db_user.is_active = user_data.is_active
    if getattr(user_data, 'is_seller', None) is not None:
        db_user.is_seller = user_data.is_seller
    if hashed_password:
        db_user.hashed_password = hashed_password

    db.commit()
    db.refresh(db_user)
    return db_user


def delete_user(db: Session, db_user: User) -> None:
    """Remove permanentemente o usuário do banco de dados (exclusão/desvinculação)."""
    db.delete(db_user)
    db.commit()


# ==============================================================================
# 3. CONSULTAS E OPERAÇÕES DE ORGANIZAÇÃO (Organization)
# ==============================================================================

def get_organization_by_name(db: Session, name: str) -> Organization | None:
    """Busca uma organização pelo nome exato."""
    stmt = select(Organization).where(Organization.name == name)
    return db.execute(stmt).scalar_one_or_none()


def get_organization_by_id(db: Session, id: uuid.UUID) -> Organization | None:
    """Busca uma organização pelo seu identificador UUID."""
    stmt = select(Organization).where(Organization.id == id)
    return db.execute(stmt).scalar_one_or_none()


def get_all_organizations(db: Session) -> list[Organization]:
    """Retorna todas as organizações cadastradas no sistema."""
    stmt = select(Organization)
    return db.execute(stmt).scalars().all()


def create_organization(db: Session, organization_data: OrganizationCreate) -> Organization:
    """Cria e salva uma nova organização no banco de dados."""
    db_organization = Organization(
        name=organization_data.name,
    )
    db.add(db_organization)
    db.commit()
    db.refresh(db_organization)
    return db_organization


def update_organization(db: Session, db_org: Organization, org_data: OrganizationUpdate) -> Organization:
    """Atualiza os campos de uma organização existente."""
    if org_data.name is not None:
        db_org.name = org_data.name
    if org_data.is_active is not None:
        db_org.is_active = org_data.is_active
    db.commit()
    db.refresh(db_org)
    return db_org


def delete_organization(db: Session, db_org: Organization) -> None:
    """Exclui a organização do banco de dados e limpa vínculos com segurança via CASCADE."""
    db.delete(db_org)
    db.commit()


def bulk_delete_organizations(db: Session, org_ids: list[uuid.UUID]) -> int:
    """Exclui múltiplas organizações em lote via CASCADE."""
    deleted_count = 0
    for org_id in org_ids:
        org = get_organization_by_id(db, id=org_id)
        if org:
            db.delete(org)
            deleted_count += 1
    db.commit()
    return deleted_count


def bulk_delete_users(db: Session, user_ids: list[uuid.UUID], current_user_id: uuid.UUID) -> int:
    """Exclui múltiplos usuários em lote, ignorando autoexclusão do usuário logado."""
    deleted_count = 0
    for user_id in user_ids:
        if user_id == current_user_id:
            continue
        user = get_user_by_id(db, id=user_id)
        if user:
            db.delete(user)
            deleted_count += 1
    db.commit()
    return deleted_count


def bulk_delete_roles(db: Session, role_ids: list[uuid.UUID]) -> int:
    """Exclui múltiplos cargos em lote."""
    deleted_count = 0
    for role_id in role_ids:
        role = get_role_by_id(db, id=role_id)
        if role:
            for u in list(role.users):
                u.role_id = None
            db.delete(role)
            deleted_count += 1
    db.commit()
    return deleted_count


# ==============================================================================
# 4. CONSULTAS E OPERAÇÕES DE CARGO (Role)
# ==============================================================================

def get_role_by_name(db: Session, name: str) -> Role | None:
    """Busca um cargo pelo seu nome."""
    stmt = select(Role).where(Role.name == name)
    return db.execute(stmt).scalar_one_or_none()


def get_role_by_id(db: Session, id: uuid.UUID) -> Role | None:
    """Busca um cargo pelo seu ID UUID."""
    stmt = select(Role).where(Role.id == id)
    return db.execute(stmt).scalar_one_or_none()


def get_all_roles(db: Session) -> list[Role]:
    """Retorna todos os cargos cadastrados no banco com suas permissões."""
    stmt = select(Role)
    return db.execute(stmt).scalars().all()


def create_role(db: Session, role_data: RoleCreate, permissions: list[Permission] = []) -> Role:
    """Cria e persiste um novo cargo com sua lista de permissões associadas."""
    db_role = Role(
        name=role_data.name,
        description=role_data.description,
        is_active=role_data.is_active,
        organization_id=role_data.organization_id,
        permissions=permissions
    )
    db.add(db_role)
    db.commit()
    db.refresh(db_role)
    return db_role


def update_role(db: Session, db_role: Role, role_data: RoleUpdate, permissions: list[Permission] | None = None) -> Role:
    """Atualiza dados do cargo e sincroniza a lista de permissões associadas."""
    if role_data.name is not None:
        db_role.name = role_data.name
    if role_data.description is not None:
        db_role.description = role_data.description
    if role_data.is_active is not None:
        db_role.is_active = role_data.is_active
    if permissions is not None:
        db_role.permissions = permissions

    db.commit()
    db.refresh(db_role)
    return db_role


def delete_role(db: Session, db_role: Role) -> None:
    """Exclui o cargo do banco de dados."""
    db.delete(db_role)
    db.commit()


# ==============================================================================
# 5. CONSULTAS E OPERAÇÕES DE CONTATO INSTITUCIONAL (Contact)
# ==============================================================================

from controlb.modules.identity.models import Contact
from controlb.modules.identity.schemas import ContactCreate, ContactUpdate


def list_contacts(
    db: Session,
    organization_id: uuid.UUID,
    search: str | None = None,
    is_customer: bool | None = None,
    is_supplier: bool | None = None,
    is_carrier: bool | None = None,
    is_active: bool | None = None,
) -> list[Contact]:
    """Lista os contatos de uma organização com filtros avançados de papéis e busca."""
    stmt = select(Contact).where(Contact.organization_id == organization_id)
    if is_customer is not None:
        stmt = stmt.where(Contact.is_customer == is_customer)
    if is_supplier is not None:
        stmt = stmt.where(Contact.is_supplier == is_supplier)
    if is_carrier is not None:
        stmt = stmt.where(Contact.is_carrier == is_carrier)
    if is_active is not None:
        stmt = stmt.where(Contact.is_active == is_active)
    if search:
        term = f"%{search.strip()}%"
        stmt = stmt.where(
            (Contact.name.ilike(term)) |
            (Contact.trade_name.ilike(term)) |
            (Contact.full_name.ilike(term)) |
            (Contact.email.ilike(term)) |
            (Contact.document.ilike(term)) |
            (Contact.phone.ilike(term)) |
            (Contact.address_city.ilike(term))
        )
    stmt = stmt.order_by(Contact.name)
    return db.execute(stmt).scalars().all()


def get_contact_by_id(db: Session, contact_id: uuid.UUID, organization_id: uuid.UUID) -> Contact | None:
    """Busca um contato por ID dentro de uma organização."""
    stmt = select(Contact).where(
        Contact.id == contact_id,
        Contact.organization_id == organization_id
    )
    return db.execute(stmt).scalar_one_or_none()


def get_contact_by_document(db: Session, document: str, organization_id: uuid.UUID) -> Contact | None:
    """Busca um contato pelo documento (CNPJ/CPF) dentro da organização."""
    stmt = select(Contact).where(
        Contact.document == document.strip(),
        Contact.organization_id == organization_id
    )
    return db.execute(stmt).scalar_one_or_none()


def create_contact(db: Session, organization_id: uuid.UUID, data: ContactCreate) -> Contact:
    """Cria e persiste um novo contato/parceiro unificado."""
    new_id = uuid.uuid4()
    contact = Contact(
        id=new_id,
        organization_id=organization_id,
        person_type=data.person_type or "PJ",
        document=data.document.strip() if data.document else None,
        name=data.name.strip() if data.name else (data.full_name or "").strip(),
        trade_name=data.trade_name.strip() if data.trade_name else None,
        state_registration=data.state_registration.strip() if data.state_registration else None,
        full_name=data.full_name.strip() if data.full_name else None,
        position=data.position.strip() if data.position else None,
        email=data.email.strip() if data.email else None,
        phone=data.phone.strip() if data.phone else None,
        mobile=data.mobile.strip() if data.mobile else None,
        address_street=data.address_street,
        address_number=data.address_number,
        address_neighborhood=data.address_neighborhood,
        address_city=data.address_city,
        address_state=data.address_state,
        address_zip_code=data.address_zip_code,
        is_customer=data.is_customer,
        is_supplier=data.is_supplier,
        is_carrier=data.is_carrier,
        credit_limit=data.credit_limit,
        origin_module=data.origin_module or "IDENTITY",
        is_active=data.is_active,
        notes=data.notes
    )
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return contact


def update_contact(db: Session, contact: Contact, data: ContactUpdate) -> Contact:
    """Atualiza dados cadastrais e perfis de um contato."""
    if data.person_type is not None:
        contact.person_type = data.person_type
    if data.document is not None:
        contact.document = data.document.strip() if data.document else None
    if data.name is not None:
        contact.name = data.name.strip()
    if data.trade_name is not None:
        contact.trade_name = data.trade_name.strip() if data.trade_name else None
    if data.state_registration is not None:
        contact.state_registration = data.state_registration.strip() if data.state_registration else None
    if data.full_name is not None:
        contact.full_name = data.full_name.strip() if data.full_name else None
    if data.position is not None:
        contact.position = data.position.strip() if data.position else None
    if data.email is not None:
        contact.email = data.email.strip() if data.email else None
    if data.phone is not None:
        contact.phone = data.phone.strip() if data.phone else None
    if data.mobile is not None:
        contact.mobile = data.mobile.strip() if data.mobile else None
    if data.address_street is not None:
        contact.address_street = data.address_street
    if data.address_number is not None:
        contact.address_number = data.address_number
    if data.address_neighborhood is not None:
        contact.address_neighborhood = data.address_neighborhood
    if data.address_city is not None:
        contact.address_city = data.address_city
    if data.address_state is not None:
        contact.address_state = data.address_state
    if data.address_zip_code is not None:
        contact.address_zip_code = data.address_zip_code
    if data.is_customer is not None:
        contact.is_customer = data.is_customer
    if data.is_supplier is not None:
        contact.is_supplier = data.is_supplier
    if data.is_carrier is not None:
        contact.is_carrier = data.is_carrier
    if data.credit_limit is not None:
        contact.credit_limit = data.credit_limit
    if data.is_active is not None:
        contact.is_active = data.is_active
    if data.notes is not None:
        contact.notes = data.notes

    db.commit()
    db.refresh(contact)
    return contact


def delete_contact(db: Session, contact: Contact) -> None:
    """Remove um contato do banco."""
    db.delete(contact)
    db.commit()


# ==============================================================================
# 7. CONSULTAS E OPERAÇÕES DE EQUIPE (Team)
# ==============================================================================

def list_teams(
    db: Session,
    organization_id: uuid.UUID,
    module_category: str | None = None,
    is_active: bool | None = None
) -> list[Team]:
    """Retorna as equipes de uma organização, com filtro opcional por módulo."""
    stmt = select(Team).where(Team.organization_id == organization_id)
    if module_category:
        stmt = stmt.where(Team.module_category == module_category.upper())
    if is_active is not None:
        stmt = stmt.where(Team.is_active == is_active)
    stmt = stmt.order_by(Team.name)
    return db.execute(stmt).scalars().all()


def get_team_by_id(db: Session, team_id: uuid.UUID, organization_id: uuid.UUID) -> Team | None:
    """Busca uma equipe pelo ID e organização."""
    stmt = select(Team).where(Team.id == team_id, Team.organization_id == organization_id)
    return db.execute(stmt).scalar_one_or_none()


def create_team(db: Session, organization_id: uuid.UUID, data: TeamCreate) -> Team:
    """Cria e persiste uma nova equipe com seus membros associados."""
    team = Team(
        id=uuid.uuid4(),
        organization_id=organization_id,
        name=data.name.strip(),
        code=data.code.strip() if data.code else None,
        module_category=(data.module_category or "SALES").upper(),
        description=data.description.strip() if data.description else None,
        leader_id=data.leader_id,
        is_active=data.is_active
    )
    if data.member_ids:
        users_stmt = select(User).where(User.id.in_(data.member_ids), User.organization_id == organization_id)
        team.members = list(db.execute(users_stmt).scalars().all())
    
    db.add(team)
    db.commit()
    db.refresh(team)
    return team


def update_team(db: Session, team: Team, data: TeamUpdate) -> Team:
    """Atualiza dados e membros de uma equipe."""
    if data.name is not None:
        team.name = data.name.strip()
    if data.code is not None:
        team.code = data.code.strip() if data.code else None
    if data.module_category is not None:
        team.module_category = data.module_category.upper()
    if data.description is not None:
        team.description = data.description.strip() if data.description else None
    if data.leader_id is not None:
        team.leader_id = data.leader_id
    if data.is_active is not None:
        team.is_active = data.is_active
    if data.member_ids is not None:
        users_stmt = select(User).where(User.id.in_(data.member_ids), User.organization_id == team.organization_id)
        team.members = list(db.execute(users_stmt).scalars().all())

    db.commit()
    db.refresh(team)
    return team


def delete_team(db: Session, team: Team) -> None:
    """Remove uma equipe do banco."""
    db.delete(team)
    db.commit()


def add_team_members(db: Session, team: Team, user_ids: list[uuid.UUID]) -> Team:
    """Adiciona múltiplos membros a uma equipe existente."""
    if user_ids:
        users_stmt = select(User).where(User.id.in_(user_ids), User.organization_id == team.organization_id)
        new_users = db.execute(users_stmt).scalars().all()
        current_ids = {u.id for u in team.members}
        for u in new_users:
            if u.id not in current_ids:
                team.members.append(u)
        db.commit()
        db.refresh(team)
    return team


def remove_team_member(db: Session, team: Team, user_id: uuid.UUID) -> Team:
    """Remove um membro específico de uma equipe."""
    team.members = [u for u in team.members if u.id != user_id]
    db.commit()
    db.refresh(team)
    return team


def get_teams_by_user(db: Session, user_id: uuid.UUID, organization_id: uuid.UUID) -> list[Team]:
    """Retorna todas as equipes às quais um usuário pertence."""
    stmt = select(Team).join(Team.members).where(
        User.id == user_id,
        Team.organization_id == organization_id,
        Team.is_active == True
    )
    return db.execute(stmt).scalars().all()