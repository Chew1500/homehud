/** Shared types for the Hearth API surface. Kept minimal for scaffolding;
 *  specific endpoints will extend these as each tab is ported. */

export interface AuthStatus {
  authenticated: boolean;
  user_id: string;
  admin: boolean;
}

export interface PairResponse {
  token: string;
  user_id: string;
  admin: boolean;
}

export interface ApiError {
  error: string;
}

/** Thrown by the API client for non-2xx responses. */
export class ApiFetchError extends Error {
  constructor(
    public status: number,
    public payload: unknown,
    message?: string,
  ) {
    super(message ?? `API ${status}`);
    this.name = 'ApiFetchError';
  }

  get isUnauthorized() {
    return this.status === 401;
  }

  get isForbidden() {
    return this.status === 403;
  }
}
