export interface User {
  id: string;
  name: string;
  email: string;
  picture: string;
  is_superuser?: boolean;
  tenant_id?: string | null;
  roles?: string[];
}
