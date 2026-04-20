// [v84-2-4-2][front-nextjs:pages]
import { AdminShell } from '@/modules/admin/components';

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return <AdminShell>{children}</AdminShell>;
}
