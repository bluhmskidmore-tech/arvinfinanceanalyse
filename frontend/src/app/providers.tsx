import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";

import { ApiClientProvider, type ApiClient } from "../api/clientContext";

type AppProvidersProps = {
  children: ReactNode;
  client?: ApiClient;
};

export function AppProviders({ children, client }: AppProvidersProps) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 60_000,
            // 默认 gcTime 仅 5 分钟：离开首页超过 5 分钟再回来，全部查询被回收、
            // 退回冷加载。延长后切回页面先渲染缓存再后台校验（staleTime 语义不变）。
            gcTime: 30 * 60_000,
            retry: 0,
            refetchOnWindowFocus: false,
          },
        },
      }),
  );

  return (
    <ApiClientProvider client={client}>
      <QueryClientProvider client={queryClient}>
        {children}
      </QueryClientProvider>
    </ApiClientProvider>
  );
}
