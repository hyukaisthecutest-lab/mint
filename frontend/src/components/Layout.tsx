import { Outlet, NavLink, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { LayoutDashboard, CreditCard, ArrowLeftRight, LogOut, Leaf } from "lucide-react";
import { useAuthStore } from "../store/authStore";
import { getMe } from "../api/auth";

const navItems = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/accounts", label: "Accounts", icon: CreditCard },
  { to: "/transactions", label: "Transactions", icon: ArrowLeftRight },
];

export default function Layout() {
  const { logout, setUser } = useAuthStore();
  const navigate = useNavigate();

  const { data: user } = useQuery({
    queryKey: ["me"],
    queryFn: async () => {
      const u = await getMe();
      setUser(u);
      return u;
    },
  });

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  return (
    <div className="flex h-screen bg-gray-50">
      <aside className="w-64 bg-mint-700 text-white flex flex-col">
        <div className="p-6 flex items-center gap-2 border-b border-mint-600">
          <Leaf className="w-7 h-7 text-mint-200" />
          <span className="text-2xl font-bold tracking-tight">mint</span>
        </div>
        <nav className="flex-1 p-4 space-y-1">
          {navItems.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${
                  isActive ? "bg-mint-600 text-white" : "text-mint-100 hover:bg-mint-600/50"
                }`
              }
            >
              <Icon className="w-5 h-5" />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="p-4 border-t border-mint-600">
          {user && (
            <div className="px-4 py-2 mb-2 text-sm text-mint-200">
              {user.first_name} {user.last_name}
            </div>
          )}
          <button
            onClick={handleLogout}
            className="flex items-center gap-3 px-4 py-3 w-full rounded-lg text-mint-100 hover:bg-mint-600/50 transition-colors"
          >
            <LogOut className="w-5 h-5" />
            Sign out
          </button>
        </div>
      </aside>
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  );
}
