/**
 * The application's type surface.
 *
 * Mirrors `backend/app/schemas`. When a schema changes on the server, the
 * matching declaration here must change with it — both sides will compile
 * happily otherwise and disagree only at runtime.
 */

export * from './api'
export * from './dashboard'
export * from './domain'
export * from './enums'
export * from './intelligence'
export * from './navigation'
