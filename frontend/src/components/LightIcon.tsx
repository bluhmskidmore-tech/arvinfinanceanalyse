import type { SVGProps } from "react";

export type LightIconName =
  | "alert"
  | "apartment"
  | "appstore"
  | "arrow-down"
  | "arrow-right"
  | "arrow-up"
  | "bank"
  | "bar-chart"
  | "bulb"
  | "calendar"
  | "check-circle"
  | "check-square"
  | "database"
  | "dot-chart"
  | "clock"
  | "eye"
  | "file-search"
  | "file-text"
  | "fund"
  | "fund-projection"
  | "info-circle"
  | "line-chart"
  | "loading"
  | "question-circle"
  | "reload"
  | "safety-certificate"
  | "search"
  | "settings"
  | "star"
  | "table"
  | "team"
  | "thunderbolt"
  | "trophy"
  | "unordered-list"
  | "user"
  | "warning";

type LightIconProps = Omit<SVGProps<SVGSVGElement>, "name"> & {
  name: LightIconName;
  title?: string;
};

function IconPath({ name }: { name: LightIconName }) {
  switch (name) {
    case "alert":
    case "warning":
      return (
        <>
          <path d="M12 3 2.8 19h18.4L12 3Z" />
          <path d="M12 8v5" />
          <path d="M12 17h.01" />
        </>
      );
    case "apartment":
      return (
        <>
          <path d="M4 20V8l8-4 8 4v12" />
          <path d="M8 20v-6h8v6" />
          <path d="M8 10h.01M12 10h.01M16 10h.01" />
        </>
      );
    case "appstore":
      return (
        <>
          <rect x="4" y="4" width="6" height="6" rx="1.5" />
          <rect x="14" y="4" width="6" height="6" rx="1.5" />
          <rect x="4" y="14" width="6" height="6" rx="1.5" />
          <rect x="14" y="14" width="6" height="6" rx="1.5" />
        </>
      );
    case "arrow-down":
      return (
        <>
          <path d="M12 5v14" />
          <path d="m6 13 6 6 6-6" />
        </>
      );
    case "arrow-right":
      return (
        <>
          <path d="M5 12h14" />
          <path d="m13 6 6 6-6 6" />
        </>
      );
    case "arrow-up":
      return (
        <>
          <path d="M12 19V5" />
          <path d="m6 11 6-6 6 6" />
        </>
      );
    case "bank":
      return (
        <>
          <path d="m3 10 9-6 9 6" />
          <path d="M5 10h14" />
          <path d="M6 10v8M10 10v8M14 10v8M18 10v8" />
          <path d="M4 18h16" />
        </>
      );
    case "bar-chart":
      return (
        <>
          <path d="M4 19V5" />
          <path d="M4 19h16" />
          <path d="M8 16v-5M12 16V8M16 16v-8" />
        </>
      );
    case "bulb":
      return (
        <>
          <path d="M9 18h6" />
          <path d="M10 22h4" />
          <path d="M8.5 14.5a6 6 0 1 1 7 0c-.9.7-1.5 1.7-1.5 3h-4c0-1.3-.6-2.3-1.5-3Z" />
        </>
      );
    case "calendar":
      return (
        <>
          <rect x="4" y="5" width="16" height="15" rx="2" />
          <path d="M8 3v4M16 3v4M4 10h16" />
        </>
      );
    case "check-circle":
      return (
        <>
          <circle cx="12" cy="12" r="8" />
          <path d="m8.5 12.5 2.2 2.2 4.8-5.1" />
        </>
      );
    case "check-square":
      return (
        <>
          <rect x="4" y="4" width="16" height="16" rx="2" />
          <path d="m8.5 12.3 2.3 2.3 4.8-5.2" />
        </>
      );
    case "database":
      return (
        <>
          <ellipse cx="12" cy="6" rx="7" ry="3" />
          <path d="M5 6v6c0 1.7 3.1 3 7 3s7-1.3 7-3V6" />
          <path d="M5 12v6c0 1.7 3.1 3 7 3s7-1.3 7-3v-6" />
        </>
      );
    case "clock":
      return (
        <>
          <circle cx="12" cy="12" r="8" />
          <path d="M12 7v5l3 2" />
        </>
      );
    case "dot-chart":
      return (
        <>
          <path d="M4 19h16" />
          <circle cx="8" cy="15" r="1.5" />
          <circle cx="12" cy="10" r="1.5" />
          <circle cx="17" cy="7" r="1.5" />
        </>
      );
    case "eye":
      return (
        <>
          <path d="M2.8 12s3.3-6 9.2-6 9.2 6 9.2 6-3.3 6-9.2 6-9.2-6-9.2-6Z" />
          <circle cx="12" cy="12" r="2.5" />
        </>
      );
    case "file-search":
      return (
        <>
          <path d="M6 3h8l4 4v14H6z" />
          <path d="M14 3v5h5" />
          <circle cx="11" cy="14" r="2.5" />
          <path d="m13 16 2 2" />
        </>
      );
    case "file-text":
      return (
        <>
          <path d="M6 3h8l4 4v14H6z" />
          <path d="M14 3v5h5" />
          <path d="M9 12h6M9 16h6" />
        </>
      );
    case "fund":
      return (
        <>
          <path d="M4 18V8" />
          <path d="M8 18V5" />
          <path d="M12 18v-7" />
          <path d="M16 18V9" />
          <path d="M20 18V6" />
        </>
      );
    case "fund-projection":
      return (
        <>
          <rect x="4" y="5" width="16" height="12" rx="2" />
          <path d="M8 14v-3M12 14V8M16 14v-5" />
          <path d="M9 21h6" />
        </>
      );
    case "info-circle":
    case "question-circle":
      return (
        <>
          <circle cx="12" cy="12" r="8" />
          {name === "question-circle" ? <path d="M9.8 9a2.4 2.4 0 1 1 4.2 1.6c-1 .8-2 1.2-2 2.9" /> : <path d="M12 11v5" />}
          <path d="M12 8h.01" />
        </>
      );
    case "line-chart":
      return (
        <>
          <path d="M4 19h16" />
          <path d="M5 15 9 11l3 2 6-7" />
        </>
      );
    case "loading":
      return (
        <>
          <path d="M12 3a9 9 0 0 1 9 9" />
          <path d="M21 12a9 9 0 0 1-9 9" opacity="0.35" />
          <path d="M12 21a9 9 0 0 1-9-9" opacity="0.35" />
        </>
      );
    case "reload":
      return (
        <>
          <path d="M20 12a8 8 0 1 1-2.3-5.7" />
          <path d="M20 4v6h-6" />
        </>
      );
    case "safety-certificate":
      return (
        <>
          <path d="M12 3 5 6v5c0 4.4 2.8 7.9 7 10 4.2-2.1 7-5.6 7-10V6z" />
          <path d="m8.8 12.2 2 2 4.4-4.6" />
        </>
      );
    case "search":
      return (
        <>
          <circle cx="11" cy="11" r="6" />
          <path d="m16 16 4 4" />
        </>
      );
    case "settings":
      return (
        <>
          <circle cx="12" cy="12" r="3" />
          <path d="M19 12a7 7 0 0 0-.1-1l2-1.5-2-3.4-2.4 1a7.5 7.5 0 0 0-1.7-1L14.5 3h-5l-.4 3.1a7.5 7.5 0 0 0-1.7 1l-2.4-1-2 3.4 2 1.5a7 7 0 0 0 0 2l-2 1.5 2 3.4 2.4-1a7.5 7.5 0 0 0 1.7 1l.4 3.1h5l.4-3.1a7.5 7.5 0 0 0 1.7-1l2.4 1 2-3.4-2-1.5a7 7 0 0 0 .1-1Z" />
        </>
      );
    case "star":
      return <path d="m12 3 2.6 5.4 5.9.8-4.3 4.2 1 5.9L12 16.5 6.8 19.3l1-5.9-4.3-4.2 5.9-.8z" />;
    case "table":
      return (
        <>
          <rect x="4" y="5" width="16" height="14" rx="2" />
          <path d="M4 10h16M9 5v14M15 5v14" />
        </>
      );
    case "team":
      return (
        <>
          <circle cx="9" cy="8" r="3" />
          <circle cx="17" cy="10" r="2" />
          <path d="M3.5 20a5.5 5.5 0 0 1 11 0" />
          <path d="M14.5 17.5A4.5 4.5 0 0 1 21 21" />
        </>
      );
    case "thunderbolt":
      return <path d="M13 2 4 14h7l-1 8 10-13h-7z" />;
    case "trophy":
      return (
        <>
          <path d="M8 4h8v4a4 4 0 0 1-8 0z" />
          <path d="M8 6H4v2a4 4 0 0 0 4 4M16 6h4v2a4 4 0 0 1-4 4" />
          <path d="M12 12v5M9 21h6M8 17h8" />
        </>
      );
    case "unordered-list":
      return (
        <>
          <path d="M8 7h12M8 12h12M8 17h12" />
          <path d="M4 7h.01M4 12h.01M4 17h.01" />
        </>
      );
    case "user":
      return (
        <>
          <circle cx="12" cy="8" r="4" />
          <path d="M5 21a7 7 0 0 1 14 0" />
        </>
      );
  }
}

export function LightIcon({ className, name, title, ...props }: LightIconProps) {
  const classes = ["moss-light-icon", className].filter(Boolean).join(" ");

  return (
    <svg
      aria-hidden={title ? undefined : "true"}
      className={classes}
      data-icon={name}
      fill="none"
      focusable="false"
      role={title ? "img" : undefined}
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="2"
      viewBox="0 0 24 24"
      {...props}
    >
      {title ? <title>{title}</title> : null}
      <IconPath name={name} />
    </svg>
  );
}
