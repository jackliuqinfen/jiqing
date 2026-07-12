export function getLoadedProjectPageCount(recordCount: number, pageSize: number) {
  const safePageSize = Math.max(1, pageSize)
  return Math.max(1, Math.ceil(Math.max(0, recordCount) / safePageSize))
}

export function flattenLoadedProjectPages<T>(pages: ReadonlyArray<ReadonlyArray<T>>) {
  return pages.flatMap((page) => page)
}

type LifecycleRefreshTasks<TSnapshot, TAncillary> = {
  snapshot: () => Promise<TSnapshot> | TSnapshot
  ancillary: Array<() => Promise<TAncillary> | TAncillary>
}

export async function settleLifecycleRefresh<TSnapshot, TAncillary>(tasks: LifecycleRefreshTasks<TSnapshot, TAncillary>) {
  let snapshotPromise: Promise<TSnapshot>
  try {
    snapshotPromise = Promise.resolve(tasks.snapshot())
  } catch (error) {
    snapshotPromise = Promise.reject(error)
  }

  const ancillaryPromises = tasks.ancillary.map((task) => Promise.resolve().then(task))
  const [snapshot, ancillary] = await Promise.all([
    Promise.allSettled([snapshotPromise]).then(([result]) => result),
    Promise.allSettled(ancillaryPromises),
  ])

  return { snapshot, ancillary }
}
