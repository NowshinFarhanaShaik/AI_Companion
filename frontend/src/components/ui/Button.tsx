import type { ButtonHTMLAttributes } from "react";
import { buttonClasses, type ButtonSize, type ButtonVariant } from "./buttonStyles";

type Props = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant; size?: ButtonSize; loading?: boolean };

export function Button({ variant, size, loading, disabled, className = "", children, ...rest }: Props) {
  return (
    <button {...rest} disabled={disabled || loading} className={`${buttonClasses(variant, size)} ${className}`}>
      {loading ? "Working…" : children}
    </button>
  );
}
