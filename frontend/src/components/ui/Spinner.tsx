const sizes = { sm: "h-4 w-4", md: "h-6 w-6" };

// A span, so it is valid inside paragraphs and buttons as well as block containers.
export function Spinner({ size = "md", className = "" }: { size?: keyof typeof sizes; className?: string }) {
  return (
    <span
      role="status"
      aria-label="Loading"
      className={`block animate-spin rounded-full border-2 border-slate-300 border-t-indigo-600 ${sizes[size]} ${className}`}
    />
  );
}
