import { useQuery } from "@tanstack/react-query";
import { useLocation } from "react-router-dom";

import { useApiClient } from "../../../api/client";
import { workbenchNavigation } from "../../../mocks/navigation";

export default function WorkbenchPlaceholderPage() {
  const client = useApiClient();
  const location = useLocation();
  const section =
    workbenchNavigation.find((item) => item.path === location.pathname) ??
    workbenchNavigation[0];

  const { data } = useQuery({
    queryKey: ["workbench-placeholder", section.key],
    queryFn: () => client.getPlaceholderSnapshot(section.key),
  });

  const snapshot = data?.result;

  return (
    <section>
      <h1
        style={{
          marginTop: 0,
          marginBottom: 10,
          fontSize: 32,
          fontWeight: 600,
          letterSpacing: "-0.03em",
        }}
      >
        {snapshot?.title ?? section.label}
      </h1>
      <p
        style={{
          marginBottom: 24,
          color: "#5c6b82",
          fontSize: 15,
        }}
      >
        {snapshot?.summary}
      </p>

      <div
        style={{
          padding: 24,
          borderRadius: 20,
          background: "#fbfcfe",
          border: "1px solid #e4ebf5",
          boxShadow: "0 18px 40px rgba(19, 37, 70, 0.08)",
        }}
      >
        <ul style={{ margin: 0, paddingLeft: 18, color: "#5c6b82" }}>
          {(snapshot?.highlights ?? []).map((item) => (
            <li key={item} style={{ marginBottom: 10 }}>
              {item}
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
