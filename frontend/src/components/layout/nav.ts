export type NavItem = { to: string; label: string; staffOnly?: boolean };

export const navItems: NavItem[] = [
  { to: "/", label: "Home" },
  { to: "/spaces", label: "Spaces" },
  { to: "/analytics", label: "Analytics" },
  { to: "/admin", label: "Admin", staffOnly: true },
];
