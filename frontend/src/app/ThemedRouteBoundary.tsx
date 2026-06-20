import type { ReactNode } from "react";

type ThemedRouteBoundaryProps = {
  children: ReactNode;
};

export default function ThemedRouteBoundary({ children }: ThemedRouteBoundaryProps) {
  return <>{children}</>;
}
