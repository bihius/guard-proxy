import type { ComponentProps } from "react";

type IconProps = ComponentProps<"svg">;

function iconProps(props: IconProps) {
  return {
    width: 16,
    height: 16,
    viewBox: "0 0 16 16",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.4,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    ...props,
  };
}

export function InfoIcon(props: IconProps) {
  return (
    <svg {...iconProps(props)}>
      <circle cx="8" cy="8" r="6.5" />
      <line x1="8" y1="7" x2="8" y2="11" />
      <circle cx="8" cy="5" r="0.5" fill="currentColor" />
    </svg>
  );
}

export function ArrowRightIcon(props: IconProps) {
  return (
    <svg {...iconProps(props)}>
      <line x1="3" y1="8" x2="13" y2="8" />
      <polyline points="9 4 13 8 9 12" />
    </svg>
  );
}

export function ShieldIcon(props: IconProps) {
  return (
    <svg
      {...iconProps({
        width: 20,
        height: 20,
        viewBox: "0 0 20 20",
        strokeWidth: 1.6,
        ...props,
      })}
    >
      <path d="M10 2 L3 6 L3 11 C3 15 6 18 10 19 C14 18 17 15 17 11 L17 6 Z" />
      <polyline points="7 10 9.5 12.5 13.5 7.5" />
    </svg>
  );
}

export function LeafIcon(props: IconProps) {
  return (
    <svg {...iconProps(props)}>
      <path d="M4 14s1-6 8-10c-4 4-6 7-8 10z" />
      <path d="M4 14c2-2 4-3 8-4" />
    </svg>
  );
}

export function SnowflakeIcon(props: IconProps) {
  return (
    <svg {...iconProps(props)}>
      <line x1="8" y1="1" x2="8" y2="15" />
      <line x1="1" y1="8" x2="15" y2="8" />
      <line x1="3" y1="3" x2="13" y2="13" />
      <line x1="13" y1="3" x2="3" y2="13" />
      <line x1="8" y1="1" x2="6.5" y2="3" />
      <line x1="8" y1="1" x2="9.5" y2="3" />
      <line x1="8" y1="15" x2="6.5" y2="13" />
      <line x1="8" y1="15" x2="9.5" y2="13" />
    </svg>
  );
}

export function MenuIcon(props: IconProps) {
  return (
    <svg
      {...iconProps({
        width: 20,
        height: 20,
        viewBox: "0 0 20 20",
        strokeWidth: 1.8,
        ...props,
      })}
    >
      <line x1="3" y1="5" x2="17" y2="5" />
      <line x1="3" y1="10" x2="17" y2="10" />
      <line x1="3" y1="15" x2="17" y2="15" />
    </svg>
  );
}

export function CloseIcon(props: IconProps) {
  return (
    <svg
      {...iconProps({
        width: 18,
        height: 18,
        viewBox: "0 0 18 18",
        strokeWidth: 1.8,
        ...props,
      })}
    >
      <line x1="4" y1="4" x2="14" y2="14" />
      <line x1="14" y1="4" x2="4" y2="14" />
    </svg>
  );
}

export function ServerIcon(props: IconProps) {
  return (
    <svg
      {...iconProps({
        width: 18,
        height: 18,
        viewBox: "0 0 18 18",
        strokeWidth: 1.5,
        ...props,
      })}
    >
      <rect x="3" y="3" width="12" height="4" rx="1.5" />
      <rect x="3" y="11" width="12" height="4" rx="1.5" />
      <line x1="6" y1="5" x2="6.01" y2="5" />
      <line x1="6" y1="13" x2="6.01" y2="13" />
    </svg>
  );
}

export function AlertTriangleIcon(props: IconProps) {
  return (
    <svg
      {...iconProps({
        width: 18,
        height: 18,
        viewBox: "0 0 18 18",
        strokeWidth: 1.5,
        ...props,
      })}
    >
      <path d="M9 3.2 15 14H3L9 3.2Z" />
      <line x1="9" y1="7" x2="9" y2="10.5" />
      <circle cx="9" cy="12.8" r="0.5" fill="currentColor" />
    </svg>
  );
}

export function PulseIcon(props: IconProps) {
  return (
    <svg
      {...iconProps({
        width: 18,
        height: 18,
        viewBox: "0 0 18 18",
        strokeWidth: 1.5,
        ...props,
      })}
    >
      <polyline points="2.5 9.5 5.5 9.5 7.2 5.5 10.3 12.5 12.1 8.2 15.5 8.2" />
    </svg>
  );
}
