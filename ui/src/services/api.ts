/**
 * API service for communicating with the FastFoodOrdering backend
 */

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8080';

export interface BrowserGeoLocation {
  latitude: number;
  longitude: number;
  accuracy: number;
}

export interface SessionManagerPrompt {
  user: string;
  prompt: string;
  session_id?: string | null;
  current_geolocation?: BrowserGeoLocation | null;
}

export interface SessionManagerChatResult {
  response: string;
  session_id?: string | null;
}

export interface SessionId {
  session_id: string;
}

export interface SessionObjective {
  objective: string;
}

export interface BrowserBase64Screenshot {
  b64_encoded_image: string;
}

export interface BrowserClickCoordinates {
  x: number;
  y: number;
}

/**
 * Main chat endpoint for session manager agent
 * POST /{user}/sessions/chat
 */
export async function sendSessionChat(
  user: string,
  prompt: string,
  sessionId?: string | null,
  geolocation?: BrowserGeoLocation | null
): Promise<SessionManagerChatResult> {
  const payload: SessionManagerPrompt = {
    user,
    prompt,
    session_id: sessionId,
    current_geolocation: geolocation,
  };

  const response = await fetch(`${BACKEND_URL}/${user}/sessions/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(`API error: ${response.status} ${response.statusText}`);
  }

  return response.json();
}

/**
 * Get all sessions for a user
 * GET /{user}/sessions
 */
export async function getSessions(user: string): Promise<string[]> {
  const response = await fetch(`${BACKEND_URL}/${user}/sessions`, {
    method: 'GET',
  });

  if (!response.ok) {
    throw new Error(`API error: ${response.status} ${response.statusText}`);
  }

  return response.json();
}

/**
 * Create a new session with auto-generated ID
 * POST /{user}/sessions
 */
export async function createSession(
  user: string,
  objective: string
): Promise<SessionId> {
  const response = await fetch(`${BACKEND_URL}/${user}/sessions`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ objective } as SessionObjective),
  });

  if (!response.ok) {
    throw new Error(`API error: ${response.status} ${response.statusText}`);
  }

  return response.json();
}

/**
 * Update an existing session
 * PUT /{user}/sessions/{session_id}
 */
export async function updateSession(
  user: string,
  sessionId: string,
  objective: string
): Promise<SessionId> {
  const response = await fetch(`${BACKEND_URL}/${user}/sessions/${sessionId}`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ objective } as SessionObjective),
  });

  if (!response.ok) {
    throw new Error(`API error: ${response.status} ${response.statusText}`);
  }

  return response.json();
}

/**
 * Get a single screenshot from a session
 * GET /{user}/sessions/{session_id}/screenshot
 */
export async function getScreenshot(
  user: string,
  sessionId: string
): Promise<BrowserBase64Screenshot> {
  const response = await fetch(
    `${BACKEND_URL}/${user}/sessions/${sessionId}/screenshot`,
    {
      method: 'GET',
    }
  );

  if (!response.ok) {
    throw new Error(`API error: ${response.status} ${response.statusText}`);
  }

  return response.json();
}

/**
 * Get the browser screenshot stream URL
 * GET /{user}/sessions/{session_id}/screenshot/stream
 */
export function getScreenshotStreamUrl(user: string, sessionId: string): string {
  return `${BACKEND_URL}/${user}/sessions/${sessionId}/screenshot/stream`;
}

/**
 * Send a click event to the browser at relative coordinates (0-1 range)
 * POST /{user}/sessions/{session_id}/click
 */
export async function sendBrowserClick(
  user: string,
  sessionId: string,
  x: number,
  y: number
): Promise<void> {
  const payload: BrowserClickCoordinates = { x, y };

  const response = await fetch(
    `${BACKEND_URL}/${user}/sessions/${sessionId}/click`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    }
  );

  if (!response.ok) {
    throw new Error(`API error: ${response.status} ${response.statusText}`);
  }
}
