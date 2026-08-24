import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Edit3,
  Plus,
  RefreshCw,
  ShieldCheck,
  Trash2,
  UserRound,
  Users,
} from 'lucide-react';

import { Can } from '@/components/Can';
import { ConfirmModal } from '@/components/ConfirmModal/ConfirmModal';
import { Modal } from '@/components/Modal/Modal';
import { useToast } from '@/components/Toast/ToastContext';
import { formatApiError, identityService } from '@/services/api';
import type { Team, TeamMemberInfo } from '@/types';

import './CommercialTeamsSettings.scss';

const MANAGE_PERMISSIONS = ['teams:manage', 'users:edit', 'crm:manage', 'sales:manage'];

interface TeamFormState {
  name: string;
  code: string;
  description: string;
  leader_id: string;
  member_ids: string[];
  is_active: boolean;
}

const EMPTY_FORM: TeamFormState = {
  name: '',
  code: '',
  description: '',
  leader_id: '',
  member_ids: [],
  is_active: true,
};

export const CommercialTeamsSettings: React.FC = () => {
  const toast = useToast();
  const [teams, setTeams] = useState<Team[]>([]);
  const [candidates, setCandidates] = useState<TeamMemberInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [isEditorOpen, setIsEditorOpen] = useState(false);
  const [editingTeam, setEditingTeam] = useState<Team | null>(null);
  const [teamToDelete, setTeamToDelete] = useState<Team | null>(null);
  const [form, setForm] = useState<TeamFormState>(EMPTY_FORM);

  const loadData = useCallback(async (forceRefresh = false) => {
    setLoading(true);
    try {
      const [teamData, candidateData] = await Promise.all([
        identityService.getTeams('SALES', forceRefresh),
        identityService.getTeamCandidates(forceRefresh),
      ]);
      setTeams(teamData);
      setCandidates(candidateData);
    } catch (error) {
      toast.error(formatApiError(error, 'Não foi possível carregar as equipes comerciais.'));
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const activeCount = useMemo(
    () => teams.filter((team) => team.is_active).length,
    [teams],
  );

  const openCreate = () => {
    setEditingTeam(null);
    setForm(EMPTY_FORM);
    setIsEditorOpen(true);
  };

  const openEdit = (team: Team) => {
    setEditingTeam(team);
    setForm({
      name: team.name,
      code: team.code ?? '',
      description: team.description ?? '',
      leader_id: team.leader_id ?? '',
      member_ids: team.members.map((member) => member.id),
      is_active: team.is_active,
    });
    setIsEditorOpen(true);
  };

  const closeEditor = () => {
    if (saving) return;
    setIsEditorOpen(false);
    setEditingTeam(null);
    setForm(EMPTY_FORM);
  };

  const toggleMember = (userId: string) => {
    if (userId === form.leader_id) return;
    setForm((current) => ({
      ...current,
      member_ids: current.member_ids.includes(userId)
        ? current.member_ids.filter((id) => id !== userId)
        : [...current.member_ids, userId],
    }));
  };

  const handleLeaderChange = (leaderId: string) => {
    setForm((current) => ({
      ...current,
      leader_id: leaderId,
      member_ids: leaderId && !current.member_ids.includes(leaderId)
        ? [...current.member_ids, leaderId]
        : current.member_ids,
    }));
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!form.name.trim()) return;
    setSaving(true);
    try {
      const payload = {
        name: form.name.trim(),
        code: form.code.trim() || null,
        module_category: 'SALES',
        description: form.description.trim() || null,
        leader_id: form.leader_id || null,
        member_ids: form.member_ids,
        is_active: form.is_active,
      };
      if (editingTeam?.id) {
        await identityService.updateTeam(editingTeam.id, payload);
        toast.success('Equipe comercial atualizada.');
      } else {
        await identityService.createTeam({
          ...payload,
          code: payload.code ?? undefined,
          description: payload.description ?? undefined,
          leader_id: payload.leader_id ?? undefined,
        });
        toast.success('Equipe comercial criada.');
      }
      setIsEditorOpen(false);
      setEditingTeam(null);
      setForm(EMPTY_FORM);
      await loadData(true);
    } catch (error) {
      toast.error(formatApiError(error, 'Não foi possível salvar a equipe comercial.'));
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!teamToDelete) return;
    setDeleting(true);
    try {
      await identityService.deleteTeam(teamToDelete.id);
      toast.success('Equipe comercial excluída.');
      setTeamToDelete(null);
      await loadData(true);
    } catch (error) {
      toast.error(formatApiError(error, 'Não foi possível excluir a equipe comercial.'));
    } finally {
      setDeleting(false);
    }
  };

  return (
    <section className="commercial-teams-settings" aria-labelledby="commercial-teams-title">
      <div className="commercial-teams-header">
        <div className="commercial-teams-title-wrap">
          <div className="commercial-teams-icon"><Users size={21} /></div>
          <div>
            <h2 id="commercial-teams-title">Equipes comerciais</h2>
            <p>Estrutura única do Identity compartilhada por CRM e Vendas.</p>
          </div>
        </div>
        <div className="commercial-teams-actions">
          <span className="commercial-teams-counter">{activeCount} ativas</span>
          <button
            type="button"
            className="commercial-team-icon-button"
            onClick={() => void loadData(true)}
            disabled={loading}
            aria-label="Atualizar equipes"
            title="Atualizar equipes"
          >
            <RefreshCw size={16} className={loading ? 'spinning' : ''} />
          </button>
          <Can anyOf={MANAGE_PERMISSIONS}>
            <button type="button" className="commercial-team-primary-button" onClick={openCreate}>
              <Plus size={16} /> Nova equipe
            </button>
          </Can>
        </div>
      </div>

      <div className="commercial-teams-note">
        <ShieldCheck size={17} />
        <span>A categoria <strong>SALES</strong> define escopo e vínculos comerciais; os usuários continuam pertencendo ao Identity.</span>
      </div>

      {loading ? (
        <div className="commercial-teams-empty"><RefreshCw size={22} className="spinning" /> Carregando equipes...</div>
      ) : teams.length === 0 ? (
        <div className="commercial-teams-empty">
          <Users size={28} />
          <strong>Nenhuma equipe comercial cadastrada</strong>
          <span>Crie a primeira equipe para organizar lideranca, membros e escopo de dados.</span>
        </div>
      ) : (
        <div className="commercial-teams-grid">
          {teams.map((team) => (
            <article key={team.id} className={`commercial-team-card ${team.is_active ? '' : 'is-inactive'}`}>
              <div className="commercial-team-card-header">
                <div>
                  <div className="commercial-team-name-row">
                    <h3>{team.name}</h3>
                    <span className={`commercial-team-status ${team.is_active ? 'active' : 'inactive'}`}>
                      {team.is_active ? 'Ativa' : 'Inativa'}
                    </span>
                  </div>
                  {team.code && <code>{team.code}</code>}
                </div>
                <Can anyOf={MANAGE_PERMISSIONS}>
                  <div className="commercial-team-card-actions">
                    <button type="button" onClick={() => openEdit(team)} aria-label={`Editar ${team.name}`} title="Editar equipe">
                      <Edit3 size={15} />
                    </button>
                    <button type="button" className="danger" onClick={() => setTeamToDelete(team)} aria-label={`Excluir ${team.name}`} title="Excluir equipe">
                      <Trash2 size={15} />
                    </button>
                  </div>
                </Can>
              </div>
              {team.description && <p className="commercial-team-description">{team.description}</p>}
              <div className="commercial-team-leader">
                <UserRound size={16} />
                <span><small>Líder</small>{team.leader_name || 'Não definido'}</span>
              </div>
              <div className="commercial-team-members">
                <span className="commercial-team-members-title">{team.members.length} integrantes</span>
                <div className="commercial-team-member-list">
                  {team.members.length > 0
                    ? team.members.map((member) => <span key={member.id}>{member.full_name}</span>)
                    : <em>Sem integrantes</em>}
                </div>
              </div>
            </article>
          ))}
        </div>
      )}

      <Modal
        isOpen={isEditorOpen}
        onClose={closeEditor}
        title={editingTeam ? 'Editar equipe comercial' : 'Nova equipe comercial'}
        subtitle="O mesmo cadastro será utilizado no CRM e no módulo de Vendas."
        size="lg"
      >
        <form className="commercial-team-form" onSubmit={handleSubmit}>
          <div className="commercial-team-form-row">
            <label>
              <span>Nome da equipe *</span>
              <input required maxLength={100} value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} placeholder="Ex: Equipe Nordeste" />
            </label>
            <label>
              <span>Código</span>
              <input maxLength={50} value={form.code} onChange={(event) => setForm({ ...form, code: event.target.value.toUpperCase() })} placeholder="Ex: NORDESTE" />
            </label>
          </div>
          <label>
            <span>Descricao</span>
            <textarea maxLength={255} rows={3} value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} placeholder="Responsabilidade ou carteira atendida pela equipe" />
          </label>
          <div className="commercial-team-form-row">
            <label>
              <span>Lider da equipe</span>
              <select value={form.leader_id} onChange={(event) => handleLeaderChange(event.target.value)}>
                <option value="">Sem lider definido</option>
                {candidates.map((candidate) => <option key={candidate.id} value={candidate.id}>{candidate.full_name}</option>)}
              </select>
            </label>
            <label className="commercial-team-active-toggle">
              <input type="checkbox" checked={form.is_active} onChange={(event) => setForm({ ...form, is_active: event.target.checked })} />
              <span>Equipe ativa</span>
            </label>
          </div>
          <fieldset className="commercial-team-member-selector">
            <legend>Integrantes ({form.member_ids.length})</legend>
            {candidates.length === 0 ? (
              <p>Nenhum colaborador ativo disponível.</p>
            ) : (
              <div className="commercial-team-candidate-grid">
                {candidates.map((candidate) => {
                  const isLeader = candidate.id === form.leader_id;
                  return (
                    <label key={candidate.id} className={isLeader ? 'is-leader' : ''}>
                      <input
                        type="checkbox"
                        checked={form.member_ids.includes(candidate.id)}
                        disabled={isLeader}
                        onChange={() => toggleMember(candidate.id)}
                      />
                      <span><strong>{candidate.full_name}</strong><small>{candidate.email}</small></span>
                      {isLeader && <em>Lider</em>}
                    </label>
                  );
                })}
              </div>
            )}
          </fieldset>
          <div className="commercial-team-form-actions">
            <button type="button" className="secondary" onClick={closeEditor} disabled={saving}>Cancelar</button>
            <button type="submit" className="primary" disabled={saving || !form.name.trim()}>
              {saving ? 'Salvando...' : 'Salvar equipe'}
            </button>
          </div>
        </form>
      </Modal>

      <ConfirmModal
        isOpen={teamToDelete !== null}
        onClose={() => !deleting && setTeamToDelete(null)}
        onConfirm={handleDelete}
        title="Excluir equipe comercial?"
        message={<>A equipe <strong>{teamToDelete?.name}</strong> será removida do CRM e de Vendas, pois ambos usam o mesmo cadastro.</>}
        confirmText="Excluir equipe"
        isLoading={deleting}
      />
    </section>
  );
};
