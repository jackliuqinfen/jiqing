export type ProjectMutationMode = 'create' | 'edit'

type ProjectMutationFields = Record<string, unknown>

export function buildProjectMutationPayload<T extends ProjectMutationFields>(mode: ProjectMutationMode, form: T) {
  const {
    projectStatus: _projectStatus,
    auditStage: _auditStage,
    auditProjectId: _auditProjectId,
    ...editableFields
  } = form

  if (mode === 'create') {
    return {
      ...editableFields,
      projectStatus: 'awarded',
      auditStage: 'not_linked',
    }
  }

  return editableFields
}
