// [v84-4-3-1][front-nextjs:api]
export interface Session {
  id: string;
  userId: string;
  deviceName: string | null;
  deviceOs: string | null;
  ipAddress: string | null;
  lastSeenAt: string;
  createdAt: string;
}
