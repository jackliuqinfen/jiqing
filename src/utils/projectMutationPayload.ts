export type ProjectMutationMode = 'create' | 'edit'

type ProjectMutationFields = Record<string, unknown>

export function buildProjectMutationPayload<T extends ProjectMutationFields>(mode: ProjectMutationMode, form: T) {
  if (mode === 'create') {
    throw new Error('Formal projects must be created by contract review confirmation')
  }

  const {
    projectStatus: _projectStatus,
    auditStage: _auditStage,
    auditProjectId: _auditProjectId,
    ...editableFields
  } = form

  return editableFields
}
