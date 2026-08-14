export type DesktopSyncProjectLoadInvalidation =
  | 'dialog_close'
  | 'auth_change'
  | 'permission_changed'
  | 'unmount'

export interface DesktopSyncProjectLoadTicket {
  generation: number
  userId: string
}

export function createDesktopSyncProjectLoadCycle() {
  let generation = 0

  return {
    begin(userId: string): DesktopSyncProjectLoadTicket {
      generation += 1
      return Object.freeze({ generation, userId })
    },

    invalidate(_reason: DesktopSyncProjectLoadInvalidation): void {
      generation += 1
    },

    isCurrent(ticket: DesktopSyncProjectLoadTicket, currentUserId: string | null): boolean {
      return (
        ticket.generation === generation
        && ticket.userId === currentUserId
      )
    },
  }
}
