import { Outlet } from "react-router";

export function PublicLayout() {
  return (
    <main className="bg-background text-foreground">
      <Outlet />
    </main>
  );
}
