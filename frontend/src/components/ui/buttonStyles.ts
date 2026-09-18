const variants = {
  primary: "bg-indigo-600 text-white hover:bg-indigo-700",
  secondary: "bg-white text-slate-800 border border-slate-300 hover:bg-slate-50",
  ghost: "text-slate-700 hover:bg-slate-100",
  danger: "bg-red-600 text-white hover:bg-red-700",
};
const sizes = { sm: "px-2.5 py-1.5 text-sm", md: "px-4 py-2 text-sm" };

export type ButtonVariant = keyof typeof variants;
export type ButtonSize = keyof typeof sizes;

// Shared with links styled as buttons: an <a> must not contain a <button>.
export function buttonClasses(variant: ButtonVariant = "primary", size: ButtonSize = "md") {
  return `inline-flex items-center justify-center gap-2 rounded-lg font-medium transition focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 disabled:cursor-not-allowed disabled:opacity-50 ${variants[variant]} ${sizes[size]}`;
}
