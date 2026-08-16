/**
 * pages/Cadastros/Cadastros.tsx - Central de Cadastros, Catálogo e Perfis de Acesso (RBAC)
 * 
 * Permite gerenciar de forma integrada:
 * 1. 🏢 Organizações (Empresas e Filiais)
 * 2. 👥 Usuários (Perfis, Permissões, Status e Desvinculação)
 * 3. 🛡️ Cargos (Matriz de Permissões de Acesso)
 * 4. 🚚 Fornecedores (Razão Social, CNPJ/CPF, Contatos)
 * 5. 📦 Produtos & Insumos (SKU, Unidade de Medida, Preço Base)
 * 6. 🎯 Centros de Custo (Código Contábil, Unidades Orçamentárias)
 */

import React, { useEffect, useState } from 'react';
import { 
  Building2, Users, Shield, Package, Truck, Target, ChevronRight, 
  Search, CheckCircle2, XCircle, RefreshCw, Plus, Mail, Phone,
  Loader2, AlertCircle, Trash2, Edit3, ShieldAlert, CheckSquare, Square
} from 'lucide-react';
import { identityService, purchasingService, authService } from '@/services/api';
import { User, Role, Organization, Permission, Supplier, Product, ProductCategory, CostCenter } from '@/types';
import { Navbar } from '@/components/Navbar';
import { Modal } from '@/components/Modal/Modal';
import { usePermissions } from '@/hooks/usePermissions';
import './Cadastros.scss';

type MenuOption = 'organizacoes' | 'usuarios' | 'cargos' | 'fornecedores' | 'produtos' | 'centros-custo';

export const Cadastros: React.FC = () => {
  const { hasPermission } = usePermissions();

  const [activeMenu, setActiveMenu] = useState<MenuOption>('fornecedores');
  const [searchTerm, setSearchTerm] = useState('');

  // Estados dos Dados carregados da API
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [permissions, setPermissions] = useState<Permission[]>([]);
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [categories, setCategories] = useState<ProductCategory[]>([]);
  const [costCenters, setCostCenters] = useState<CostCenter[]>([]);

  // Estados de Carregamento
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // =========================================================================
  // ESTADOS DO MODAL DE CRIAÇÃO (WIZARD)
  // =========================================================================
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [modalError, setModalError] = useState<string | null>(null);

  // Campos de Criação
  const [userFullName, setUserFullName] = useState('');
  const [userEmail, setUserEmail] = useState('');
  const [userPassword, setUserPassword] = useState('');
  const [userOrgId, setUserOrgId] = useState('');
  const [userRoleId, setUserRoleId] = useState('');
  const [orgName, setOrgName] = useState('');
  const [roleName, setRoleName] = useState('');
  const [roleDescription, setRoleDescription] = useState('');
  const [selectedPermissionIds, setSelectedPermissionIds] = useState<string[]>([]);

  // Campos de Fornecedor
  const [supplierName, setSupplierName] = useState('');
  const [supplierTradeName, setSupplierTradeName] = useState('');
  const [supplierCnpj, setSupplierCnpj] = useState('');
  const [supplierEmail, setSupplierEmail] = useState('');
  const [supplierPhone, setSupplierPhone] = useState('');
  const [supplierCity, setSupplierCity] = useState('');
  const [supplierState, setSupplierState] = useState('');

  // Campos de Produto
  const [productSku, setProductSku] = useState('');
  const [productName, setProductName] = useState('');
  const [productDesc, setProductDesc] = useState('');
  const [productUnit, setProductUnit] = useState('UN');
  const [productPrice, setProductPrice] = useState('0.00');
  const [productCategoryId, setProductCategoryId] = useState('');

  // Campos de Centro de Custo
  const [costCenterCode, setCostCenterCode] = useState('');
  const [costCenterName, setCostCenterName] = useState('');
  const [costCenterDesc, setCostCenterDesc] = useState('');

  // =========================================================================
  // ESTADOS DO MODAL DE PERFIL / EDIÇÃO DE USUÁRIO
  // =========================================================================
  const [selectedUser, setSelectedUser] = useState<User | null>(null);
  const [isProfileModalOpen, setIsProfileModalOpen] = useState(false);
  const [editFullName, setEditFullName] = useState('');
  const [editEmail, setEditEmail] = useState('');
  const [editOrgId, setEditOrgId] = useState('');
  const [editRoleId, setEditRoleId] = useState('');
  const [editIsActive, setEditIsActive] = useState(true);
  const [editNewPassword, setEditNewPassword] = useState('');

  // =========================================================================
  // ESTADOS DO MODAL DE EDIÇÃO DE CARGO & MATRIZ DE PERMISSÕES
  // =========================================================================
  const [selectedRole, setSelectedRole] = useState<Role | null>(null);
  const [isRoleModalOpen, setIsRoleModalOpen] = useState(false);
  const [editRoleName, setEditRoleName] = useState('');
  const [editRoleDescription, setEditRoleDescription] = useState('');
  const [editRolePermissionIds, setEditRolePermissionIds] = useState<string[]>([]);

  // Estado do Modal de Confirmação de Exclusão
  const [itemToDelete, setItemToDelete] = useState<{ id: string; name: string; type: 'user' | 'org' | 'role' | 'supplier' } | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const currentUserEmail = authService.getUserEmail();

  // 1. Busca todos os dados da API em paralelo com tratamento de erros
  const loadData = async () => {
    setLoading(true);
    setError(null);

    try {
      const [
        orgsData, usersData, rolesData, permsData, 
        suppsData, prodsData, catsData, ccsData
      ] = await Promise.all([
        identityService.getOrganizations().catch(() => []),
        identityService.getUsers().catch(() => []),
        identityService.getRoles().catch(() => []),
        identityService.getPermissions().catch(() => []),
        purchasingService.getSuppliers().catch(() => []),
        purchasingService.getProducts().catch(() => []),
        purchasingService.getCategories().catch(() => []),
        purchasingService.getCostCenters().catch(() => []),
      ]);

      setOrganizations(orgsData);
      setUsers(usersData);
      setRoles(rolesData);
      setPermissions(permsData);
      setSuppliers(suppsData);
      setProducts(prodsData);
      setCategories(catsData);
      setCostCenters(ccsData);
    } catch (err: any) {
      console.error('Erro ao carregar dados de cadastros:', err);
      setError('Não foi possível se comunicar com o backend.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleSelectMenu = (menu: MenuOption) => {
    setActiveMenu(menu);
    setSearchTerm('');
  };

  // Abre modal de criação e limpa os campos
  const handleOpenCreateModal = () => {
    setModalError(null);
    setUserFullName('');
    setUserEmail('');
    setUserPassword('');
    setUserOrgId(organizations[0]?.id || '');
    setUserRoleId(roles[0]?.id || '');
    setOrgName('');
    setRoleName('');
    setRoleDescription('');
    setSelectedPermissionIds([]);
    
    // Reset fornecedor
    setSupplierName('');
    setSupplierTradeName('');
    setSupplierCnpj('');
    setSupplierEmail('');
    setSupplierPhone('');
    setSupplierCity('');
    setSupplierState('');

    // Reset produto
    setProductSku(`PRD-${Math.floor(1000 + Math.random() * 9000)}`);
    setProductName('');
    setProductDesc('');
    setProductUnit('UN');
    setProductPrice('0.00');
    setProductCategoryId(categories[0]?.id || '');

    // Reset centro de custo
    setCostCenterCode(`CC-${Math.floor(100 + Math.random() * 900)}`);
    setCostCenterName('');
    setCostCenterDesc('');

    setIsModalOpen(true);
  };

  // Abre o modal de Perfil do Usuário
  const handleOpenUserProfile = (user: User) => {
    setSelectedUser(user);
    setEditFullName(user.full_name);
    setEditEmail(user.email);
    setEditOrgId(user.organization_id || '');
    setEditRoleId(user.role_id || '');
    setEditIsActive(user.is_active);
    setEditNewPassword('');
    setModalError(null);
    setIsProfileModalOpen(true);
  };

  // Abre o modal de Edição de Cargo com Matriz de Permissões
  const handleOpenRoleEdit = (role: Role) => {
    setSelectedRole(role);
    setEditRoleName(role.name);
    setEditRoleDescription(role.description || '');
    setEditRolePermissionIds(role.permissions?.map(p => p.id) || []);
    setModalError(null);
    setIsRoleModalOpen(true);
  };

  const togglePermission = (permId: string, currentList: string[], setList: React.Dispatch<React.SetStateAction<string[]>>) => {
    if (currentList.includes(permId)) {
      setList(currentList.filter(id => id !== permId));
    } else {
      setList([...currentList, permId]);
    }
  };

  // 2. Submissão de Criação de Registro
  const handleCreateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isSaving) return;

    setIsSaving(true);
    setModalError(null);

    try {
      if (activeMenu === 'organizacoes') {
        if (!orgName.trim()) throw new Error('O nome da organização é obrigatório.');
        await identityService.createOrganization(orgName.trim());
      } 
      else if (activeMenu === 'usuarios') {
        if (!userFullName.trim() || !userEmail.trim() || !userPassword) {
          throw new Error('Preencha todos os campos obrigatórios do usuário.');
        }
        await identityService.createUser({
          full_name: userFullName.trim(),
          email: userEmail.trim(),
          password: userPassword,
          organization_id: userOrgId || undefined,
          role_id: userRoleId || undefined,
        });
      } 
      else if (activeMenu === 'cargos') {
        if (!roleName.trim()) throw new Error('O nome do cargo é obrigatório.');
        await identityService.createRole(
          roleName.trim(),
          roleDescription.trim(),
          organizations[0]?.id || '00000000-0000-0000-0000-000000000000',
          selectedPermissionIds
        );
      }
      else if (activeMenu === 'fornecedores') {
        if (!supplierName.trim() || !supplierCnpj.trim()) {
          throw new Error('Razão Social e CNPJ/CPF são campos obrigatórios.');
        }
        await purchasingService.createSupplier({
          name: supplierName.trim(),
          trade_name: supplierTradeName.trim() || undefined,
          cnpj_cpf: supplierCnpj.trim(),
          email: supplierEmail.trim() || undefined,
          phone: supplierPhone.trim() || undefined,
          city: supplierCity.trim() || undefined,
          state: supplierState.trim() || undefined,
        });
      }
      else if (activeMenu === 'produtos') {
        if (!productSku.trim() || !productName.trim()) {
          throw new Error('SKU e Nome do Produto são obrigatórios.');
        }
        await purchasingService.createProduct({
          sku: productSku.trim(),
          name: productName.trim(),
          description: productDesc.trim() || undefined,
          unit_of_measure: productUnit,
          reference_price: parseFloat(productPrice) || 0,
          category_id: productCategoryId || undefined,
        });
      }
      else if (activeMenu === 'centros-custo') {
        if (!costCenterCode.trim() || !costCenterName.trim()) {
          throw new Error('Código e Nome do Centro de Custo são obrigatórios.');
        }
        await purchasingService.createCostCenter({
          code: costCenterCode.trim(),
          name: costCenterName.trim(),
          description: costCenterDesc.trim() || undefined,
        });
      }

      setIsModalOpen(false);
      await loadData();
    } catch (err: any) {
      setModalError(
        err.response?.data?.detail || err.message || 'Erro ao salvar o registro no servidor.'
      );
    } finally {
      setIsSaving(false);
    }
  };

  // 3. Salvar Edição de Perfil do Usuário
  const handleSaveUserProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedUser || isSaving) return;

    setIsSaving(true);
    setModalError(null);

    try {
      await identityService.updateUser(selectedUser.id, {
        full_name: editFullName.trim(),
        email: editEmail.trim(),
        organization_id: editOrgId || undefined,
        role_id: editRoleId || undefined,
        is_active: editIsActive,
        password: editNewPassword.trim() ? editNewPassword : undefined,
      });

      setIsProfileModalOpen(false);
      await loadData();
    } catch (err: any) {
      setModalError(
        err.response?.data?.detail || err.message || 'Erro ao atualizar o perfil do usuário.'
      );
    } finally {
      setIsSaving(false);
    }
  };

  // 4. Salvar Edição de Cargo & Permissões
  const handleSaveRole = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedRole || isSaving) return;

    setIsSaving(true);
    setModalError(null);

    try {
      await identityService.updateRole(selectedRole.id, {
        name: editRoleName.trim(),
        description: editRoleDescription.trim(),
        permission_ids: editRolePermissionIds
      });

      setIsRoleModalOpen(false);
      await loadData();
    } catch (err: any) {
      setModalError(
        err.response?.data?.detail || err.message || 'Erro ao atualizar o cargo e permissões.'
      );
    } finally {
      setIsSaving(false);
    }
  };

  // 5. Executar Exclusão Confirmada
  const handleConfirmDelete = async () => {
    if (!itemToDelete || isDeleting) return;

    setIsDeleting(true);
    try {
      if (itemToDelete.type === 'user') {
        await identityService.deleteUser(itemToDelete.id);
        if (selectedUser?.id === itemToDelete.id) {
          setIsProfileModalOpen(false);
        }
      } else if (itemToDelete.type === 'org') {
        await identityService.deleteOrganization(itemToDelete.id);
      } else if (itemToDelete.type === 'role') {
        await identityService.deleteRole(itemToDelete.id);
      } else if (itemToDelete.type === 'supplier') {
        await purchasingService.deleteSupplier(itemToDelete.id);
      }

      setItemToDelete(null);
      await loadData();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Erro ao excluir o registro.');
    } finally {
      setIsDeleting(false);
    }
  };

  // Agrupamento de permissões por Módulo
  const permissionsByModule = permissions.reduce((acc, perm) => {
    if (!acc[perm.module]) acc[perm.module] = [];
    acc[perm.module].push(perm);
    return acc;
  }, {} as Record<string, Permission[]>);

  // Filtros de busca
  const filteredOrgs = organizations.filter(o =>
    o.name.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const filteredUsers = users.filter(u =>
    u.full_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    u.email.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const filteredRoles = roles.filter(r =>
    r.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    (r.description && r.description.toLowerCase().includes(searchTerm.toLowerCase()))
  );

  const filteredSuppliers = suppliers.filter(s =>
    s.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    (s.trade_name && s.trade_name.toLowerCase().includes(searchTerm.toLowerCase())) ||
    s.cnpj_cpf.includes(searchTerm)
  );

  const filteredProducts = products.filter(p =>
    p.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    p.sku.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const filteredCostCenters = costCenters.filter(c =>
    c.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    c.code.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="cadastros-page">
      <Navbar />

      <div className="cadastros-layout">
        
        {/* ========================================================= */}
        {/* 1. BARRA LATERAL ESQUERDA (Sidebar Protegida por RBAC)    */}
        {/* ========================================================= */}
        <aside className="sidebar-left">
          <div className="sidebar-header">
            <span className="sidebar-section-title">Menu de Cadastros</span>
          </div>

          <nav className="sidebar-menu-list">
            
            {/* 1. Fornecedores */}
            <button
              type="button"
              className={`sidebar-menu-btn ${activeMenu === 'fornecedores' ? 'active' : ''}`}
              onClick={() => handleSelectMenu('fornecedores')}
            >
              <div className="btn-label">
                <Truck size={16} className="icon-supplier" />
                <span>Fornecedores</span>
              </div>
              <div className="btn-end">
                <span className="count-pill">{suppliers.length}</span>
                <ChevronRight size={14} className="arrow" />
              </div>
            </button>

            {/* 2. Produtos & Insumos */}
            <button
              type="button"
              className={`sidebar-menu-btn ${activeMenu === 'produtos' ? 'active' : ''}`}
              onClick={() => handleSelectMenu('produtos')}
            >
              <div className="btn-label">
                <Package size={16} className="icon-products" />
                <span>Produtos & Insumos</span>
              </div>
              <div className="btn-end">
                <span className="count-pill">{products.length}</span>
                <ChevronRight size={14} className="arrow" />
              </div>
            </button>

            {/* 3. Centros de Custo */}
            <button
              type="button"
              className={`sidebar-menu-btn ${activeMenu === 'centros-custo' ? 'active' : ''}`}
              onClick={() => handleSelectMenu('centros-custo')}
            >
              <div className="btn-label">
                <Target size={16} className="icon-cc" />
                <span>Centros de Custo</span>
              </div>
              <div className="btn-end">
                <span className="count-pill">{costCenters.length}</span>
                <ChevronRight size={14} className="arrow" />
              </div>
            </button>

            {/* 4. Organizações */}
            {hasPermission('organizations:view') && (
              <button
                type="button"
                className={`sidebar-menu-btn ${activeMenu === 'organizacoes' ? 'active' : ''}`}
                onClick={() => handleSelectMenu('organizacoes')}
              >
                <div className="btn-label">
                  <Building2 size={16} className="icon-org" />
                  <span>Organizações</span>
                </div>
                <div className="btn-end">
                  <span className="count-pill">{organizations.length}</span>
                  <ChevronRight size={14} className="arrow" />
                </div>
              </button>
            )}

            {/* 5. Usuários */}
            {hasPermission('users:view') && (
              <button
                type="button"
                className={`sidebar-menu-btn ${activeMenu === 'usuarios' ? 'active' : ''}`}
                onClick={() => handleSelectMenu('usuarios')}
              >
                <div className="btn-label">
                  <Users size={16} className="icon-users" />
                  <span>Usuários</span>
                </div>
                <div className="btn-end">
                  <span className="count-pill">{users.length}</span>
                  <ChevronRight size={14} className="arrow" />
                </div>
              </button>
            )}

            {/* 6. Cargos e Permissões */}
            {hasPermission('roles:view') && (
              <button
                type="button"
                className={`sidebar-menu-btn ${activeMenu === 'cargos' ? 'active' : ''}`}
                onClick={() => handleSelectMenu('cargos')}
              >
                <div className="btn-label">
                  <Shield size={16} className="icon-roles" />
                  <span>Cargos e Permissões</span>
                </div>
                <div className="btn-end">
                  <span className="count-pill">{roles.length}</span>
                  <ChevronRight size={14} className="arrow" />
                </div>
              </button>
            )}

          </nav>
        </aside>

        {/* ========================================================= */}
        {/* 2. ÁREA DE CONTEÚDO PRINCIPAL                             */}
        {/* ========================================================= */}
        <main className="content-right">
          
          <header className="content-header">
            <div className="titles">
              <h1>
                {activeMenu === 'fornecedores' && 'Gestão de Fornecedores'}
                {activeMenu === 'produtos' && 'Catálogo de Produtos & Insumos'}
                {activeMenu === 'centros-custo' && 'Centros de Custo'}
                {activeMenu === 'organizacoes' && 'Gestão de Organizações'}
                {activeMenu === 'usuarios' && 'Gestão de Usuários & Perfis'}
                {activeMenu === 'cargos' && 'Cargos e Matriz de Permissões'}
              </h1>
              <p>
                {activeMenu === 'fornecedores' && 'Empresas parceiras, dados fiscais e contatos de suprimentos'}
                {activeMenu === 'produtos' && 'Itens cadastrados com SKU, unidade de medida e preço de referência'}
                {activeMenu === 'centros-custo' && 'Unidades orçamentárias e alocações de compras'}
                {activeMenu === 'organizacoes' && 'Empresas, filiais e unidades de negócio cadastradas'}
                {activeMenu === 'usuarios' && 'Gerencie perfis, permissões, vinculação de organizações e desvinculação'}
                {activeMenu === 'cargos' && 'Configure os níveis de acesso e matriz de permissões granulares por cargo'}
              </p>
            </div>

            <div className="header-actions">
              <button className="btn-refresh" onClick={loadData} disabled={loading} title="Atualizar Dados">
                <RefreshCw size={13} className={loading ? 'spin' : ''} />
                <span>Atualizar</span>
              </button>

              <button className="btn-primary" onClick={handleOpenCreateModal}>
                <Plus size={14} />
                <span>
                  {activeMenu === 'fornecedores' && 'Novo Fornecedor'}
                  {activeMenu === 'produtos' && 'Novo Produto'}
                  {activeMenu === 'centros-custo' && 'Novo Centro de Custo'}
                  {activeMenu === 'organizacoes' && 'Nova Organização'}
                  {activeMenu === 'usuarios' && 'Novo Usuário'}
                  {activeMenu === 'cargos' && 'Novo Cargo'}
                </span>
              </button>
            </div>
          </header>

          {error && <div className="alert-error">{error}</div>}

          {/* Painel com Toolbar de Busca */}
          <div className="table-card">
            <div className="table-toolbar">
              <div className="search-wrap">
                <Search size={14} />
                <input
                  type="text"
                  placeholder={
                    activeMenu === 'fornecedores' ? 'Buscar fornecedor por nome ou CNPJ...' :
                    activeMenu === 'produtos' ? 'Buscar produto por nome ou SKU...' :
                    activeMenu === 'centros-custo' ? 'Buscar por nome ou código...' :
                    activeMenu === 'organizacoes' ? 'Buscar organização...' :
                    activeMenu === 'usuarios' ? 'Buscar usuário...' :
                    'Buscar cargo...'
                  }
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                />
              </div>

              <span className="results-count">
                {activeMenu === 'fornecedores' && `${filteredSuppliers.length} fornecedor(es)`}
                {activeMenu === 'produtos' && `${filteredProducts.length} produto(s)`}
                {activeMenu === 'centros-custo' && `${filteredCostCenters.length} centro(s) de custo`}
                {activeMenu === 'organizacoes' && `${filteredOrgs.length} organização(ões)`}
                {activeMenu === 'usuarios' && `${filteredUsers.length} usuário(s)`}
                {activeMenu === 'cargos' && `${filteredRoles.length} cargo(s)`}
              </span>
            </div>

            {/* TABELA: FORNECEDORES */}
            {activeMenu === 'fornecedores' && (
              loading ? (
                <div className="state-empty">Carregando fornecedores...</div>
              ) : filteredSuppliers.length === 0 ? (
                <div className="state-empty">Nenhum fornecedor encontrado.</div>
              ) : (
                <div className="table-responsive">
                  <table className="enterprise-table">
                    <thead>
                      <tr>
                        <th>Fornecedor</th>
                        <th>CNPJ / CPF</th>
                        <th>Contato</th>
                        <th>Status</th>
                        <th style={{ textAlign: 'right' }}>Ações</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredSuppliers.map(supp => (
                        <tr key={supp.id}>
                          <td>
                            <div className="cell-with-icon">
                              <div className="icon-badge orange-bg">
                                <Truck size={14} />
                              </div>
                              <div>
                                <strong>{supp.name}</strong>
                                {supp.trade_name && <span className="sub-label">{supp.trade_name}</span>}
                              </div>
                            </div>
                          </td>
                          <td>
                            <span className="code-tag">{supp.cnpj_cpf}</span>
                          </td>
                          <td>
                            <div className="contact-info">
                              {supp.email && <span className="contact-item"><Mail size={11} /> {supp.email}</span>}
                              {supp.phone && <span className="contact-item"><Phone size={11} /> {supp.phone}</span>}
                              {!supp.email && !supp.phone && <span className="text-muted">Não informado</span>}
                            </div>
                          </td>
                          <td>
                            <span className={`badge-pill ${supp.is_active ? 'active' : 'inactive'}`}>
                              {supp.is_active ? <CheckCircle2 size={11} /> : <XCircle size={11} />}
                              {supp.is_active ? 'Ativo' : 'Inativo'}
                            </span>
                          </td>
                          <td style={{ textAlign: 'right' }}>
                            <button
                              className="btn-action-icon delete"
                              onClick={() => setItemToDelete({ id: supp.id, name: supp.name, type: 'supplier' })}
                              title="Excluir Fornecedor"
                            >
                              <Trash2 size={14} />
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )
            )}

            {/* TABELA: PRODUTOS & INSUMOS */}
            {activeMenu === 'produtos' && (
              loading ? (
                <div className="state-empty">Carregando catálogo de produtos...</div>
              ) : filteredProducts.length === 0 ? (
                <div className="state-empty">Nenhum produto cadastrado no catálogo.</div>
              ) : (
                <div className="table-responsive">
                  <table className="enterprise-table">
                    <thead>
                      <tr>
                        <th>Produto / Insumo</th>
                        <th>Código SKU</th>
                        <th>Unidade</th>
                        <th>Preço Referência</th>
                        <th>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredProducts.map(prod => (
                        <tr key={prod.id}>
                          <td>
                            <div className="cell-with-icon">
                              <div className="icon-badge blue-bg">
                                <Package size={14} />
                              </div>
                              <div>
                                <strong>{prod.name}</strong>
                                {prod.description && <span className="sub-label">{prod.description}</span>}
                              </div>
                            </div>
                          </td>
                          <td>
                            <span className="code-tag">{prod.sku}</span>
                          </td>
                          <td>
                            <span className="unit-badge">{prod.unit_of_measure}</span>
                          </td>
                          <td>
                            <strong>R$ {Number(prod.reference_price).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}</strong>
                          </td>
                          <td>
                            <span className={`badge-pill ${prod.is_active ? 'active' : 'inactive'}`}>
                              {prod.is_active ? <CheckCircle2 size={11} /> : <XCircle size={11} />}
                              {prod.is_active ? 'Ativo' : 'Inativo'}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )
            )}

            {/* TABELA: CENTROS DE CUSTO */}
            {activeMenu === 'centros-custo' && (
              loading ? (
                <div className="state-empty">Carregando centros de custo...</div>
              ) : filteredCostCenters.length === 0 ? (
                <div className="state-empty">Nenhum centro de custo encontrado.</div>
              ) : (
                <div className="table-responsive">
                  <table className="enterprise-table">
                    <thead>
                      <tr>
                        <th>Código</th>
                        <th>Nome do Centro de Custo</th>
                        <th>Descrição</th>
                        <th>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredCostCenters.map(cc => (
                        <tr key={cc.id}>
                          <td>
                            <span className="code-tag">{cc.code}</span>
                          </td>
                          <td>
                            <strong>{cc.name}</strong>
                          </td>
                          <td>{cc.description || 'Sem descrição'}</td>
                          <td>
                            <span className={`badge-pill ${cc.is_active ? 'active' : 'inactive'}`}>
                              {cc.is_active ? <CheckCircle2 size={11} /> : <XCircle size={11} />}
                              {cc.is_active ? 'Ativo' : 'Inativo'}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )
            )}

            {/* TABELA: ORGANIZAÇÕES */}
            {activeMenu === 'organizacoes' && (
              loading ? (
                <div className="state-empty">Carregando organizações...</div>
              ) : filteredOrgs.length === 0 ? (
                <div className="state-empty">Nenhuma organização encontrada.</div>
              ) : (
                <div className="table-responsive">
                  <table className="enterprise-table">
                    <thead>
                      <tr>
                        <th>Nome da Organização</th>
                        <th>Status</th>
                        <th>Data de Cadastro</th>
                        <th style={{ textAlign: 'right' }}>Ações</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredOrgs.map(org => (
                        <tr key={org.id}>
                          <td>
                            <div className="cell-with-icon">
                              <div className="icon-badge brand-bg">
                                <Building2 size={14} />
                              </div>
                              <strong>{org.name}</strong>
                            </div>
                          </td>
                          <td>
                            <span className={`badge-pill ${org.is_active ? 'active' : 'inactive'}`}>
                              {org.is_active ? <CheckCircle2 size={11} /> : <XCircle size={11} />}
                              {org.is_active ? 'Ativa' : 'Inativa'}
                            </span>
                          </td>
                          <td>{new Date(org.created_at).toLocaleDateString('pt-BR')}</td>
                          <td style={{ textAlign: 'right' }}>
                            {hasPermission('organizations:manage') && (
                              <button
                                className="btn-action-icon delete"
                                onClick={() => setItemToDelete({ id: org.id, name: org.name, type: 'org' })}
                                title="Excluir Organização"
                              >
                                <Trash2 size={14} />
                              </button>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )
            )}

            {/* TABELA: USUÁRIOS */}
            {activeMenu === 'usuarios' && (
              loading ? (
                <div className="state-empty">Carregando usuários...</div>
              ) : filteredUsers.length === 0 ? (
                <div className="state-empty">Nenhum usuário encontrado.</div>
              ) : (
                <div className="table-responsive">
                  <table className="enterprise-table">
                    <thead>
                      <tr>
                        <th>Colaborador</th>
                        <th>E-mail Corporativo</th>
                        <th>Status</th>
                        <th>Data de Cadastro</th>
                        <th style={{ textAlign: 'right' }}>Ações / Perfil</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredUsers.map(user => {
                        const isSelf = user.email === currentUserEmail;
                        return (
                          <tr key={user.id}>
                            <td>
                              <div 
                                className="cell-with-icon clickable" 
                                onClick={() => (hasPermission('users:edit') || isSelf) && handleOpenUserProfile(user)}
                                title="Clique para abrir o perfil do usuário"
                              >
                                <div className="avatar-circle-sm">
                                  {user.full_name.charAt(0).toUpperCase()}
                                </div>
                                <div>
                                  <strong>{user.full_name}</strong>
                                  {isSelf && <span className="badge-self">Você</span>}
                                </div>
                              </div>
                            </td>
                            <td>
                              <span className="email-text">
                                <Mail size={12} />
                                {user.email}
                              </span>
                            </td>
                            <td>
                              <span className={`badge-pill ${user.is_active ? 'active' : 'inactive'}`}>
                                {user.is_active ? <CheckCircle2 size={11} /> : <XCircle size={11} />}
                                {user.is_active ? 'Ativo' : 'Inativo'}
                              </span>
                            </td>
                            <td>{new Date(user.created_at).toLocaleDateString('pt-BR')}</td>
                            <td style={{ textAlign: 'right' }}>
                              <div className="row-actions">
                                {(hasPermission('users:edit') || isSelf) && (
                                  <button
                                    className="btn-action-icon edit"
                                    onClick={() => handleOpenUserProfile(user)}
                                    title="Editar Perfil do Usuário"
                                  >
                                    <Edit3 size={14} />
                                  </button>
                                )}

                                {hasPermission('users:delete') && (
                                  <button
                                    className="btn-action-icon delete"
                                    onClick={() => setItemToDelete({ id: user.id, name: user.full_name, type: 'user' })}
                                    disabled={isSelf}
                                    title={isSelf ? 'Você não pode excluir sua própria conta' : 'Desvincular / Excluir Usuário'}
                                  >
                                    <Trash2 size={14} />
                                  </button>
                                )}
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )
            )}

            {/* TABELA: CARGOS & PERMISSÕES */}
            {activeMenu === 'cargos' && (
              loading ? (
                <div className="state-empty">Carregando cargos...</div>
              ) : filteredRoles.length === 0 ? (
                <div className="state-empty">Nenhum cargo encontrado.</div>
              ) : (
                <div className="table-responsive">
                  <table className="enterprise-table">
                    <thead>
                      <tr>
                        <th>Nome do Cargo</th>
                        <th>Descrição da Função</th>
                        <th>Permissões Atribuídas</th>
                        <th>Status</th>
                        <th style={{ textAlign: 'right' }}>Ações</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredRoles.map(role => (
                        <tr key={role.id}>
                          <td>
                            <div 
                              className={`cell-with-icon ${hasPermission('roles:manage') ? 'clickable' : ''}`}
                              onClick={() => hasPermission('roles:manage') && handleOpenRoleEdit(role)}
                            >
                              <div className="icon-badge purple-bg">
                                <Shield size={14} />
                              </div>
                              <strong>{role.name}</strong>
                            </div>
                          </td>
                          <td>
                            <span className="role-desc-text">
                              {role.description || 'Sem descrição cadastrada'}
                            </span>
                          </td>
                          <td>
                            <button 
                              type="button"
                              className="badge-permissions-btn"
                              onClick={() => hasPermission('roles:manage') && handleOpenRoleEdit(role)}
                              disabled={!hasPermission('roles:manage')}
                              title="Configurar matriz de permissões"
                            >
                              <Shield size={12} />
                              <span>{role.permissions?.length || 0} permissões</span>
                            </button>
                          </td>
                          <td>
                            <span className={`badge-pill ${role.is_active ? 'active' : 'inactive'}`}>
                              {role.is_active ? <CheckCircle2 size={11} /> : <XCircle size={11} />}
                              {role.is_active ? 'Ativo' : 'Inativo'}
                            </span>
                          </td>
                          <td style={{ textAlign: 'right' }}>
                            {hasPermission('roles:manage') && (
                              <div className="row-actions">
                                <button
                                  className="btn-action-icon edit"
                                  onClick={() => handleOpenRoleEdit(role)}
                                  title="Editar Cargo e Permissões"
                                >
                                  <Edit3 size={14} />
                                </button>

                                <button
                                  className="btn-action-icon delete"
                                  onClick={() => setItemToDelete({ id: role.id, name: role.name, type: 'role' })}
                                  title="Excluir Cargo"
                                >
                                  <Trash2 size={14} />
                                </button>
                              </div>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )
            )}

          </div>
        </main>

      </div>

      {/* ============================================================= */}
      {/* 3. MODAL DE CRIAÇÃO (WIZARD POLIVALENTE)                       */}
      {/* ============================================================= */}
      <Modal
        isOpen={isModalOpen}
        onClose={() => !isSaving && setIsModalOpen(false)}
        title={
          activeMenu === 'fornecedores' ? 'Novo Fornecedor' :
          activeMenu === 'produtos' ? 'Novo Produto no Catálogo' :
          activeMenu === 'centros-custo' ? 'Novo Centro de Custo' :
          activeMenu === 'organizacoes' ? 'Nova Organização' :
          activeMenu === 'usuarios' ? 'Novo Usuário' :
          'Novo Cargo'
        }
        subtitle={
          activeMenu === 'fornecedores' ? 'Cadastre os dados fiscais e de contato da empresa parceira' :
          activeMenu === 'produtos' ? 'Cadastre o item, SKU e preço base de referência' :
          activeMenu === 'centros-custo' ? 'Cadastre o código e nome da unidade orçamentária' :
          activeMenu === 'organizacoes' ? 'Cadastre uma nova empresa ou filial' :
          activeMenu === 'usuarios' ? 'Crie uma conta de acesso para um colaborador' :
          'Defina o cargo e selecione a matriz de permissões'
        }
      >
        <form onSubmit={handleCreateSubmit} className="wizard-form">
          {modalError && (
            <div className="modal-alert-error">
              <AlertCircle size={14} />
              <span>{modalError}</span>
            </div>
          )}

          {/* FORNECEDOR */}
          {activeMenu === 'fornecedores' && (
            <>
              <div className="form-group">
                <label htmlFor="suppName">Razão Social / Nome Oficial *</label>
                <input
                  id="suppName"
                  type="text"
                  placeholder="Ex: Distribuidora Nacional de Medicamentos Ltda"
                  value={supplierName}
                  onChange={(e) => setSupplierName(e.target.value)}
                  required
                  autoFocus
                  disabled={isSaving}
                />
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label htmlFor="suppTradeName">Nome Fantasia</label>
                  <input
                    id="suppTradeName"
                    type="text"
                    placeholder="Ex: MedDistribuidora"
                    value={supplierTradeName}
                    onChange={(e) => setSupplierTradeName(e.target.value)}
                    disabled={isSaving}
                  />
                </div>

                <div className="form-group">
                  <label htmlFor="suppCnpj">CNPJ ou CPF *</label>
                  <input
                    id="suppCnpj"
                    type="text"
                    placeholder="00.000.000/0000-00"
                    value={supplierCnpj}
                    onChange={(e) => setSupplierCnpj(e.target.value)}
                    required
                    disabled={isSaving}
                  />
                </div>
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label htmlFor="suppEmail">E-mail Comercial</label>
                  <input
                    id="suppEmail"
                    type="email"
                    placeholder="vendas@fornecedor.com"
                    value={supplierEmail}
                    onChange={(e) => setSupplierEmail(e.target.value)}
                    disabled={isSaving}
                  />
                </div>

                <div className="form-group">
                  <label htmlFor="suppPhone">Telefone / WhatsApp</label>
                  <input
                    id="suppPhone"
                    type="text"
                    placeholder="(11) 99999-9999"
                    value={supplierPhone}
                    onChange={(e) => setSupplierPhone(e.target.value)}
                    disabled={isSaving}
                  />
                </div>
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label htmlFor="suppCity">Cidade</label>
                  <input
                    id="suppCity"
                    type="text"
                    placeholder="São Paulo"
                    value={supplierCity}
                    onChange={(e) => setSupplierCity(e.target.value)}
                    disabled={isSaving}
                  />
                </div>

                <div className="form-group">
                  <label htmlFor="suppState">Estado (UF)</label>
                  <input
                    id="suppState"
                    type="text"
                    placeholder="SP"
                    maxLength={2}
                    value={supplierState}
                    onChange={(e) => setSupplierState(e.target.value.toUpperCase())}
                    disabled={isSaving}
                  />
                </div>
              </div>
            </>
          )}

          {/* PRODUTO */}
          {activeMenu === 'produtos' && (
            <>
              <div className="form-row">
                <div className="form-group">
                  <label htmlFor="prodSku">Código SKU *</label>
                  <input
                    id="prodSku"
                    type="text"
                    placeholder="Ex: MAT-001"
                    value={productSku}
                    onChange={(e) => setProductSku(e.target.value)}
                    required
                    autoFocus
                    disabled={isSaving}
                  />
                </div>

                <div className="form-group">
                  <label htmlFor="prodUnit">Unidade de Medida</label>
                  <select
                    id="prodUnit"
                    value={productUnit}
                    onChange={(e) => setProductUnit(e.target.value)}
                    disabled={isSaving}
                  >
                    <option value="UN">Unidade (UN)</option>
                    <option value="KG">Quilograma (KG)</option>
                    <option value="L">Litro (L)</option>
                    <option value="CX">Caixa (CX)</option>
                    <option value="M">Metro (M)</option>
                    <option value="PCT">Pacote (PCT)</option>
                  </select>
                </div>
              </div>

              <div className="form-group">
                <label htmlFor="prodName">Nome do Produto / Insumo *</label>
                <input
                  id="prodName"
                  type="text"
                  placeholder="Ex: Luvas de Procedimento Nitrílicas"
                  value={productName}
                  onChange={(e) => setProductName(e.target.value)}
                  required
                  disabled={isSaving}
                />
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label htmlFor="prodPrice">Preço de Referência (R$)</label>
                  <input
                    id="prodPrice"
                    type="number"
                    step="0.01"
                    placeholder="0.00"
                    value={productPrice}
                    onChange={(e) => setProductPrice(e.target.value)}
                    disabled={isSaving}
                  />
                </div>

                <div className="form-group">
                  <label htmlFor="prodCategory">Categoria</label>
                  <select
                    id="prodCategory"
                    value={productCategoryId}
                    onChange={(e) => setProductCategoryId(e.target.value)}
                    disabled={isSaving}
                  >
                    <option value="">Geral / Sem Categoria</option>
                    {categories.map(cat => (
                      <option key={cat.id} value={cat.id}>{cat.name}</option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="form-group">
                <label htmlFor="prodDesc">Descrição Detalhada</label>
                <input
                  id="prodDesc"
                  type="text"
                  placeholder="Especificações técnicas, modelo ou marca sugerida"
                  value={productDesc}
                  onChange={(e) => setProductDesc(e.target.value)}
                  disabled={isSaving}
                />
              </div>
            </>
          )}

          {/* CENTRO DE CUSTO */}
          {activeMenu === 'centros-custo' && (
            <>
              <div className="form-group">
                <label htmlFor="ccCode">Código Contábil *</label>
                <input
                  id="ccCode"
                  type="text"
                  placeholder="Ex: CC-101"
                  value={costCenterCode}
                  onChange={(e) => setCostCenterCode(e.target.value)}
                  required
                  autoFocus
                  disabled={isSaving}
                />
              </div>

              <div className="form-group">
                <label htmlFor="ccName">Nome da Unidade / Setor *</label>
                <input
                  id="ccName"
                  type="text"
                  placeholder="Ex: Farmácia Central / UTI"
                  value={costCenterName}
                  onChange={(e) => setCostCenterName(e.target.value)}
                  required
                  disabled={isSaving}
                />
              </div>

              <div className="form-group">
                <label htmlFor="ccDesc">Descrição / Finalidade</label>
                <input
                  id="ccDesc"
                  type="text"
                  placeholder="Finalidade orçamentária"
                  value={costCenterDesc}
                  onChange={(e) => setCostCenterDesc(e.target.value)}
                  disabled={isSaving}
                />
              </div>
            </>
          )}

          {/* ORGANIZAÇÕES */}
          {activeMenu === 'organizacoes' && (
            <div className="form-group">
              <label htmlFor="orgName">Nome da Organização *</label>
              <input
                id="orgName"
                type="text"
                placeholder="Ex: FarmaNutri Filial Centro"
                value={orgName}
                onChange={(e) => setOrgName(e.target.value)}
                required
                autoFocus
                disabled={isSaving}
              />
            </div>
          )}

          {/* USUÁRIOS */}
          {activeMenu === 'usuarios' && (
            <>
              <div className="form-group">
                <label htmlFor="userName">Nome Completo *</label>
                <input
                  id="userName"
                  type="text"
                  placeholder="Ex: Carlos Silva"
                  value={userFullName}
                  onChange={(e) => setUserFullName(e.target.value)}
                  required
                  autoFocus
                  disabled={isSaving}
                />
              </div>

              <div className="form-group">
                <label htmlFor="userEmail">E-mail Corporativo *</label>
                <input
                  id="userEmail"
                  type="email"
                  placeholder="carlos@empresa.com"
                  value={userEmail}
                  onChange={(e) => setUserEmail(e.target.value)}
                  required
                  disabled={isSaving}
                />
              </div>

              <div className="form-group">
                <label htmlFor="userPassword">Senha Inicial *</label>
                <input
                  id="userPassword"
                  type="password"
                  placeholder="••••••••"
                  value={userPassword}
                  onChange={(e) => setUserPassword(e.target.value)}
                  required
                  disabled={isSaving}
                />
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label htmlFor="userOrg">Organização</label>
                  <select
                    id="userOrg"
                    value={userOrgId}
                    onChange={(e) => setUserOrgId(e.target.value)}
                    disabled={isSaving}
                  >
                    <option value="">Selecione...</option>
                    {organizations.map(org => (
                      <option key={org.id} value={org.id}>{org.name}</option>
                    ))}
                  </select>
                </div>

                <div className="form-group">
                  <label htmlFor="userRole">Cargo (Role)</label>
                  <select
                    id="userRole"
                    value={userRoleId}
                    onChange={(e) => setUserRoleId(e.target.value)}
                    disabled={isSaving}
                  >
                    <option value="">Selecione...</option>
                    {roles.map(role => (
                      <option key={role.id} value={role.id}>{role.name}</option>
                    ))}
                  </select>
                </div>
              </div>
            </>
          )}

          {/* CARGOS */}
          {activeMenu === 'cargos' && (
            <>
              <div className="form-group">
                <label htmlFor="roleName">Nome do Cargo *</label>
                <input
                  id="roleName"
                  type="text"
                  placeholder="Ex: Gestor de Compras"
                  value={roleName}
                  onChange={(e) => setRoleName(e.target.value)}
                  required
                  autoFocus
                  disabled={isSaving}
                />
              </div>

              <div className="form-group">
                <label htmlFor="roleDesc">Descrição da Função</label>
                <input
                  id="roleDesc"
                  type="text"
                  placeholder="Ex: Responsável por cotações e pedidos"
                  value={roleDescription}
                  onChange={(e) => setRoleDescription(e.target.value)}
                  disabled={isSaving}
                />
              </div>

              <div className="permissions-matrix-wrap">
                <span className="matrix-title">Matriz de Permissões de Acesso</span>
                <div className="permissions-modules-list">
                  {Object.entries(permissionsByModule).map(([moduleName, modulePerms]) => (
                    <div key={moduleName} className="module-group">
                      <span className="module-name">{moduleName}</span>
                      <div className="module-perms">
                        {modulePerms.map(perm => {
                          const isChecked = selectedPermissionIds.includes(perm.id);
                          return (
                            <div 
                              key={perm.id} 
                              className={`perm-checkbox-item ${isChecked ? 'checked' : ''}`}
                              onClick={() => togglePermission(perm.id, selectedPermissionIds, setSelectedPermissionIds)}
                            >
                              {isChecked ? <CheckSquare size={16} className="icon-checked" /> : <Square size={16} className="icon-square" />}
                              <div className="perm-labels">
                                <span className="perm-name">{perm.name}</span>
                                <span className="perm-code">{perm.code}</span>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}

          <footer className="modal-footer">
            <button
              type="button"
              className="btn-cancel"
              onClick={() => setIsModalOpen(false)}
              disabled={isSaving}
            >
              Cancelar
            </button>

            <button type="submit" className="btn-save" disabled={isSaving}>
              {isSaving ? (
                <>
                  <Loader2 size={14} className="spin" />
                  <span>Salvando...</span>
                </>
              ) : (
                <span>Salvar Registro</span>
              )}
            </button>
          </footer>
        </form>
      </Modal>

      {/* MODAL DE PERFIL / EDIÇÃO DE USUÁRIO */}
      <Modal
        isOpen={isProfileModalOpen}
        onClose={() => !isSaving && setIsProfileModalOpen(false)}
        title="Perfil do Usuário"
        subtitle="Gerencie as informações cadastrais, acessos e desvinculação"
      >
        {selectedUser && (
          <form onSubmit={handleSaveUserProfile} className="wizard-form">
            {modalError && (
              <div className="modal-alert-error">
                <AlertCircle size={14} />
                <span>{modalError}</span>
              </div>
            )}

            <div className="profile-card-header">
              <div className="avatar-xl">
                {selectedUser.full_name.charAt(0).toUpperCase()}
              </div>
              <div className="info">
                <h3>{selectedUser.full_name}</h3>
                <span className="email">{selectedUser.email}</span>
                <span className="created">Cadastrado em {new Date(selectedUser.created_at).toLocaleDateString('pt-BR')}</span>
              </div>
            </div>

            <div className="form-group">
              <label htmlFor="editName">Nome Completo *</label>
              <input
                id="editName"
                type="text"
                value={editFullName}
                onChange={(e) => setEditFullName(e.target.value)}
                required
                disabled={isSaving || (!hasPermission('users:edit') && selectedUser.email !== currentUserEmail)}
              />
            </div>

            <div className="form-group">
              <label htmlFor="editEmail">E-mail Corporativo *</label>
              <input
                id="editEmail"
                type="email"
                value={editEmail}
                onChange={(e) => setEditEmail(e.target.value)}
                required
                disabled={isSaving || !hasPermission('users:edit')}
              />
            </div>

            <div className="form-row">
              <div className="form-group">
                <label htmlFor="editOrg">Organização Vinculada</label>
                <select
                  id="editOrg"
                  value={editOrgId}
                  onChange={(e) => setEditOrgId(e.target.value)}
                  disabled={isSaving || !hasPermission('users:edit')}
                >
                  <option value="">Selecione...</option>
                  {organizations.map(org => (
                    <option key={org.id} value={org.id}>{org.name}</option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label htmlFor="editRole">Cargo / Perfil</label>
                <select
                  id="editRole"
                  value={editRoleId}
                  onChange={(e) => setEditRoleId(e.target.value)}
                  disabled={isSaving || !hasPermission('users:edit')}
                >
                  <option value="">Selecione...</option>
                  {roles.map(role => (
                    <option key={role.id} value={role.id}>{role.name}</option>
                  ))}
                </select>
              </div>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label htmlFor="editStatus">Status da Conta</label>
                <select
                  id="editStatus"
                  value={editIsActive ? 'active' : 'inactive'}
                  onChange={(e) => setEditIsActive(e.target.value === 'active')}
                  disabled={isSaving || !hasPermission('users:edit')}
                >
                  <option value="active">Ativo (Acesso Liberado)</option>
                  <option value="inactive">Inativo (Acesso Bloqueado)</option>
                </select>
              </div>

              <div className="form-group">
                <label htmlFor="editPassword">Redefinir Senha</label>
                <input
                  id="editPassword"
                  type="password"
                  placeholder="Nova senha (opcional)"
                  value={editNewPassword}
                  onChange={(e) => setEditNewPassword(e.target.value)}
                  disabled={isSaving}
                />
              </div>
            </div>

            <footer className="modal-footer space-between">
              {hasPermission('users:delete') && (
                <button
                  type="button"
                  className="btn-danger-unlink"
                  onClick={() => setItemToDelete({ id: selectedUser.id, name: selectedUser.full_name, type: 'user' })}
                  disabled={isSaving || selectedUser.email === currentUserEmail}
                  title={selectedUser.email === currentUserEmail ? 'Você não pode excluir sua própria conta' : 'Desvincular e Excluir Usuário'}
                >
                  <Trash2 size={14} />
                  <span>Desvincular Usuário</span>
                </button>
              )}

              <div className="right-actions">
                <button
                  type="button"
                  className="btn-cancel"
                  onClick={() => setIsProfileModalOpen(false)}
                  disabled={isSaving}
                >
                  Cancelar
                </button>

                <button type="submit" className="btn-save" disabled={isSaving}>
                  {isSaving ? (
                    <>
                      <Loader2 size={14} className="spin" />
                      <span>Salvando...</span>
                    </>
                  ) : (
                    <span>Salvar Alterações</span>
                  )}
                </button>
              </div>
            </footer>
          </form>
        )}
      </Modal>

      {/* MODAL DE EDIÇÃO DE CARGO & MATRIZ DE PERMISSÕES */}
      <Modal
        isOpen={isRoleModalOpen}
        onClose={() => !isSaving && setIsRoleModalOpen(false)}
        title="Editar Cargo & Permissões"
        subtitle="Configure os dados do cargo e a matriz de acessos permitidos"
      >
        {selectedRole && (
          <form onSubmit={handleSaveRole} className="wizard-form">
            {modalError && (
              <div className="modal-alert-error">
                <AlertCircle size={14} />
                <span>{modalError}</span>
              </div>
            )}

            <div className="form-group">
              <label htmlFor="editRoleName">Nome do Cargo *</label>
              <input
                id="editRoleName"
                type="text"
                value={editRoleName}
                onChange={(e) => setEditRoleName(e.target.value)}
                required
                disabled={isSaving}
              />
            </div>

            <div className="form-group">
              <label htmlFor="editRoleDesc">Descrição da Função</label>
              <input
                id="editRoleDesc"
                type="text"
                value={editRoleDescription}
                onChange={(e) => setEditRoleDescription(e.target.value)}
                disabled={isSaving}
              />
            </div>

            <div className="permissions-matrix-wrap">
              <span className="matrix-title">Matriz de Permissões de Acesso</span>
              <div className="permissions-modules-list">
                {Object.entries(permissionsByModule).map(([moduleName, modulePerms]) => (
                  <div key={moduleName} className="module-group">
                    <span className="module-name">{moduleName}</span>
                    <div className="module-perms">
                      {modulePerms.map(perm => {
                        const isChecked = editRolePermissionIds.includes(perm.id);
                        return (
                          <div 
                            key={perm.id} 
                            className={`perm-checkbox-item ${isChecked ? 'checked' : ''}`}
                            onClick={() => togglePermission(perm.id, editRolePermissionIds, setEditRolePermissionIds)}
                          >
                            {isChecked ? <CheckSquare size={16} className="icon-checked" /> : <Square size={16} className="icon-square" />}
                            <div className="perm-labels">
                              <span className="perm-name">{perm.name}</span>
                              <span className="perm-code">{perm.code}</span>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <footer className="modal-footer">
              <button
                type="button"
                className="btn-cancel"
                onClick={() => setIsRoleModalOpen(false)}
                disabled={isSaving}
              >
                Cancelar
              </button>

              <button type="submit" className="btn-save" disabled={isSaving}>
                {isSaving ? (
                  <>
                    <Loader2 size={14} className="spin" />
                    <span>Salvando...</span>
                  </>
                ) : (
                  <span>Salvar Permissões</span>
                )}
              </button>
            </footer>
          </form>
        )}
      </Modal>

      {/* MODAL DE CONFIRMAÇÃO DE EXCLUSÃO */}
      <Modal
        isOpen={!!itemToDelete}
        onClose={() => !isDeleting && setItemToDelete(null)}
        title="Confirmar Exclusão"
      >
        {itemToDelete && (
          <div className="delete-confirm-box">
            <div className="icon-warning-wrap">
              <ShieldAlert size={32} />
            </div>

            <p className="confirm-text">
              Tem certeza que deseja excluir permanentemente{' '}
              <strong>"{itemToDelete.name}"</strong>?
            </p>
            <p className="subtext">
              Esta ação removerá todos os vínculos associados e não poderá ser desfeita.
            </p>

            <div className="confirm-actions">
              <button
                className="btn-cancel"
                onClick={() => setItemToDelete(null)}
                disabled={isDeleting}
              >
                Voltar
              </button>

              <button
                className="btn-confirm-delete"
                onClick={handleConfirmDelete}
                disabled={isDeleting}
              >
                {isDeleting ? (
                  <>
                    <Loader2 size={14} className="spin" />
                    <span>Excluindo...</span>
                  </>
                ) : (
                  <>
                    <Trash2 size={14} />
                    <span>Sim, Excluir</span>
                  </>
                )}
              </button>
            </div>
          </div>
        )}
      </Modal>

    </div>
  );
};
