"use client";

import * as DialogPrimitive from "@radix-ui/react-dialog";
import * as SelectPrimitive from "@radix-ui/react-select";
import * as TabsPrimitive from "@radix-ui/react-tabs";
import * as TooltipPrimitive from "@radix-ui/react-tooltip";
import { Check, ChevronDown, X } from "lucide-react";
import type {
  ButtonHTMLAttributes,
  HTMLAttributes,
  InputHTMLAttributes,
  ReactNode,
  SelectHTMLAttributes,
  TextareaHTMLAttributes,
} from "react";
import { cn } from "@/lib/utils";

export function Button({
  className,
  variant = "primary",
  size = "default",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  size?: "default" | "small" | "icon";
}) {
  return (
    <button
      className={cn("ui-button", `ui-button-${variant}`, `ui-button-${size}`, className)}
      {...props}
    />
  );
}

export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={cn("ui-input", className)} {...props} />;
}

export function Textarea({
  className,
  ...props
}: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={cn("ui-input ui-textarea", className)} {...props} />;
}

export function NativeSelect({
  className,
  children,
  ...props
}: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select className={cn("ui-input ui-native-select", className)} {...props}>
      {children}
    </select>
  );
}

export function Badge({
  className,
  tone = "neutral",
  ...props
}: HTMLAttributes<HTMLSpanElement> & {
  tone?: "neutral" | "success" | "warning" | "info" | "danger";
}) {
  return <span className={cn("ui-badge", `ui-badge-${tone}`, className)} {...props} />;
}

export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("ui-card", className)} {...props} />;
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("skeleton", className)} aria-hidden="true" />;
}

export function Progress({ value }: { value: number }) {
  return (
    <div
      className="ui-progress"
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={value}
    >
      <div style={{ width: `${Math.max(0, Math.min(100, value))}%` }} />
    </div>
  );
}

export function Field({
  label,
  htmlFor,
  hint,
  error,
  children,
  className,
}: {
  label: string;
  htmlFor: string;
  hint?: string;
  error?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("form-field", className)}>
      <label htmlFor={htmlFor}>{label}</label>
      {hint ? <p className="field-hint">{hint}</p> : null}
      {children}
      {error ? (
        <p className="field-error" id={`${htmlFor}-error`} role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}

export function EmptyState({
  icon,
  title,
  description,
  action,
}: {
  icon?: ReactNode;
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="empty-state">
      {icon ? <span className="empty-state-icon">{icon}</span> : null}
      <h2>{title}</h2>
      <p>{description}</p>
      {action ? <div>{action}</div> : null}
    </div>
  );
}

export function ErrorState({
  title = "We couldn’t load this view",
  message,
  retry,
}: {
  title?: string;
  message?: string;
  retry?: () => void;
}) {
  return (
    <div className="error-state" role="alert">
      <strong>{title}</strong>
      <p>{message ?? "The information you asked for isn’t available right now. Try again, or return to the previous workspace."}</p>
      {retry ? <Button onClick={retry} variant="secondary">Try again</Button> : null}
    </div>
  );
}

export function PageHeader({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <header className="page-header">
      <div>
        {eyebrow ? <p className="eyebrow">{eyebrow}</p> : null}
        <h1>{title}</h1>
        {description ? <p>{description}</p> : null}
      </div>
      {action ? <div className="page-header-action">{action}</div> : null}
    </header>
  );
}

export function SectionHeader({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="section-header">
      <div>
        <h2>{title}</h2>
        {description ? <p>{description}</p> : null}
      </div>
      {action}
    </div>
  );
}

export const Dialog = DialogPrimitive.Root;
export const DialogTrigger = DialogPrimitive.Trigger;
export function DialogContent({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: ReactNode;
}) {
  return (
    <DialogPrimitive.Portal>
      <DialogPrimitive.Overlay className="dialog-overlay" />
      <DialogPrimitive.Content className="dialog-content">
        <DialogPrimitive.Title>{title}</DialogPrimitive.Title>
        {description ? (
          <DialogPrimitive.Description>{description}</DialogPrimitive.Description>
        ) : null}
        {children}
        <DialogPrimitive.Close className="dialog-close" aria-label="Close">
          <X size={18} />
        </DialogPrimitive.Close>
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  );
}

export const Tabs = TabsPrimitive.Root;
export const TabsList = TabsPrimitive.List;
export const TabsTrigger = TabsPrimitive.Trigger;
export const TabsContent = TabsPrimitive.Content;

export const TooltipProvider = TooltipPrimitive.Provider;
export const Tooltip = TooltipPrimitive.Root;
export const TooltipTrigger = TooltipPrimitive.Trigger;
export const TooltipContent = TooltipPrimitive.Content;

export const Select = SelectPrimitive.Root;
export const SelectValue = SelectPrimitive.Value;
export const SelectTrigger = SelectPrimitive.Trigger;
export function SelectContent({ children }: { children: ReactNode }) {
  return (
    <SelectPrimitive.Portal>
      <SelectPrimitive.Content className="select-content" position="popper">
        <SelectPrimitive.Viewport>{children}</SelectPrimitive.Viewport>
      </SelectPrimitive.Content>
    </SelectPrimitive.Portal>
  );
}
export function SelectItem({
  value,
  children,
}: {
  value: string;
  children: ReactNode;
}) {
  return (
    <SelectPrimitive.Item className="select-item" value={value}>
      <SelectPrimitive.ItemText>{children}</SelectPrimitive.ItemText>
      <SelectPrimitive.ItemIndicator><Check size={15} /></SelectPrimitive.ItemIndicator>
    </SelectPrimitive.Item>
  );
}

export function SelectButton({
  placeholder,
  "aria-label": ariaLabel,
}: {
  placeholder: string;
  "aria-label": string;
}) {
  return (
    <SelectTrigger className="ui-input select-trigger" aria-label={ariaLabel}>
      <SelectValue placeholder={placeholder} />
      <ChevronDown size={16} />
    </SelectTrigger>
  );
}
